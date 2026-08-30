"""
GmailIngestionService — the Phase 1 slice of the canonical pipeline (spec
section 37):

    Sync Gmail -> find alerts in lookback window -> check processed
    -> normalize email -> (basic) detect platform -> save job_email

Parsing the email into an actual job (title/company/URL/...) is Phase 2+;
this service's job ends at a persisted, deduplicated `JobEmail` row.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.gmail.client import GmailClient, build_lookback_query
from app.gmail.models import GmailAccount
from app.gmail.normalizer import normalize_email
from app.gmail.oauth import refresh_access_token
from app.jobs.models.job_email import JobEmail
from app.jobs.services.job_processing_service import JobProcessingService
from app.repositories.gmail_account_repository import GmailAccountRepository
from app.repositories.job_email_repository import JobEmailRepository
from app.repositories.job_platform_repository import JobPlatformRepository

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    account_email: str
    messages_found: int
    messages_ingested: int
    messages_skipped_duplicate: int
    messages_failed: int


@dataclass
class BackfillResult:
    account_email: str
    candidates: int
    processed: int
    failed: int


class GmailIngestionService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._accounts = GmailAccountRepository(db)
        self._job_emails = JobEmailRepository(db)
        self._platforms = JobPlatformRepository(db)
        self._job_processing = JobProcessingService(db)

    def _get_valid_access_token(self, account: GmailAccount) -> str:
        """Returns a usable access token, refreshing it first if expired."""
        now = datetime.now(UTC)
        expires_at = account.token_expires_at
        if expires_at.tzinfo is None:
            # Some DB drivers (SQLite, and MySQL DATETIME columns without
            # explicit UTC handling) drop tzinfo on read; treat naive values
            # as UTC since that's what we always write.
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at > now:
            return self._accounts.decrypt_access_token(account)

        refresh_token = self._accounts.decrypt_refresh_token(account)
        new_access_token, new_expiry = refresh_access_token(refresh_token)
        self._accounts.update_access_token(account, new_access_token, new_expiry)
        return new_access_token

    def _is_excluded_sender(self, sender: str) -> bool:
        """True when the sender matches one of the configured excluded
        domains (e.g. glassdoor.com) — those emails are recorded for dedup
        but never parsed into jobs."""
        sender_lower = sender.lower()
        return any(domain in sender_lower for domain in self._settings.job_alert_excluded_domains)

    def sync_account(self, account: GmailAccount) -> SyncResult:
        access_token = self._get_valid_access_token(account)
        client = GmailClient(access_token)

        # No sender-domain whitelist: every job-alert email in the lookback
        # window is fetched (only Gmail's own category plus the excluded
        # domains scope the search), so alerts from platforms we haven't
        # configured yet are found too.
        query = build_lookback_query(
            self._settings.job_alert_lookback_hours,
            excluded_domains=self._settings.job_alert_excluded_domains,
            gmail_category=self._settings.job_alert_gmail_category,
        )

        message_ids = client.search_message_ids(query)

        # Labeling is a nice-to-have (lets you see processed emails in the
        # Gmail UI) but requires a broader scope than gmail.readonly. Our
        # real dedup mechanism is the DB unique constraint below, so a
        # missing/insufficient scope for labeling must never fail the sync.
        label_id: str | None
        try:
            label_id = client.ensure_label(self._settings.job_automation_processed_label)
        except Exception:  # noqa: BLE001
            label_id = None

        ingested = 0
        skipped_duplicate = 0
        failed = 0

        for message_id in message_ids:
            if self._job_emails.is_already_processed(account.id, message_id):
                skipped_duplicate += 1
                continue

            try:
                self._ingest_one(client, account, message_id, label_id)
                ingested += 1
            except Exception:  # noqa: BLE001 - one bad email must not abort the whole sync
                failed += 1

        return SyncResult(
            account_email=account.email,
            messages_found=len(message_ids),
            messages_ingested=ingested,
            messages_skipped_duplicate=skipped_duplicate,
            messages_failed=failed,
        )

    def _ingest_one(
        self, client: GmailClient, account: GmailAccount, message_id: str, label_id: str | None
    ) -> JobEmail:
        raw_message = client.get_message(message_id)
        normalized = normalize_email(raw_message)

        platform = self._platforms.detect_by_sender(normalized.sender)
        source = platform.slug if platform else None

        job_email = self._job_emails.create_from_normalized_email(
            gmail_account_id=account.id, email=normalized, source=source
        )

        # Run parse -> classify -> dedupe -> persist immediately, while we
        # still have the normalized email in hand — job_emails intentionally
        # doesn't store the body (spec section 40), so this is the only
        # point at which the full pipeline can run for this message.
        #
        # Excluded sources (e.g. Glassdoor) are still recorded so dedup
        # works, but never parsed — they can never reach the dashboard even
        # if the Gmail query's -from: negations miss them.
        if not self._is_excluded_sender(normalized.sender):
            try:
                self._job_processing.process_email(job_email_id=job_email.id, email=normalized)
            except Exception:  # noqa: BLE001 - a parsing failure must not lose the raw email record
                # Logged, never silently swallowed: a systematic pipeline failure
                # (bad enum mapping, missing table, ...) must be visible in the
                # server logs instead of "successful" syncs with zero jobs.
                logger.exception("Failed to process job_email_id=%s", job_email.id)

        if label_id is not None:
            try:
                client.apply_label(message_id, label_id)
            except Exception:  # noqa: BLE001 - labeling is best-effort, never blocks persistence
                pass

        self._job_emails.mark_processed(job_email)
        return job_email

    def sync_all_accounts(self) -> list[SyncResult]:
        return [self.sync_account(account) for account in self._accounts.list_all()]

    def backfill_jobs(self, account: GmailAccount) -> BackfillResult:
        """Re-fetches and reprocesses job_emails that were ingested before
        the parse/classify/persist pipeline was wired into sync_account
        (or that failed processing at the time). Since job_emails doesn't
        store the email body, this re-fetches each message from Gmail.

        One-shot per email: every attempt leaves a trace (a Job row or a
        backfill_attempted processing event), so repeated calls only ever
        process emails the pipeline has never seen an outcome for."""
        access_token = self._get_valid_access_token(account)
        client = GmailClient(access_token)

        pending = self._job_emails.list_without_job(account.id)
        processed = 0
        failed = 0

        for job_email in pending:
            try:
                raw_message = client.get_message(job_email.gmail_message_id)
                normalized = normalize_email(raw_message)
                if self._is_excluded_sender(normalized.sender):
                    # Excluded sources (e.g. Glassdoor) are never parsed into
                    # jobs; record the attempt so they aren't re-downloaded on
                    # every backfill either.
                    self._job_emails.record_processing_event(
                        job_email_id=job_email.id,
                        event_type="backfill_attempted",
                        status="skipped",
                        message="Excluded sender — never parsed into jobs",
                    )
                    processed += 1
                    continue
                jobs = self._job_processing.process_email(
                    job_email_id=job_email.id, email=normalized
                )
                processed += 1
                if not jobs:
                    # Zero jobs parsed (newsletter, application confirmation,
                    # account notice, ...): record the attempt so this email
                    # isn't re-fetched on every future backfill.
                    self._job_emails.record_processing_event(
                        job_email_id=job_email.id,
                        event_type="backfill_attempted",
                        status="success",
                        message="No job parsed from this email",
                    )
            except Exception:  # noqa: BLE001 - one bad email must not abort the whole backfill
                logger.exception("Backfill failed for job_email_id=%s", job_email.id)
                failed += 1
                self._job_emails.record_processing_event(
                    job_email_id=job_email.id,
                    event_type="backfill_attempted",
                    status="failed",
                    message="Processing failed during backfill (see server log)",
                )

        return BackfillResult(
            account_email=account.email, candidates=len(pending), processed=processed, failed=failed
        )

    def backfill_all_accounts(self) -> list[BackfillResult]:
        return [self.backfill_jobs(account) for account in self._accounts.list_all()]
