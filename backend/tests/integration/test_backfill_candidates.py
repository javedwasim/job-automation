from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.gmail.dto import NormalizedEmail
from app.jobs.models.enums import JobStatus
from app.jobs.models.job import Job
from app.jobs.models.processing_event import ProcessingEvent
from app.repositories.job_email_repository import JobEmailRepository


def _ingest_email(db: Session, *, message_id: str, account_id: int = 1):
    email = NormalizedEmail(
        gmail_message_id=message_id,
        thread_id=message_id,
        sender="LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
        subject="New jobs for you",
        received_at=datetime.now(UTC),
        plain_text="body",
        html=None,
        links=[],
    )
    return JobEmailRepository(db).create_from_normalized_email(
        gmail_account_id=account_id, email=email
    )


def test_email_without_job_or_event_is_backfill_candidate(db_session: Session) -> None:
    job_email = _ingest_email(db_session, message_id="m-1")

    pending = JobEmailRepository(db_session).list_without_job(gmail_account_id=1)

    assert [e.id for e in pending] == [job_email.id]


def test_email_with_backfill_attempt_event_is_not_candidate(db_session: Session) -> None:
    repo = JobEmailRepository(db_session)
    job_email = _ingest_email(db_session, message_id="m-1")
    # e.g. a newsletter that parsed to zero jobs during a previous backfill.
    repo.record_processing_event(
        job_email_id=job_email.id,
        event_type="backfill_attempted",
        status="success",
        message="No job parsed from this email",
    )

    assert repo.list_without_job(gmail_account_id=1) == []


def test_email_with_failed_backfill_attempt_is_not_candidate(db_session: Session) -> None:
    repo = JobEmailRepository(db_session)
    job_email = _ingest_email(db_session, message_id="m-1")
    repo.record_processing_event(
        job_email_id=job_email.id,
        event_type="backfill_attempted",
        status="failed",
        message="Processing failed during backfill",
    )

    # Failed attempts are also one-shot: the error is in the event log and
    # server logs; retrying every backfill forever would re-download it.
    assert repo.list_without_job(gmail_account_id=1) == []


def test_email_with_duplicate_detected_event_is_not_candidate(db_session: Session) -> None:
    repo = JobEmailRepository(db_session)
    job_email = _ingest_email(db_session, message_id="m-1")
    # Re-sent digest whose jobs were all duplicates of an earlier email:
    # no Job row points at this email, but a duplicate_detected event does.
    db_session.add(
        ProcessingEvent(
            job_email_id=job_email.id,
            job_id=None,
            event_type="duplicate_detected",
            status="skipped",
            message="Fingerprint already exists",
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    assert repo.list_without_job(gmail_account_id=1) == []


def test_email_with_job_is_not_candidate(db_session: Session) -> None:
    repo = JobEmailRepository(db_session)
    job_email = _ingest_email(db_session, message_id="m-1")
    now = datetime.now(UTC)
    db_session.add(
        Job(
            job_email_id=job_email.id,
            fingerprint="fp-1",
            title="Backend Developer",
            received_at=now,
            status=JobStatus.RELEVANT,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    assert repo.list_without_job(gmail_account_id=1) == []


def test_events_for_other_accounts_do_not_shadow_candidates(db_session: Session) -> None:
    repo = JobEmailRepository(db_session)
    mine = _ingest_email(db_session, message_id="m-1", account_id=1)
    other = _ingest_email(db_session, message_id="m-2", account_id=2)
    repo.record_processing_event(
        job_email_id=other.id,
        event_type="backfill_attempted",
        status="success",
        message="no job",
    )

    pending = repo.list_without_job(gmail_account_id=1)
    assert [e.id for e in pending] == [mine.id]