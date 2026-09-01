import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base

# Import models so Base.metadata knows about every table before create_all.
from app.gmail.models import GmailAccount  # noqa: F401
from app.jobs.models.job import Job  # noqa: F401
from app.jobs.models.job_category import JobCategory  # noqa: F401
from app.jobs.models.job_category_keyword import JobCategoryKeyword  # noqa: F401
from app.jobs.models.job_email import JobEmail  # noqa: F401
from app.jobs.models.job_platform import JobPlatform  # noqa: F401
from app.jobs.models.processing_event import ProcessingEvent  # noqa: F401
from app.job_scraper.models import ScrapedJob  # noqa: F401
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session with the full schema applied — used for
    repository/service tests that need real unique-constraint and query
    behavior without requiring a live MySQL instance.

    Uses a single StaticPool connection with check_same_thread=False so the
    same session is usable from both the test thread and the TestClient's
    request worker thread (integration tests seed data in the main thread
    and then hit the API, which Starlette executes in another thread).
    """
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, future=True)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
