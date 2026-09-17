from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.ping")
def ping() -> str:
    """Trivial task used only to verify the worker is alive in Phase 0."""
    return "pong"
