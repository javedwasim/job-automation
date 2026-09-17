import logging

from app.database.session import SessionLocal
from app.gmail.service import GmailIngestionService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.sync_gmail",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    time_limit=300,
)
def sync_gmail() -> dict:
    """Runs ingestion for every connected Gmail account. Scheduled by Celery
    Beat at JOB_ALERT_POLL_INTERVAL minutes (spec section 35)."""
    db = SessionLocal()
    try:
        service = GmailIngestionService(db)
        results = service.sync_all_accounts()
        summary = {
            "accounts_synced": len(results),
            "total_ingested": sum(r.messages_ingested for r in results),
            "total_failed": sum(r.messages_failed for r in results),
        }
        logger.info("gmail sync complete: %s", summary)
        return summary
    finally:
        db.close()
