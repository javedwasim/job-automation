from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.job_alerts.classification.contracts import ClassificationResult
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.jobs.fingerprinting.job_fingerprint_service import JobFingerprintService
from app.jobs.models.enums import JobStatus
from app.jobs.models.job import Job
from app.jobs.models.job_category import JobCategory
from app.jobs.models.processing_event import ProcessingEvent


class JobRepository:
    def __init__(
        self, db: Session, fingerprint_service: JobFingerprintService | None = None
    ) -> None:
        self._db = db
        self._fingerprints = fingerprint_service or JobFingerprintService()

    def find_by_fingerprint(self, fingerprint: str) -> Job | None:
        return self._db.scalar(select(Job).where(Job.fingerprint == fingerprint))

    def persist(
        self,
        *,
        job_email_id: int,
        normalized_job: NormalizedJob,
        classification: ClassificationResult,
        platform_id: int | None = None,
    ) -> Job:
        """Computes the centralized fingerprint (platform + canonical URL,
        spec section 16) and either:
          - records a DUPLICATE processing event and returns the existing Job
            — enriching it ONLY with fields the existing record is missing
            (e.g. a posting date a later email stated and the first didn't).
            Existing values are never overwritten and job_posted_at is never
            replaced with a later email's received_at (spec sections 3/10/16),
          - or inserts a new Job with status RELEVANT/IRRELEVANT based on
            classification.
        """
        fingerprint = self._fingerprints.fingerprint(
            platform=normalized_job.source,
            job_url=normalized_job.job_url,
            title=normalized_job.title,
            company=normalized_job.company,
            platform_job_id=normalized_job.platform_job_id,
        )

        existing = self.find_by_fingerprint(fingerprint)
        if existing is not None:
            self._enrich_existing(existing, normalized_job)
            self._record_event(
                job_email_id=job_email_id,
                job_id=existing.id,
                event_type="duplicate_detected",
                status="skipped",
                message=f"Fingerprint {fingerprint} already exists as job {existing.id}",
            )
            return existing

        now = datetime.now(UTC)
        status = JobStatus.RELEVANT if classification.matched else JobStatus.IRRELEVANT

        job = Job(
            job_email_id=job_email_id,
            platform_id=platform_id,
            fingerprint=fingerprint,
            title=normalized_job.title,
            company=normalized_job.company,
            location=normalized_job.location,
            job_url=normalized_job.job_url,
            application_url=normalized_job.application_url,
            platform_job_id=normalized_job.platform_job_id,
            job_posted_at=normalized_job.job_posted_at,
            received_at=normalized_job.received_at,
            remote_type=normalized_job.remote_type,
            salary=normalized_job.salary,
            employment_type=normalized_job.employment_type,
            status=status,
            created_at=now,
            updated_at=now,
        )

        if classification.matched:
            categories = self._db.scalars(
                select(JobCategory).where(JobCategory.name.in_(classification.categories))
            ).all()
            job.categories = list(categories)

        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)

        self._record_event(
            job_email_id=job_email_id,
            job_id=job.id,
            event_type="job_persisted",
            status="success",
            message=f"Persisted with status {status.value}",
        )
        return job

    def list_relevant(self, limit: int = 100) -> list[Job]:
        return list(
            self._db.scalars(
                select(Job)
                .where(Job.status.in_([JobStatus.RELEVANT, JobStatus.EXPORTED]))
                .order_by(Job.received_at.desc())
                .limit(limit)
            )
        )

    def list_all(self, limit: int = 200) -> list[Job]:
        """Every extracted job regardless of classification status, most
        recently received first — the dashboard shows the pipeline's full
        output, not only category matches."""
        return list(self._db.scalars(select(Job).order_by(Job.received_at.desc()).limit(limit)))

    def list_paginated(self, *, page: int, page_size: int) -> tuple[list[Job], int]:
        """One page of jobs, newest received first (id as the tiebreaker so
        rows sharing a received_at keep a stable order), plus the total row
        count for the dashboard's pager. Page is 1-based."""
        total = self._db.scalar(select(func.count()).select_from(Job)) or 0
        rows = list(
            self._db.scalars(
                select(Job)
                .order_by(Job.received_at.desc(), Job.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total

    def _enrich_existing(self, existing: Job, normalized_job: NormalizedJob) -> None:
        """Merge policy for a repeated job (spec section 16): fill in fields
        the first email didn't state, never overwrite what's already known,
        never fabricate. job_posted_at is only set when it was NULL and the
        new candidate has a REAL extracted posting date."""
        changed = False
        if existing.job_posted_at is None and normalized_job.job_posted_at is not None:
            existing.job_posted_at = normalized_job.job_posted_at
            changed = True
        for field in ("remote_type", "salary", "employment_type"):
            if getattr(existing, field) is None:
                new_value = getattr(normalized_job, field)
                if new_value is not None:
                    setattr(existing, field, new_value)
                    changed = True
        if changed:
            existing.updated_at = datetime.now(UTC)
            self._db.commit()

    def record_event(
        self, *, job_email_id: int, job_id: int | None, event_type: str, status: str, message: str
    ) -> None:
        """Public event recorder — used by the centralized processing
        pipeline to log normalization rejections and freshness filtering
        outcomes for emails whose candidates never became Job rows."""
        self._record_event(
            job_email_id=job_email_id,
            job_id=job_id,
            event_type=event_type,
            status=status,
            message=message,
        )

    def _record_event(
        self, *, job_email_id: int, job_id: int | None, event_type: str, status: str, message: str
    ) -> None:
        event = ProcessingEvent(
            job_email_id=job_email_id,
            job_id=job_id,
            event_type=event_type,
            status=status,
            message=message,
            created_at=datetime.now(UTC),
        )
        self._db.add(event)
        self._db.commit()
