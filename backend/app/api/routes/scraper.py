"""HTTP endpoints for the independent LinkedIn job scraper.

The run endpoint executes a scrape synchronously (browser automation runs
for the duration of the request) so the dashboard receives a complete
result set; the Celery task in app.tasks.scraper_tasks mirrors this for
scheduled background runs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.job_scraper.browser import LinkedInScraperError
from app.job_scraper.repository import ScrapedJobRepository
from app.job_scraper.schemas import (
    LinkedInScrapeOut,
    LinkedInScrapeRequest,
    ScrapedJobOut,
    ScrapedJobsPageOut,
)
from app.job_scraper.service import LinkedInScraperService

router = APIRouter(prefix="/scraper", tags=["scraper"])

_MAX_LIST_LIMIT = 200


def _build_service(db: Session) -> LinkedInScraperService:
    return LinkedInScraperService(db)


@router.post("/linkedin/run", response_model=LinkedInScrapeOut)
def run_linkedin_scrape(
    payload: LinkedInScrapeRequest,
    db: Session = Depends(get_db),
) -> LinkedInScrapeOut:
    """Scrapes LinkedIn job-search results for the given filters: opens the
    search URL in a headless browser, extracts ONE job per job card,
    deduplicates by LinkedIn job ID, validates the posted age, and persists
    the results. Browser/flake failures become a clean 502 detail."""
    try:
        return _build_service(db).run(payload)
    except LinkedInScraperError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/jobs", response_model=ScrapedJobsPageOut)
def list_scraped_jobs(
    limit: int = Query(default=50, ge=1, le=_MAX_LIST_LIMIT),
    db: Session = Depends(get_db),
) -> ScrapedJobsPageOut:
    """Most recent scraped jobs, newest first — the scraper section of the
    dashboard. These rows are marked source='linkedin_scraper' and live in
    their own table, so they never mix with Gmail-derived jobs."""
    repository = ScrapedJobRepository(db)
    rows = repository.list_recent(limit=limit)
    return ScrapedJobsPageOut(
        items=[ScrapedJobOut.model_validate(row) for row in rows],
        total=repository.count(),
    )