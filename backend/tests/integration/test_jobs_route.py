from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.jobs.models.enums import JobStatus
from app.jobs.models.job import Job
from app.main import app


@pytest.fixture
def api_client(db_session: Session) -> TestClient:
    """TestClient with the app's DB dependency pointed at the in-memory
    SQLite session instead of the real SessionLocal."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_job(
    db_session: Session,
    *,
    job_email_id: int,
    title: str,
    fingerprint: str,
    received_at: datetime,
) -> Job:
    now = datetime.now(UTC)
    job = Job(
        job_email_id=job_email_id,
        fingerprint=fingerprint,
        title=title,
        received_at=received_at,
        status=JobStatus.RELEVANT,
        created_at=now,
        updated_at=now,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _seed_three_jobs(db_session: Session) -> None:
    base = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    _seed_job(
        db_session,
        job_email_id=1,
        title="Oldest job",
        fingerprint="fp-oldest",
        received_at=base - timedelta(hours=3),
    )
    _seed_job(
        db_session,
        job_email_id=2,
        title="Middle job",
        fingerprint="fp-middle",
        received_at=base - timedelta(hours=2),
    )
    _seed_job(
        db_session,
        job_email_id=3,
        title="Newest job",
        fingerprint="fp-newest",
        received_at=base - timedelta(hours=1),
    )


def test_returns_newest_first_with_pagination_metadata(
    db_session: Session, api_client: TestClient
) -> None:
    _seed_three_jobs(db_session)

    response = api_client.get("/api/jobs", params={"page": 1, "page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total_pages"] == 2
    assert [item["title"] for item in body["items"]] == ["Newest job", "Middle job"]

    second = api_client.get("/api/jobs", params={"page": 2, "page_size": 2})
    assert second.status_code == 200
    second_body = second.json()
    assert [item["title"] for item in second_body["items"]] == ["Oldest job"]
    assert second_body["page"] == 2


def test_rows_sharing_received_at_keep_stable_id_desc_order(
    db_session: Session, api_client: TestClient
) -> None:
    same_time = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    first = _seed_job(
        db_session,
        job_email_id=1,
        title="Inserted first",
        fingerprint="fp-a",
        received_at=same_time,
    )
    second = _seed_job(
        db_session,
        job_email_id=2,
        title="Inserted second",
        fingerprint="fp-b",
        received_at=same_time,
    )

    response = api_client.get("/api/jobs", params={"page": 1, "page_size": 10})

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [second.id, first.id]


def test_rejects_invalid_pagination_params(api_client: TestClient) -> None:
    assert api_client.get("/api/jobs", params={"page": 0}).status_code == 422
    assert api_client.get("/api/jobs", params={"page_size": 0}).status_code == 422
    assert api_client.get("/api/jobs", params={"page_size": 101}).status_code == 422


def test_empty_database_returns_empty_page(db_session: Session, api_client: TestClient) -> None:
    response = api_client.get("/api/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["total_pages"] == 0