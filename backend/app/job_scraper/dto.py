"""Data types for the independent LinkedIn job scraper.

A scraped job corresponds to EXACTLY ONE LinkedIn job card. A card may
contain many anchor elements (company logo, job title, apply button,
tracking links) — all of them describe the same job and collapse into a
single `ScrapedJob`. The number of links never determines the number of
jobs (one card = one job).
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ScrapedJob:
    """One job extracted from one LinkedIn job card."""

    title: str
    company: str | None
    location: str | None
    # The posting age exactly as LinkedIn displayed it ("5 hours ago",
    # "1 week ago") — preserved for traceability.
    posted_text: str | None
    job_url: str | None  # exactly one, canonicalized
    job_id: str | None  # LinkedIn job ID — primary dedup key
    scraped_at: datetime  # scraper trace timestamp
    posted_at: datetime | None = None  # normalized, when reliable