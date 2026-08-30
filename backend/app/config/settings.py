"""
Application configuration.

Everything here is environment-driven — no business rules or platform /
category values are hard-coded in controllers or services. See spec
section 41 ("Configuration").
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "job-automation"
    app_env: str = Field(default="local")
    debug: bool = Field(default=True)
    secret_key: str = Field(default="change-me-in-env")

    # --- Database ---
    database_url: str = Field(
        default="mysql+pymysql://job_automation:job_automation@localhost:3306/job_automation"
    )

    # --- Redis / Celery ---
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")

    # --- Gmail ingestion (spec section 20) ---
    job_alert_lookback_hours: int = Field(default=24)
    job_alert_poll_interval: int = Field(default=5)  # minutes
    job_automation_processed_label: str = Field(default="JOB_AUTOMATION_PROCESSED")
    # Gmail category restriction for the sync query. Default is EMPTY
    # (disabled): job alerts land in different Gmail categories per platform
    # (LinkedIn -> Updates, Indeed -> Promotions), so the search must scan
    # them all. Set e.g. "updates" in .env to narrow it deliberately.
    job_alert_gmail_category: str = Field(default="")
    # Senders whose emails must never become jobs — excluded in the Gmail
    # search itself (-from:) and re-checked at ingestion time. Empty by
    # default: every job-alert sender (LinkedIn, Indeed, Glassdoor, ...) is
    # ingested; add e.g. "glassdoor.com" in .env to block one deliberately.
    job_alert_excluded_domains: list[str] = Field(default=[])

    # --- Gmail OAuth (wired up in Phase 1) ---
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(default="http://localhost:8000/api/gmail/oauth/callback")
    frontend_url: str = Field(default="http://localhost:5173")

    # --- Classification (spec section 15) ---
    job_classifier: str = Field(default="rules")  # rules | ai | hybrid

    # --- URL / redirect resolution (spec section 17) ---
    redirect_max_hops: int = Field(default=5)
    redirect_timeout_seconds: float = Field(default=5.0)

    # --- Freshness (spec section 6) ---
    # Jobs older than this — measured on job_posted_at, never received_at —
    # are dropped by the centralized freshness policy before persistence.
    max_job_age_hours: int = Field(default=24)
    # --- Unknown posting date (spec section 7) ---
    # "keep": job_posted_at stays NULL when no reliable posting date exists
    #         (never fabricated, never replaced by received_at) and the job
    #         is retained, exempt from freshness filtering.
    # "reject": unknown-date job candidates are dropped instead.
    unknown_date_policy: str = Field(default="keep")

    # --- Export ---
    csv_export_format: str = Field(default="csv")


@lru_cache
def get_settings() -> Settings:
    return Settings()
