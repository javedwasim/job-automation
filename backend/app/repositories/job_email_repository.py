import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gmail.dto import NormalizedEmail
from app.jobs.models.enums import JobEmailStatus
from app.jobs.models.job import Job
from app.jobs.models.job_email import JobEmail
from app.jobs.models.processing_event import ProcessingEvent


class JobEmailRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def is_already_processed(self, gmail_account_id: int, gmail_message_id: str) -> bool:
        """The dedup check spec section 22 calls for: 'if message already
        processed: skip'."""
        existing = self._db.scalar(
            select(JobEmail).where(
                JobEmail.gmail_account_id == gmail_account_id,
                JobEmail.gmail_message_id == gmail_message_id,
            )
        )
        return existing is not None

    def create_from_normalized_email(
        self, *, gmail_account_id: int, email: NormalizedEmail, source: str | None = None
    ) -> JobEmail:
        now = datetime.now(UTC)
        raw_hash = hashlib.sha256(
            f"{email.gmail_message_id}:{email.subject}:{email.plain_text}".encode()
        ).hexdigest()

        job_email = JobEmail(
            gmail_account_id=gmail_account_id,
            gmail_message_id=email.gmail_message_id,
            thread_id=email.thread_id,
            source=source,
            sender=email.sender,
            subject=email.subject[:998],
            received_at=email.received_at,
            status=JobEmailStatus.NEW,
            raw_hash=raw_hash,
            created_at=now,
            updated_at=now,
        )
        self._db.add(job_email)
        self._db.commit()
        self._db.refresh(job_email)
        return job_email

    def mark_processed(self, job_email: JobEmail) -> None:
        job_email.status = JobEmailStatus.PROCESSED
        job_email.processed_at = datetime.now(UTC)
        job_email.updated_at = datetime.now(UTC)
        self._db.commit()

    def mark_failed(self, job_email: JobEmail) -> None:
        job_email.status = JobEmailStatus.FAILED
        job_email.updated_at = datetime.now(UTC)
        self._db.commit()

    def list_recent(self, limit: int = 50) -> list[JobEmail]:
        return list(
            self._db.scalars(select(JobEmail).order_by(JobEmail.received_at.desc()).limit(limit))
        )

    def list_without_job(self, gmail_account_id: int) -> list[JobEmail]:
        """Returns job_emails for this account that the extraction pipeline
        has never produced ANY outcome for: no Job row AND no processing
        event (job_persisted / duplicate_detected / backfill_attempted).

        This makes backfill one-shot per email: newsletters that parse to
        zero jobs and digest re-sends whose jobs were all duplicates can
        never grow a Job row, so without the event check they would be
        re-downloaded from Gmail on every backfill forever.
        """
        job_email_ids_with_jobs = select(Job.job_email_id)
        job_email_ids_with_events = select(ProcessingEvent.job_email_id)
        return list(
            self._db.scalars(
                select(JobEmail).where(
                    JobEmail.gmail_account_id == gmail_account_id,
                    JobEmail.id.not_in(job_email_ids_with_jobs),
                    JobEmail.id.not_in(job_email_ids_with_events),
                )
            )
        )

    def record_processing_event(
        self, *, job_email_id: int, event_type: str, status: str, message: str
    ) -> None:
        """Persists a pipeline outcome for an email that produced no Job row
        of its own (used by backfill to mark emails as attempted)."""
        self._db.add(
            ProcessingEvent(
                job_email_id=job_email_id,
                job_id=None,
                event_type=event_type,
                status=status,
                message=message,
                created_at=datetime.now(UTC),
            )
        )
        self._db.commit()
