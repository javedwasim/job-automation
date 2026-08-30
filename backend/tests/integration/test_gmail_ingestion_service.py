from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.gmail.models import GmailAccount
from app.jobs.models.enums import JobEmailStatus
from app.jobs.models.job_email import JobEmail
from app.jobs.models.job_platform import JobPlatform
from app.repositories.gmail_account_repository import GmailAccountRepository
from app.repositories.job_email_repository import JobEmailRepository
from tests.fixtures.linkedin.job_alert_message import make_raw_message


class FakeGmailClient:
    """Stands in for app.gmail.client.GmailClient so tests never touch the
    real Gmail API. Returns a fixed set of raw messages."""

    def __init__(self, raw_messages: dict[str, dict]) -> None:
        self._raw_messages = raw_messages
        self.applied_labels: list[tuple[str, str]] = []

    def search_message_ids(self, query: str, max_results: int = 100) -> list[str]:
        return list(self._raw_messages.keys())

    def get_message(self, message_id: str) -> dict:
        return self._raw_messages[message_id]

    def ensure_label(self, label_name: str) -> str:
        return "Label_1"

    def apply_label(self, message_id: str, label_id: str) -> None:
        self.applied_labels.append((message_id, label_id))


@pytest.fixture
def seeded_account(db_session: Session) -> GmailAccount:
    repo = GmailAccountRepository(db_session)
    return repo.upsert(
        user_id=1,
        email="me@example.com",
        access_token="fake-access-token",
        refresh_token="fake-refresh-token",
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.fixture
def seeded_linkedin_platform(db_session: Session) -> JobPlatform:
    now = datetime.now(UTC)
    platform = JobPlatform(
        name="LinkedIn",
        slug="linkedin",
        domain="linkedin.com",
        enabled=True,
        priority=10,
        created_at=now,
        updated_at=now,
    )
    db_session.add(platform)
    db_session.commit()
    db_session.refresh(platform)
    return platform


def _service_with_fake_client(db_session: Session, fake_client: FakeGmailClient, monkeypatch):
    """Builds a GmailIngestionService but monkeypatches its GmailClient
    construction to return our fake, so no network call is ever attempted."""
    from app.gmail import service as service_module

    monkeypatch.setattr(service_module, "GmailClient", lambda access_token: fake_client)
    return service_module.GmailIngestionService(db_session)


def test_sync_account_ingests_new_message_and_tags_platform(
    db_session: Session,
    seeded_account: GmailAccount,
    seeded_linkedin_platform: JobPlatform,
    monkeypatch,
) -> None:
    raw = make_raw_message(message_id="msg-1")
    fake_client = FakeGmailClient({"msg-1": raw})
    service = _service_with_fake_client(db_session, fake_client, monkeypatch)

    result = service.sync_account(seeded_account)

    assert result.messages_found == 1
    assert result.messages_ingested == 1
    assert result.messages_skipped_duplicate == 0
    assert result.messages_failed == 0

    stored = db_session.query(JobEmail).one()
    assert stored.gmail_message_id == "msg-1"
    assert stored.source == "linkedin"
    assert stored.status == JobEmailStatus.PROCESSED
    assert fake_client.applied_labels == [("msg-1", "Label_1")]


def test_sync_account_skips_already_processed_message(
    db_session: Session, seeded_account: GmailAccount, monkeypatch
) -> None:
    raw = make_raw_message(message_id="msg-1")
    fake_client = FakeGmailClient({"msg-1": raw})
    service = _service_with_fake_client(db_session, fake_client, monkeypatch)

    first = service.sync_account(seeded_account)
    second = service.sync_account(seeded_account)

    assert first.messages_ingested == 1
    assert second.messages_ingested == 0
    assert second.messages_skipped_duplicate == 1
    # Only one job_email row should ever exist for this message.
    assert db_session.query(JobEmail).count() == 1


def test_job_email_repository_dedup_check(
    db_session: Session, seeded_account: GmailAccount
) -> None:
    repo = JobEmailRepository(db_session)
    raw = make_raw_message(message_id="msg-42")

    from app.gmail.normalizer import normalize_email

    assert repo.is_already_processed(seeded_account.id, "msg-42") is False

    repo.create_from_normalized_email(
        gmail_account_id=seeded_account.id, email=normalize_email(raw), source="linkedin"
    )

    assert repo.is_already_processed(seeded_account.id, "msg-42") is True


def test_unique_constraint_blocks_duplicate_insert_at_db_level(
    db_session: Session, seeded_account: GmailAccount
) -> None:
    """Belt-and-suspenders: even if application logic had a bug, the DB
    uniqueness constraint from spec section 22 must hold."""
    from sqlalchemy.exc import IntegrityError

    repo = JobEmailRepository(db_session)
    raw = make_raw_message(message_id="msg-dup")
    from app.gmail.normalizer import normalize_email

    normalized = normalize_email(raw)
    repo.create_from_normalized_email(gmail_account_id=seeded_account.id, email=normalized)

    with pytest.raises(IntegrityError):
        repo.create_from_normalized_email(gmail_account_id=seeded_account.id, email=normalized)
