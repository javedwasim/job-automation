"""ORM model for the independent LinkedIn scraper (a NEW job-discovery source,
separate from Gmail-derived jobs — never mixed into their tables)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ScrapedJob(Base):
    """A job discovered by the LinkedIn scraper.

    Kept in its own `scraped_jobs` table so standalone scraped records can
    never disturb or overwrite Gmail-derived jobs. `source` marks them as
    "linkedin_scraper" so the dashboard can distinguish the two streams.
    """

    __tablename__ = "scraped_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="linkedin_scraper", index=True)
    # LinkedIn job ID (from /jobs/view/<id> or the card's data attribute).
    # Unique when present — the primary dedup key. NULL for unparseable cards.
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    # Canonical job URL (tracking stripped, host normalized) — also unique so
    # two jobs that happen to share an ID-less URL still deduplicate.
    job_url: Mapped[str | None] = mapped_column(String(2048), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The posting age as LinkedIn displayed it ("5 hours ago", "1 week ago").
    posted_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Normalized posting timestamp, when reliable.
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the scrape ran — the trace reference for relative posted dates.
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)