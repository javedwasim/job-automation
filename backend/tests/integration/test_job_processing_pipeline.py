from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.gmail.normalizer import normalize_email
from app.jobs.models.enums import JobStatus
from app.jobs.models.job import Job
from app.jobs.models.job_category import JobCategory
from app.jobs.models.job_category_keyword import JobCategoryKeyword, MatchType
from app.jobs.models.processing_event import ProcessingEvent
from app.jobs.services.job_processing_service import JobProcessingService
from tests.fixtures.linkedin.job_alert_message import make_raw_message


def _seed_laravel_category(db_session: Session) -> None:
    now = datetime.now(UTC)
    category = JobCategory(
        name="Laravel", slug="laravel", enabled=True, created_at=now, updated_at=now
    )
    category.keywords = [
        JobCategoryKeyword(
            keyword="laravel", match_type=MatchType.WORD_BOUNDARY, created_at=now, updated_at=now
        )
    ]
    db_session.add(category)
    db_session.commit()


def test_same_job_from_two_emails_persists_only_once(db_session: Session) -> None:
    _seed_laravel_category(db_session)
    service = JobProcessingService(db_session)

    # Two different emails, same underlying job (same LinkedIn job ID/URL),
    # e.g. a re-sent digest — simulate via two distinct gmail_message_ids.
    email_1 = normalize_email(make_raw_message(message_id="msg-1"))
    email_2 = normalize_email(make_raw_message(message_id="msg-2"))

    jobs_from_first = service.process_email(job_email_id=1, email=email_1)
    jobs_from_second = service.process_email(job_email_id=2, email=email_2)

    assert len(jobs_from_first) == 1
    assert len(jobs_from_second) == 1
    # Same fingerprint -> same underlying Job row returned both times.
    assert jobs_from_first[0].id == jobs_from_second[0].id

    assert db_session.query(Job).count() == 1

    duplicate_events = (
        db_session.query(ProcessingEvent)
        .filter(ProcessingEvent.event_type == "duplicate_detected")
        .count()
    )
    assert duplicate_events == 1


def test_relevant_job_classified_and_persisted_with_categories(db_session: Session) -> None:
    _seed_laravel_category(db_session)
    service = JobProcessingService(db_session)

    email = normalize_email(make_raw_message(message_id="msg-1"))
    jobs = service.process_email(job_email_id=1, email=email)

    job = jobs[0]
    assert job.status == JobStatus.RELEVANT
    assert any(c.name == "Laravel" for c in job.categories)
    # job_posted_at and received_at are distinct fields, never conflated.
    received_at = job.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    assert received_at == email.received_at


def test_job_posted_at_preserved_as_none_when_email_gives_no_date(db_session: Session) -> None:
    _seed_laravel_category(db_session)
    service = JobProcessingService(db_session)

    email = normalize_email(make_raw_message(message_id="msg-1"))
    job = service.process_email(job_email_id=1, email=email)[0]

    # The fixture email has no "Posted X ago" phrase, so job_posted_at must
    # be NULL — never silently defaulted to received_at.
    assert job.job_posted_at is None
    assert job.received_at is not None
