from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class JobPlatform(Base):
    """A job-alert source (LinkedIn, Indeed, Wellfound, ...). This is a
    database-driven registry, not a hard-coded list — new platforms are
    added as rows, and later a new parser module (spec section 43), never
    by editing the ingestion pipeline.
    """

    __tablename__ = "job_platforms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    # Dotted path to the parser class, e.g. "app.job_alerts.parsers.linkedin.LinkedInParser".
    # Left nullable in Phase 1 since parsers don't exist until Phase 2.
    parser: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<JobPlatform slug={self.slug} domain={self.domain} enabled={self.enabled}>"
