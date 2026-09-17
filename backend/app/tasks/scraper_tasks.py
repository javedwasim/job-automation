"""Celery task for the LinkedIn scraper — mirrors the sync API endpoint so
the same pipeline can run on a schedule without a request in flight."""

import logging

from app.database.session import SessionLocal
from app.job_scraper.schemas import LinkedInScrapeRequest
from app.job_scraper.service import LinkedInScraperService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.scrape_linkedin",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    time_limit=300,
)
def scrape_linkedin(
    *,
    keyword: str = "",
    location: str = "",
    date_posted: str = "any",
    job_type: str = "any",
    workplace: str = "any",
) -> dict:
    """Scrapes LinkedIn with the given filters and persists the results.
    Uses the same service the POST /api/scraper/linkedin/run endpoint
    calls, so behaviour is identical whether triggered from the dashboard
    or from a scheduled task."""
    db = SessionLocal()
    try:
        result = LinkedInScraperService(db).run(
            LinkedInScrapeRequest(
                keyword=keyword,
                location=location,
                date_posted=date_posted,
                job_type=job_type,
                workplace=workplace,
            )
        )
        summary = {
            "source": result.source,
            "total_found": result.total_found,
            "saved": result.saved,
            "duplicates": result.duplicates,
            "filtered_by_date": result.filtered_by_date,
            "errors": result.errors,
        }
        logger.info("linkedin scrape complete: %s", summary)
        return summary
    finally:
        db.close()