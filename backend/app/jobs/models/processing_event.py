from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ProcessingEvent(Base):
    """Audit trail for pipeline processing (spec section 23) — one row per
    notable event (parsed, classified, duplicate, failed, ...) so failures
    are diagnosable without re-reading logs."""

    __tablename__ = "processing_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_email_id: Mapped[int | None] = mapped_column(ForeignKey("job_emails.id"), nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[str | None] = mapped_column(
        "metadata", Text, nullable=True
    )  # JSON-encoded string; Python attr renamed to avoid clashing with Base.metadata

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProcessingEvent type={self.event_type} status={self.status}>"
