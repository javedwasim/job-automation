"""Pydantic request/response schemas for the LinkedIn scraper API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LinkedInScrapeRequest(BaseModel):
    """Filters for a LinkedIn job-search scrape. Value lists match the
    dashboard dropdowns; unknown values fall back to LinkedIn's defaults."""

    keyword: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    date_posted: str = Field(default="any", max_length=32)  # any|past_24_hours|past_week|past_month
    job_type: str = Field(default="any", max_length=32)  # any|full_time|part_time|contract|temporary|internship
    workplace: str = Field(default="any", max_length=32)  # any|remote|hybrid|onsite


class ScrapedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    job_id: str | None
    title: str
    company: str | None
    location: str | None
    posted_text: str | None
    posted_at: datetime | None
    job_url: str | None
    scraped_at: datetime


class LinkedInScrapeOut(BaseModel):
    """Summary of one scrape run plus the newly persisted jobs."""

    source: str
    search_url: str
    total_found: int  # job cards seen on the page
    saved: int  # newly persisted
    duplicates: int  # already known (same job_id / URL)
    filtered_by_date: int  # excluded by our own posted-age validation
    errors: int  # cards that failed to persist
    jobs: list[ScrapedJobOut]
    scraped_at: datetime
    message: str | None = None


class ScrapedJobsPageOut(BaseModel):
    items: list[ScrapedJobOut]
    total: int