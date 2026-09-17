from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.gmail.dto import NormalizedEmail
from app.job_alerts.classification.rule_based_classifier import RuleBasedClassifier
from app.job_alerts.normalization.freshness import FreshnessPolicy
from app.job_alerts.normalization.job_normalizer import JobNormalizer
from app.job_alerts.parsers.registry import ParserRegistry
from app.jobs.models.job import Job
from app.jobs.models.job_category import JobCategory
from app.jobs.models.job_platform import JobPlatform
from app.repositories.job_repository import JobRepository


class JobProcessingService:
    """Runs the centralized, platform-independent processing pipeline (spec
    sections 15/37) for a single already-ingested email:

        parser.parse(email)  ->  list[NormalizedJob]      (platform layer)
          -> JobNormalizer    normalization + validation  (shared)
          -> FreshnessPolicy  MAX_JOB_AGE_HOURS filtering (shared)
          -> RuleBasedClassifier classification          (shared)
          -> JobRepository    fingerprint dedupe + persist(shared)

    Gmail search/ingestion (Phase 1) is a separate concern.
    """

    def __init__(self, db: Session, registry: ParserRegistry | None = None) -> None:
        self._db = db
        self._registry = registry or ParserRegistry()
        self._job_repository = JobRepository(db)
        self._normalizer = JobNormalizer()
        settings = get_settings()
        self._freshness = FreshnessPolicy(
            max_age_hours=settings.max_job_age_hours,
            unknown_date_policy=settings.unknown_date_policy,
        )

    def process_email(self, *, job_email_id: int, email: NormalizedEmail) -> list[Job]:
        parser = self._registry.get_parser(email)
        candidates = parser.parse(email)

        # Centralized normalization + validation (spec sections 2, 15):
        # clean fields, canonical URLs, extracted job IDs, resolved dates;
        # drop candidates that cannot be validated — with an explicit event.
        normalized_jobs, rejected = self._normalizer.normalize_all(
            candidates, platform=parser.slug
        )
        for item in rejected:
            self._job_repository.record_event(
                job_email_id=job_email_id,
                job_id=None,
                event_type="normalization_rejected",
                status="skipped",
                message=f"Candidate rejected during normalization: {item.reason}",
            )
        if not normalized_jobs:
            return []

        # Centralized freshness filtering (spec section 6): age is computed
        # from job_posted_at against the email's received_at, NEVER from
        # received_at itself; unknown dates follow the explicit policy and
        # are never fabricated (spec section 7). Promoted jobs are filtered
        # exactly like organic ones — only their posting age matters.
        accepted_jobs, stale = self._freshness.filter(normalized_jobs)
        for decision in stale:
            self._job_repository.record_event(
                job_email_id=job_email_id,
                job_id=None,
                event_type="filtered_stale",
                status="skipped",
                message=(
                    f"Job '{decision.job.title}' older than "
                    f"{self._freshness.max_age_hours}h (reason: {decision.reason})"
                ),
            )
        if not accepted_jobs:
            return []

        categories = list(
            self._db.scalars(select(JobCategory).where(JobCategory.enabled.is_(True)))
        )
        classifier = RuleBasedClassifier(categories)

        platform = self._db.scalar(select(JobPlatform).where(JobPlatform.slug == parser.slug))

        persisted: list[Job] = []
        for normalized_job in accepted_jobs:
            classification = classifier.classify(normalized_job)
            job = self._job_repository.persist(
                job_email_id=job_email_id,
                normalized_job=normalized_job,
                classification=classification,
                platform_id=platform.id if platform else None,
            )
            persisted.append(job)

        return persisted

