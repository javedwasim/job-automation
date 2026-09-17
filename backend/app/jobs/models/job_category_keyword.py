import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.jobs.models.job_category import JobCategory


class MatchType(enum.StrEnum):
    """Supported keyword matching strategies (spec section 13)."""

    EXACT = "exact"
    WORD_BOUNDARY = "word_boundary"
    SYNONYM = "synonym"
    NEGATIVE = "negative"  # presence excludes the category rather than including it


class JobCategoryKeyword(Base):
    __tablename__ = "job_category_keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_category_id: Mapped[int] = mapped_column(ForeignKey("job_categories.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(150), nullable=False)
    # values_callable makes SQLAlchemy persist/read the enum's *values*
    # ("exact", "word_boundary", ...), matching the DB schema created by
    # migration 90c0bc9bdc1a — sa.Enum("exact", "word_boundary", ...) with
    # server_default="word_boundary". Without it, SQLAlchemy defaults to
    # member *names* ("EXACT", "WORD_BOUNDARY"), which makes every lazy load
    # of category.keywords raise LookupError (silently swallowed by the
    # ingestion service -> zero jobs persisted).
    match_type: Mapped[MatchType] = mapped_column(
        Enum(
            MatchType,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=MatchType.WORD_BOUNDARY,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    category: Mapped["JobCategory"] = relationship(back_populates="keywords")
