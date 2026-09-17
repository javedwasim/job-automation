from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.jobs.models.enums import JobStatus
from app.jobs.models.job_category import JobCategory
from app.jobs.models.job_platform import JobPlatform

job_category_pivot = Table(
    "job_category_pivot",
    Base.metadata,
    Column("job_id", Integer, ForeignKey("jobs.id"), primary_key=True),
    Column("job_category_id", Integer, ForeignKey("job_categories.id"), primary_key=True),
    Column("confidence", Float, nullable=True),
    Column("matched_by", String(50), nullable=True),
)


class Job(Base):
    """A persisted, normalized job posting (spec section 23)."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_email_id: Mapped[int] = mapped_column(ForeignKey("job_emails.id"), nullable=False)
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("job_platforms.id"), nullable=True)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    job_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    platform_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Structured signals extracted from the alert email when the platform
    # actually states them (spec sections 2, 11-13). NULL = not stated —
    # never a guess, never copied from another job in the same digest.
    remote_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # First-class, distinct fields (spec sections 3, 23) — never conflated.
    job_posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.NEW, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    categories: Mapped[list[JobCategory]] = relationship(secondary=job_category_pivot)
    platform: Mapped[JobPlatform | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Job id={self.id} title={self.title!r} status={self.status}>"
