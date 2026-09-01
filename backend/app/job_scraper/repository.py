"""Persistence for scraped LinkedIn jobs — a repository independent of the
Gmail-derived JobRepository (spec: keep the scraper logically independent)."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.job_scraper.dto import ScrapedJob
from app.job_scraper.models import ScrapedJob as ScrapedJobRow


class ScrapedJobRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def find_existing(self, *, job_id: str | None, job_url: str | None) -> ScrapedJobRow | None:
        # job_id is the strongest dedup key; canonical URL is the fallback
        # used when a job_id could not be extracted. NULL id/url never match.
        if job_id:
            row = self._db.scalar(select(ScrapedJobRow).where(ScrapedJobRow.job_id == job_id))
            if row is not None:
                return row
        if job_url:
            row = self._db.scalar(select(ScrapedJobRow).where(ScrapedJobRow.job_url == job_url))
            if row is not None:
                return row
        return None

    def upsert(self, job: ScrapedJob) -> tuple[ScrapedJobRow, bool]:
        """Persists a new scraped job, or returns the existing row for the
        same job_id / canonical URL. Returns (row, is_new)."""
        existing = self.find_existing(job_id=job.job_id, job_url=job.job_url)
        if existing is not None:
            return existing, False
        now = datetime.now(UTC)
        row = ScrapedJobRow(
            source="linkedin_scraper",
            job_id=job.job_id,
            job_url=job.job_url,
            title=job.title,
            company=job.company,
            location=job.location,
            posted_text=job.posted_text,
            posted_at=job.posted_at,
            scraped_at=job.scraped_at,
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row, True

    def list_recent(self, limit: int = 50) -> list[ScrapedJobRow]:
        return list(
            self._db.scalars(
                select(ScrapedJobRow)
                .order_by(ScrapedJobRow.scraped_at.desc(), ScrapedJobRow.id.desc())
                .limit(limit)
            )
        )

    def count(self) -> int:
        return self._db.scalar(select(func.count()).select_from(ScrapedJobRow)) or 0