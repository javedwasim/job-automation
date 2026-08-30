"""Platform-independent job DTO (spec section 2/8). Every parser must produce
this same shape regardless of source platform."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NormalizedJob:
    title: str
    company: str | None
    location: str | None

    source: str  # platform slug, e.g. "linkedin", or "generic"
    platform_job_id: str | None

    job_url: str | None
    application_url: str | None

    job_posted_at: datetime | None  # NEVER fabricated — NULL if unknown (spec sections 4/7)
    received_at: datetime  # always the source email's received timestamp

    description: str | None

    source_email_id: str | None

    # Extra structured signals parsers may fill when the email actually
    # states them (spec sections 2/11-13). NULL means "not stated" — never
    # a guess, and never copied from a different job in the same digest.
    remote_type: str | None = None  # e.g. "remote", "hybrid", "onsite"
    salary: str | None = None
    employment_type: str | None = None  # e.g. "full-time", "contract"
    # True only when the email explicitly marks the job promoted/sponsored.
    # Promoted jobs are NOT rejected for being promoted — their actual
    # job_posted_at decides freshness (spec section 11).
    is_promoted: bool = False
    # Posting date as the email words it (e.g. "3 days ago"), kept for
    # observability alongside the computed job_posted_at.
    posted_date: str | None = None
