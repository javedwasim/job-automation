from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.jobs.models.enums import JobEmailStatus


class JobEmail(Base):
    """A single Gmail message identified as a (candidate) job alert.

    This is the record that makes processed-email detection possible: the
    unique constraint on (gmail_account_id, gmail_message_id) is what lets
    ingestion say "if message already processed: skip" (spec section 22).
    """

    __tablename__ = "job_emails"
    __table_args__ = (
        UniqueConstraint(
            "gmail_account_id", "gmail_message_id", name="uq_job_emails_account_message"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_account_id: Mapped[int] = mapped_column(
        ForeignKey("gmail_accounts.id"), nullable=False, index=True
    )
    gmail_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Detected platform slug (e.g. "linkedin"), or "generic" if none matched.
    # Nullable until platform detection runs (Phase 2) — Phase 1 only ingests.
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)  # RFC 5322 header line limit
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[JobEmailStatus] = mapped_column(
        Enum(JobEmailStatus), nullable=False, default=JobEmailStatus.NEW, index=True
    )

    # SHA-256 of the raw normalized email content — cheap integrity/debug aid,
    # not used for job-level deduplication (that's JobFingerprintService, Phase 5).
    raw_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<JobEmail id={self.id} gmail_message_id={self.gmail_message_id} status={self.status}>"
        )
