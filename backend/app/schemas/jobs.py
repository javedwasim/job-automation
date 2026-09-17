from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str | None
    location: str | None
    source: str | None = None  # platform slug, filled in by the route
    job_url: str | None
    application_url: str | None
    categories: list[str]
    job_posted_at: datetime | None
    received_at: datetime
    status: str
    # Structured signals the platform actually stated (spec sections 2,
    # 11-13) — exposed so the dashboard can render them; NULL = not stated.
    remote_type: str | None = None
    salary: str | None = None
    employment_type: str | None = None


class JobsPageOut(BaseModel):
    """Paginated jobs listing — one page of rows plus the metadata the
    dashboard needs to render pager controls."""

    items: list[JobOut]
    total: int
    page: int
    page_size: int
    total_pages: int
