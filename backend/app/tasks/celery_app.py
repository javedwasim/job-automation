from celery import Celery

from app.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "job_automation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.example_task", "app.tasks.gmail_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "sync-gmail-on-interval": {
        "task": "app.tasks.sync_gmail",
        "schedule": settings.job_alert_poll_interval * 60,  # minutes -> seconds
    },
}
