"""Orchestrates a LinkedIn scrape run.

    browser -> fetch results HTML
    card_parser -> one job per CARD (never per link)
    normalize   -> canonical URL + normalized posted_at (vs scraped_at)
    deduplicate -> by LinkedIn job_id (canonical URL fallback)
    relevance   -> title first, description fallback only when needed
    date filter -> our own posted-age validation on top of LinkedIn's f_TPR
    repository  -> persist new rows, count duplicates

The browser is injected so the whole pipeline runs under unit tests with a
stub returning canned HTML - launching Chromium is never required to test
the extraction/dedup/date/persistence logic.
"""

import logging
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.config.settings import get_settings
from app.job_alerts.extraction.job_posted_date_extractor import JobPostedDateExtractor
from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer
from app.job_scraper.browser import LinkedInScraperError, LinkedInSearchBrowser
from app.job_scraper.card_parser import parse_jobs_html
from app.job_scraper.dto import ScrapedJob
from app.job_scraper.repository import ScrapedJobRepository
from app.job_scraper.schemas import LinkedInScrapeOut, LinkedInScrapeRequest, ScrapedJobOut
from app.job_scraper.search_url import build_linkedin_search_url

logger = logging.getLogger(__name__)

# Our own posted-age window per "past N" filter (hours). LinkedIn's f_TPR
# parameters are applied at the URL level too; this is the application-level
# validation on the extracted Posted value (spec: do not rely only on
# LinkedIn's search filter).
_DATE_RANGE_HOURS: dict[str, int | None] = {
    "any": None,
    "past_24_hours": 24,
    "past_week": 7 * 24,
    "past_month": 31 * 24,
}
class LinkedInScraperService:
    """Orchestrates a scrape run; safe to build per request or per task."""

    def __init__(
        self,
        db,
        browser: LinkedInSearchBrowser | None = None,
    ) -> None:
        self._repository = ScrapedJobRepository(db)
        self._browser = browser or LinkedInSearchBrowser()
        self._dates = JobPostedDateExtractor()
        self._urls = JobUrlNormalizer()
        settings = get_settings()
        self._max_cards = settings.scraper_max_cards

    def run(self, request: LinkedInScrapeRequest) -> LinkedInScrapeOut:
        try:
            return self._run(request)
        finally:
            # Release the browser's lazily-opened job-detail session (no-op
            # for stub browsers used in tests / when no detail was fetched).
            close = getattr(self._browser, "close", None)
            if close is not None:
                close()

    def _run(self, request: LinkedInScrapeRequest) -> LinkedInScrapeOut:
        scraped_at = datetime.now(UTC)
        search_url = build_linkedin_search_url(
            keyword=request.keyword,
            location=request.location,
            date_posted=request.date_posted,
            job_type=request.job_type,
            workplace=request.workplace,
        )

        html = self._browser.fetch_search_html(search_url)
        parsed = parse_jobs_html(html, scraped_at=scraped_at)

        normalized = [self._normalize(job, scraped_at=scraped_at) for job in parsed]
        deduped = self._deduplicate(normalized)
        relevant = self._filter_by_keyword_relevance(deduped, request.keyword)
        location_filtered = self._filter_by_location(relevant, request.location)
        kept, filtered = self._apply_date_filter(location_filtered, request.date_posted, scraped_at)
        kept = kept[: self._max_cards]  # hard bound against unbounded results

        saved = 0
        duplicates = 0
        errors = 0
        persisted: list[ScrapedJobOut] = []
        for job in kept:
            try:
                row, is_new = self._repository.upsert(job)
                persisted.append(ScrapedJobOut.model_validate(row))
                if is_new:
                    saved += 1
                else:
                    duplicates += 1
            except Exception:  # pragma: no cover - defensive persistence guard
                errors += 1
                logger.exception("Failed to persist scraped job %s", job.job_id)

        message = None
        if not parsed:
            message = "No job cards found on LinkedIn for these filters."

        return LinkedInScrapeOut(
            source="linkedin_scraper",
            search_url=search_url,
            total_found=len(parsed),
            saved=saved,
            duplicates=duplicates,
            filtered_by_date=len(filtered),
            errors=errors,
            jobs=persisted,
            scraped_at=scraped_at,
            message=message,
        )

        
    # --- pipeline steps (each independently testable) -------------------------

    def _normalize(self, job: ScrapedJob, *, scraped_at: datetime) -> ScrapedJob:
        url = self._urls.canonical(job.job_url, "linkedin") if job.job_url else None
        posted_at = job.posted_at
        if posted_at is None and job.posted_text:
            # Relative ages ("5 hours ago") resolve against the SCRAPER
            # timestamp, never "now" (mirrors the email pipeline's rule of
            # using the email's own received_at as the reference).
            posted_at = self._dates.extract(job.posted_text, scraped_at)
        if posted_at is not None and posted_at.tzinfo is None:
            # Interpret naive datetimes as UTC — consistent with
            # JobPostedDateExtractor._extract_explicit_date. This prevents a
            # "can't compare offset-naive and offset-aware datetimes" crash
            # in the date filter (scraped_at/cutoff are always UTC-aware).
            posted_at = posted_at.replace(tzinfo=UTC)
        return replace(job, job_url=url, posted_at=posted_at)

    @staticmethod
    def _deduplicate(jobs: list[ScrapedJob]) -> list[ScrapedJob]:
        """One record per LinkedIn job_id; jobs without a parseable id are
        deduplicated by their canonical URL instead. Order preserved."""
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
        unique: list[ScrapedJob] = []
        for job in jobs:
            if job.job_id and job.job_id in seen_ids:
                continue
            if job.job_id:
                seen_ids.add(job.job_id)
            elif job.job_url and job.job_url in seen_urls:
                continue
            elif job.job_url:
                seen_urls.add(job.job_url)
            unique.append(job)
        return unique

    @staticmethod
    def _normalize_relevance_text(value: str) -> str:
        text = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
        return " ".join(text.split())

    @classmethod
    def _matches_keyword(cls, keyword: str, text: str) -> bool:
        """Strict-but-flexible relevance check for job titles/descriptions.

        The keyword must map to actual technology terms in the target text. A
        generic role word like "developer" by itself is never enough when the
        title is a different tech stack such as "C# / Angular" or a mixed full-
        stack title listing PHP as one of several stacks.
        """
        if not (keyword or "").strip():
            return True

        normalized_keyword = cls._normalize_relevance_text(keyword)
        normalized_text = cls._normalize_relevance_text(text)
        if not normalized_keyword or not normalized_text:
            return False

        keyword_tokens = normalized_keyword.split()
        text_tokens = normalized_text.split()
        if not keyword_tokens or not text_tokens:
            return False

        role_tokens = {
            "developer",
            "engineer",
            "programmer",
            "backend",
            "frontend",
            "fullstack",
            "software",
            "architect",
            "analyst",
            "manager",
            "lead",
            "consultant",
            "devops",
            "specialist",
            "senior",
            "junior",
            "staff",
            "principal",
        }

        tech_tokens = [t for t in keyword_tokens if t not in role_tokens]
        if not tech_tokens:
            return any(token in text_tokens for token in keyword_tokens)

        role_patterns = [
            f"{tech} {role}" for tech in tech_tokens for role in (
                "developer",
                "engineer",
                "programmer",
                "backend",
                "frontend",
                "fullstack",
                "architect",
                "analyst",
                "consultant",
                "devops",
                "specialist",
                "lead",
                "manager",
            )
        ] + [
            f"{role} {tech}" for tech in tech_tokens for role in (
                "developer",
                "engineer",
                "programmer",
                "backend",
                "frontend",
                "fullstack",
                "architect",
                "analyst",
                "consultant",
                "devops",
                "specialist",
                "lead",
                "manager",
            )
        ]
        if any(pattern in normalized_text for pattern in role_patterns):
            return True

        has_full_stack_signal = "full stack" in normalized_text or "fullstack" in normalized_text
        if has_full_stack_signal:
            mixed_stack_tokens = {
                "csharp",
                "c",
                "dotnet",
                "aspnet",
                "angular",
                "react",
                "node",
                "nodejs",
                "javascript",
                "typescript",
                "python",
                "java",
                "ruby",
                "go",
                "kotlin",
                "swift",
                "php",
                "laravel",
            }
            stack_hits = {token for token in text_tokens if token in mixed_stack_tokens}
            if len(stack_hits) > 1:
                return False

        if len(tech_tokens) == 1 and tech_tokens[0] in text_tokens:
            return False

        if len(tech_tokens) > 1 and all(token in text_tokens for token in tech_tokens):
            return True

        return False

    def _filter_by_keyword_relevance(self, jobs: list[ScrapedJob], keyword: str) -> list[ScrapedJob]:
        """Title-first relevance check with description fallback only when needed."""
        if not (keyword or "").strip():
            return jobs

        kept: list[ScrapedJob] = []
        for job in jobs:
            title = job.title or ""
            if self._matches_keyword(keyword, title):
                kept.append(job)
                continue

            if not job.job_url:
                continue

            fetcher = getattr(self._browser, "fetch_job_details_html", None)
            if fetcher is None:
                continue

            try:
                detail_html = fetcher(job.job_url)
            except LinkedInScraperError:
                continue

            description = self._extract_description_text(detail_html)
            combined_text = f"{title} {description}"
            if not self._matches_keyword(keyword, combined_text):
                continue

            title_norm = self._normalize_relevance_text(title)
            title_tokens = title_norm.split()
            keyword_norm = self._normalize_relevance_text(keyword)
            keyword_tokens = keyword_norm.split()
            tech_tokens = [token for token in keyword_tokens if token not in {
                "developer",
                "engineer",
                "programmer",
                "backend",
                "frontend",
                "fullstack",
                "software",
                "architect",
                "analyst",
                "manager",
                "lead",
                "consultant",
                "devops",
                "specialist",
                "senior",
                "junior",
                "staff",
                "principal",
            }]
            description_norm = self._normalize_relevance_text(description)
            description_tokens = description_norm.split()
            has_title_tech_signal = any(token in title_tokens for token in tech_tokens)
            description_has_direct_role_match = any(
                f"{tech} {role}" in description_norm or f"{role} {tech}" in description_norm
                for tech in tech_tokens
                for role in (
                    "developer",
                    "engineer",
                    "programmer",
                    "backend",
                    "frontend",
                    "fullstack",
                    "architect",
                    "analyst",
                    "consultant",
                    "devops",
                    "specialist",
                    "lead",
                    "manager",
                )
            )
            if not has_title_tech_signal and not description_has_direct_role_match and any(
                token in description_tokens for token in tech_tokens
            ):
                continue

            kept.append(job)

        return kept

    @staticmethod
    def _normalize_location_text(value: str | None) -> str:
        text = (value or "").lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    @classmethod
    def _matches_location(cls, requested: str, job_location: str | None) -> bool:
        """Match explicit country/city filters strictly.

        If the user selected a location such as Pakistan, then a job card with no
        location text cannot be treated as a valid match. A missing location means
        the scraper has no evidence the result belongs to the requested region, so
        it must be excluded rather than silently kept.
        """
        requested_norm = cls._normalize_location_text(requested)
        if not requested_norm:
            return True

        location_text = cls._normalize_location_text(job_location)
        if not location_text:
            return False

        requested_tokens = requested_norm.split()
        location_tokens = location_text.split()

        if any(token in location_tokens for token in requested_tokens):
            return True

        if len(requested_tokens) == 1:
            return requested_tokens[0] in location_tokens

        return False

    @classmethod
    def _filter_by_location(cls, jobs: list[ScrapedJob], location: str) -> list[ScrapedJob]:
        """Keep jobs whose location matches the requested area, if any."""
        if not (location or "").strip():
            return jobs

        return [job for job in jobs if cls._matches_location(location, job.location)]

    @staticmethod
    def _extract_description_text(detail_html: str) -> str:
        try:
            from bs4 import BeautifulSoup
        except ImportError:  # pragma: no cover - bs4 is a project dependency
            return ""

        soup = BeautifulSoup(detail_html, "html.parser")
        body = soup.body or soup
        text = body.get_text(" ", strip=True)
        return text or ""

    @staticmethod
    def _apply_date_filter(
        jobs: list[ScrapedJob], date_posted: str, scraped_at: datetime
    ) -> tuple[list[ScrapedJob], list[ScrapedJob]]:
        """Applies the requested posted-age window to cards WE can validate.

        Cards whose posted value we cannot reliably parse are kept rather
        than false-excluded - LinkedIn's own f_TPR parameter already limited
        the page to that window (spec: don't invent false precision, don't
        double-penalize unknown ages).

        Internally every comparison is done in UTC-aware form. A naive
        ``posted_at`` (should not happen after ``_normalize``, but defensive)
        is interpreted as UTC per the project convention — never stripped,
        never silently compared against an aware cutoff (which would raise
        ``TypeError``).
        """
        hours = _DATE_RANGE_HOURS.get(date_posted)
        if hours is None:
            return jobs, []
        cutoff = scraped_at - timedelta(hours=hours)
        kept: list[ScrapedJob] = []
        filtered: list[ScrapedJob] = []
        for job in jobs:
            if job.posted_at is None:
                kept.append(job)
                continue
            posted_at = job.posted_at
            if posted_at.tzinfo is None:
                # Interpret naive datetimes as UTC (project convention).
                posted_at = posted_at.replace(tzinfo=UTC)
            if posted_at >= cutoff:
                kept.append(job)
            else:
                filtered.append(job)
        return kept, filtered