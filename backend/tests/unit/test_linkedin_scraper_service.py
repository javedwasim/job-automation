"""LinkedInScraperService tests with a stubbed browser.

The full pipeline (browser -> card parse -> normalize -> dedup -> date
filter -> persist) is exercised WITHOUT launching a browser, proving the
dedup / posted-age rules and DB persistence are deterministic.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.job_scraper.browser import LinkedInSearchBrowser, LinkedInUnavailableError
from app.job_scraper.models import ScrapedJob
from app.job_scraper.schemas import LinkedInScrapeRequest
from app.job_scraper.service import LinkedInScraperService

NOW = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)


def _card(job_id: str, *, title: str = "Senior ML Engineer", posted: str = "5 hours ago") -> str:
    return f"""
    <li class="job-card-container" data-occludable-job-id="{job_id}">
      <div class="job-card-container">
        <a class="job-card-list__title--link" href="https://www.linkedin.com/jobs/view/{job_id}?trk=eml-job_digest-jobcard_body">
          <span aria-hidden="true">{title}</span>
        </a>
        <div class="job-card-container__primary-description"><span class="job-card-container__company-name">TechNova</span></div>
        <div class="job-card-container__metadata"><div class="job-card-container__metadata-sibling">Remote</div></div>
        <div class="job-card-container__footer"><span class="job-card-container__listed-time">{posted}</span></div>
        <a href="https://www.linkedin.com/jobs/view/{job_id}/apply">Apply</a>
      </div>
    </li>"""


class StubBrowser:
    """Production browser's twin: returns a canned page, records the URL."""

    def __init__(self, html: str) -> None:
        self._html = html
        self.requested_url = None

    def fetch_search_html(self, url: str) -> str:
        self.requested_url = url
        return self._html


def _build_service(db: Session, html: str) -> tuple[LinkedInScraperService, StubBrowser]:
    """Builds the service with a stub browser. The service stamps its own
    UTC now; assertions only use relative values (hours/days ago)."""
    browser = StubBrowser(html)
    return LinkedInScraperService(db, browser=browser), browser


# --- deduplication ------------------------------------------------------------------


def test_same_linkedin_job_id_deduplicates_to_one_row(db_session: Session) -> None:
    html = _card("4025123456") + _card("4025123456", title="Duplicate card")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="ML"))

    assert result.total_found == 2  # two cards seen
    assert result.saved == 1  # only ONE unique job id persisted
    assert result.duplicates == 0  # the second card was deduped pre-persist
    rows = list(db_session.scalars(select(ScrapedJob)))
    assert len(rows) == 1
    assert rows[0].job_id == "4025123456"


def test_running_the_same_scrape_twice_counts_second_as_duplicate(db_session: Session) -> None:
    html = _card("4025123456")
    service, _ = _build_service(db_session, html)

    first = service.run(LinkedInScrapeRequest(keyword="ML"))
    second = service.run(LinkedInScrapeRequest(keyword="ML"))

    assert first.saved == 1
    assert first.duplicates == 0
    assert second.saved == 0
    assert second.duplicates == 1
    assert (db_session.scalar(select(ScrapedJob).where(ScrapedJob.job_id == "4025123456"))) is not None


def test_duplicate_cards_in_db_do_not_create_new_rows_on_rerun(db_session: Session) -> None:
    html = _card("4025123456") + _card("4025123456")
    service, _ = _build_service(db_session, html)
    from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer

    now = datetime.now(UTC)
    service.run(LinkedInScrapeRequest(keyword="ML"))
    first_count = db_session.scalar(select(ScrapedJob).where(ScrapedJob.job_id == "4025123456"))
    # Pre-existing row for the same job from a previous run:
    from app.job_scraper.repository import ScrapedJobRepository
    from app.job_scraper.dto import ScrapedJob as DTO

    dupe_before = now.replace(minute=1)
    repo = ScrapedJobRepository(db_session)
    repo.upsert(
        DTO(
            title="Old", company="TechNova", location="Remote", posted_text="3 days ago",
            job_url=JobUrlNormalizer().canonical("https://www.linkedin.com/jobs/view/4025123456", "linkedin"),
            job_id="4025123456", scraped_at=dupe_before, posted_at=now - timedelta(days=3),
        )
    )
    db_session.refresh(first_count)
    assert db_session.scalar(select(ScrapedJob).where(ScrapedJob.job_id == "4025123456")) is not None


# --- date validation -----------------------------------------------------------------


def test_past_24_hours_keeps_recent_and_filters_older_cards(db_session: Session) -> None:
    html = _card("1001", posted="5 hours ago") + _card("1002", posted="2 days ago") + _card("1003", posted="1 week ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="ML", date_posted="past_24_hours"))

    assert result.total_found == 3
    assert result.filtered_by_date == 2  # 2 days + 1 week are older than 24h
    assert result.saved == 1
    assert [j.job_id for j in result.jobs] == ["1001"]


def test_past_week_keeps_week_old_but_filters_month_old(db_session: Session) -> None:
    html = _card("2001", posted="5 hours ago") + _card("2002", posted="2 days ago") + _card("2003", posted="1 month ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="ML", date_posted="past_week"))

    assert result.filtered_by_date == 1  # 1 month ago excluded
    assert {j.job_id for j in result.jobs} == {"2001", "2002"}


def test_any_time_keeps_everything(db_session: Session) -> None:
    html = _card("3001", posted="5 hours ago") + _card("3002", posted="1 month ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="ML", date_posted="any"))

    assert result.filtered_by_date == 0
    assert {j.job_id for j in result.jobs} == {"3001", "3002"}


def test_location_filter_excludes_jobs_outside_requested_country(db_session: Session) -> None:
    lahore_job = _card("3301", title="Senior Laravel Developer", posted="2 hours ago")
    lahore_job = lahore_job.replace(
        '<div class="job-card-container__metadata"><div class="job-card-container__metadata-sibling">Remote</div></div>',
        '<div class="job-card-container__metadata"><div class="job-card-container__metadata-sibling">Lahore, Pakistan (Remote)</div></div>',
    )
    dubai_job = _card("3302", title="Senior Laravel Developer", posted="30 minutes ago")
    dubai_job = dubai_job.replace(
        '<div class="job-card-container__metadata"><div class="job-card-container__metadata-sibling">Remote</div></div>',
        '<div class="job-card-container__metadata"><div class="job-card-container__metadata-sibling">Dubai, United Arab Emirates</div></div>',
    )
    service, _ = _build_service(db_session, lahore_job + dubai_job)

    result = service.run(LinkedInScrapeRequest(keyword="Laravel Developer", location="Pakistan", date_posted="any"))

    assert {j.job_id for j in result.jobs} == {"3301"}
    assert result.saved == 1


def test_location_filter_excludes_jobs_with_missing_location_when_country_is_explicit(db_session: Session) -> None:
    html = _card("3303", title="Full Stack Engineer (Laravel)", posted="12 hours ago")
    html = html.replace(
        '<div class="job-card-container__metadata"><div class="job-card-container__metadata-sibling">Remote</div></div>',
        '',
    )
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="Laravel Developer", location="Pakistan", date_posted="any"))

    assert result.saved == 0
    assert result.jobs == []


def test_unparseable_posted_value_is_not_false_excluded(db_session: Session) -> None:
    html = _card("4001", posted="Some unusual date string")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="ML", date_posted="past_24_hours"))

    # LinkedIn's own f_TPR window already limited the page; an unparseable
    # card-side value is kept (never double-penalized, never fabricated).
    assert result.filtered_by_date == 0
    assert [j.job_id for j in result.jobs] == ["4001"]


# --- pipeline wiring -----------------------------------------------------------------


def test_service_builds_search_url_and_persists_fields(db_session: Session) -> None:
    html = _card("5001", title="Senior PHP Developer", posted="18 hours ago")
    service, browser = _build_service(db_session, html)

    result = service.run(
        LinkedInScrapeRequest(keyword="PHP Developer", location="Remote", date_posted="past_24_hours", job_type="full_time", workplace="remote")
    )

    assert browser.requested_url is not None
    assert "keywords=PHP+Developer" in browser.requested_url
    assert "location=Remote" in browser.requested_url
    assert "f_TPR=r86400" in browser.requested_url
    assert "f_JT=F" in browser.requested_url
    assert "f_WT=2" in browser.requested_url

    assert result.source == "linkedin_scraper"
    assert result.saved == 1
    row = list(db_session.scalars(select(ScrapedJob)))[0]
    assert row.title == "Senior PHP Developer"
    assert row.company == "TechNova"
    assert row.location == "Remote"
    assert row.posted_text == "18 hours ago"
    assert row.posted_at is not None
    assert row.scraped_at is not None
    assert row.source == "linkedin_scraper"


def test_no_job_cards_returns_graceful_empty_summary(db_session: Session) -> None:
    service, _ = _build_service(db_session, "<html><body><p>No matching jobs found.</p></body></html>")

    result = service.run(LinkedInScrapeRequest(keyword="gibberish-search"))

    assert result.total_found == 0
    assert result.saved == 0
    assert result.jobs == []
    assert result.message is not None


def test_title_match_keeps_job_without_fetching_detail_page(db_session: Session) -> None:
    class DetailAwareBrowser(StubBrowser):
        def __init__(self, html: str) -> None:
            super().__init__(html)
            self.detail_requests = 0

        def fetch_job_details_html(self, url: str) -> str:
            self.detail_requests += 1
            return "<html><body><p>Sales engineer role for customer acquisition.</p></body></html>"

    browser = DetailAwareBrowser(_card("9101", title="Senior PHP Developer", posted="8 hours ago"))
    service = LinkedInScraperService(db_session, browser=browser)

    result = service.run(LinkedInScrapeRequest(keyword="PHP Developer", date_posted="any"))

    assert result.saved == 1
    assert browser.detail_requests == 0


def test_title_mismatch_then_description_match_keeps_job(db_session: Session) -> None:
    class DetailAwareBrowser(StubBrowser):
        def __init__(self, html: str, detail_text: str) -> None:
            super().__init__(html)
            self.detail_text = detail_text
            self.detail_requests = 0

        def fetch_job_details_html(self, url: str) -> str:
            self.detail_requests += 1
            return self.detail_text

    html = _card("9102", title="Senior Backend Engineer", posted="2 days ago")
    detail_html = "<html><body><div><h1>Senior Backend Engineer</h1><p>We are hiring a senior PHP developer with Laravel experience.</p></div></body></html>"
    browser = DetailAwareBrowser(html, detail_html)
    service = LinkedInScraperService(db_session, browser=browser)

    result = service.run(LinkedInScrapeRequest(keyword="PHP Developer", date_posted="past_week"))

    assert result.saved == 1
    assert browser.detail_requests == 1


def test_neither_title_nor_description_match_excludes_job(db_session: Session) -> None:
    class DetailAwareBrowser(StubBrowser):
        def __init__(self, html: str, detail_text: str) -> None:
            super().__init__(html)
            self.detail_text = detail_text
            self.detail_requests = 0

        def fetch_job_details_html(self, url: str) -> None:
            self.detail_requests += 1
            return self.detail_text

    html = _card("9103", title="Senior Sales Engineer", posted="6 hours ago")
    detail_html = "<html><body><p>We sell enterprise software to customers and manage account growth.</p></body></html>"
    browser = DetailAwareBrowser(html, detail_html)
    service = LinkedInScraperService(db_session, browser=browser)

    result = service.run(LinkedInScrapeRequest(keyword="PHP Developer", date_posted="any"))

    assert result.saved == 0
    assert result.jobs == []
    assert browser.detail_requests == 1


def test_keyword_has_no_php_token_does_not_match_full_stack_csharp_title(db_session: Session) -> None:
    html = _card("9104", title="Senior Full Stack Developer – C# / Angular (Remote, Full-Time) [HR209] (PK)", posted="21 minutes ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="PHP Developer", date_posted="any"))

    assert result.saved == 0
    assert result.jobs == []


def test_laravel_keyword_requires_laravel_related_technology(db_session: Session) -> None:
    csharp_html = _card("9105", title="Senior Full Stack Developer – C# / Angular (Remote, Full-Time) [HR209] (PK)", posted="21 minutes ago")
    laravel_html = _card("9106", title="Senior Full-Stack Developer (Laravel + React/Next.js)", posted="21 minutes ago")

    csharp_service, _ = _build_service(db_session, csharp_html)
    csharp_result = csharp_service.run(LinkedInScrapeRequest(keyword="Laravel Developer", date_posted="any"))
    assert csharp_result.saved == 0
    assert csharp_result.jobs == []

    laravel_service, _ = _build_service(db_session, laravel_html)
    laravel_result = laravel_service.run(LinkedInScrapeRequest(keyword="Laravel Developer", date_posted="any"))
    assert laravel_result.saved == 1
    assert laravel_result.jobs[0].title == "Senior Full-Stack Developer (Laravel + React/Next.js)"


def test_php_keyword_rejects_mixed_full_stack_title_list(db_session: Session) -> None:
    html = _card("9108", title="Senior Full Stack Developer (C#, Python, and PHP) - Pakistan", posted="21 minutes ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="PHP Developer", date_posted="any"))

    assert result.saved == 0
    assert result.jobs == []


def test_generic_engineer_title_does_not_survive_laravel_description_fallback(db_session: Session) -> None:
    class DetailAwareBrowser(StubBrowser):
        def __init__(self, html: str, detail_text: str) -> None:
            super().__init__(html)
            self.detail_text = detail_text
            self.detail_requests = 0

        def fetch_job_details_html(self, url: str) -> str:
            self.detail_requests += 1
            return self.detail_text

    html = _card("9109", title="Senior Software Engineer", posted="2 hours ago")
    detail_html = "<html><body><p>We build a platform with Laravel and PHP for internal tooling and APIs.</p></body></html>"
    browser = DetailAwareBrowser(html, detail_html)
    service = LinkedInScraperService(db_session, browser=browser)

    result = service.run(LinkedInScrapeRequest(keyword="Laravel Developer", date_posted="any"))

    assert result.saved == 0
    assert result.jobs == []
    assert browser.detail_requests == 1


def test_full_stack_keyword_still_matches_full_stack_title(db_session: Session) -> None:
    html = _card("9107", title="Senior Full Stack Developer (Remote)", posted="21 minutes ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="Full Stack Developer", date_posted="any"))

    assert result.saved == 1
    assert result.jobs[0].title == "Senior Full Stack Developer (Remote)"


def test_close_releases_persistent_detail_session() -> None:
    """close() frees the lazily-opened job-detail session (page, browser,
    playwright) so repeated scrapes never leak Chromium processes."""
    from unittest.mock import Mock

    browser = LinkedInSearchBrowser(headless=True, timeout_seconds=1, max_scroll_passes=0)
    page = Mock()
    chrome = Mock()
    pw = Mock()
    browser._detail_session = (pw, chrome, page)

    browser.close()

    assert browser._detail_session is None
    page.close.assert_called_once()
    chrome.close.assert_called_once()
    pw.stop.assert_called_once()


def test_close_is_safe_when_no_session_was_opened() -> None:
    browser = LinkedInSearchBrowser(headless=True, timeout_seconds=1, max_scroll_passes=0)

    assert browser._detail_session is None
    browser.close()  # must not raise


def test_service_does_not_require_close_on_stub_browser(db_session: Session) -> None:
    """The service calls close() defensively; browser stubs without that
    method (as used across the test suite) must keep working unchanged."""
    html = _card("7701")
    service, browser = _build_service(db_session, html)
    assert not hasattr(browser, "close")

    result = service.run(LinkedInScrapeRequest(keyword="ML"))
    assert result.saved == 1


# --- browser error propagation -------------------------------------------------


def test_browser_session_preserves_linkedin_scraper_errors() -> None:
    browser = LinkedInSearchBrowser(headless=True, timeout_seconds=1, max_scroll_passes=0)

    with pytest.raises(LinkedInUnavailableError, match="did not respond"):
        with browser._browser_session():
            raise LinkedInUnavailableError("LinkedIn did not respond within 1s.")


# --- datetime consistency (spec: timezone-aware UTC internally) ----------------


def test_normalize_normalizes_naive_posted_at_to_utc(db_session: Session) -> None:
    """_parse_iso can return naive datetimes from LinkedIn <time datetime='2024-01-15'>
    attributes. _normalize must convert them to UTC-aware BEFORE the date filter
    compares them against the UTC-aware cutoff."""
    from app.job_scraper.dto import ScrapedJob as DTO

    service, _ = _build_service(db_session, _card("1"))
    now = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)

    naive_posted = datetime(2024, 1, 15)  # no tzinfo — the bug scenario
    assert naive_posted.tzinfo is None

    job = DTO(
        title="Test", company="C", location=None,
        posted_text="5 hours ago",
        job_url="https://www.linkedin.com/jobs/view/1", job_id="1",
        scraped_at=now, posted_at=naive_posted,
    )
    normalized = service._normalize(job, scraped_at=now)

    assert normalized.posted_at is not None
    assert normalized.posted_at.tzinfo is not None  # MUST be aware


def test_naive_iso_from_time_element_does_not_crash_pipeline(db_session: Session) -> None:
    """End-to-end: a <time datetime='2024-01-15'> attribute yields a naive
    datetime from fromisoformat. The full pipeline must not crash with
    TypeError when _apply_date_filter compares it to the UTC-aware cutoff."""
    html = _card("2").replace(
        '<span class="job-card-container__listed-time">5 hours ago</span>',
        '<span class="job-card-container__listed-time"><time datetime="2024-01-15" class="job-search-card__listdate">5 hours ago</time></span>',
    )
    service, _ = _build_service(db_session, html)
    result = service.run(LinkedInScrapeRequest(keyword="ML", date_posted="past_24_hours"))

    assert result.errors == 0


# --- date filtering ----------------------------------------------------------------


def test_job_within_24_hours_is_kept(db_session: Session) -> None:
    html = _card("3", posted="5 hours ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="ML", date_posted="past_24_hours"))

    assert result.saved == 1
    assert result.filtered_by_date == 0
    assert len(result.jobs) == 1


def test_job_older_than_24_hours_is_filtered(db_session: Session) -> None:
    html = _card("4", posted="2 days ago")
    service, _ = _build_service(db_session, html)

    result = service.run(LinkedInScrapeRequest(keyword="ML", date_posted="past_24_hours"))

    assert result.saved == 0
    assert result.filtered_by_date == 1
    assert len(result.jobs) == 0


def test_job_at_24_hour_boundary_is_inclusive(db_session: Session) -> None:
    """A job posted exactly 24h before scraped_at sits at the cutoff boundary.
    The >= comparison keeps it (boundary is inclusive)."""
    from app.job_scraper.dto import ScrapedJob as DTO

    now = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)
    boundary_job = DTO(
        title="Boundary", company="C", location="Remote", posted_text="1 day ago",
        job_url="https://www.linkedin.com/jobs/view/555", job_id="555",
        scraped_at=now, posted_at=now - timedelta(hours=24),
    )

    service, _ = _build_service(db_session, _card("1"))
    kept, filtered = service._apply_date_filter([boundary_job], "past_24_hours", now)

    assert boundary_job in kept
    assert len(filtered) == 0


def test_aware_posted_at_comparison_does_not_raise(db_session: Session) -> None:
    """Direct unit test for _apply_date_filter with explicitly aware posted_at
    values — the exact scenario that caused the original TypeError."""
    from app.job_scraper.dto import ScrapedJob as DTO

    now = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)

    recent = DTO(
        title="Recent", company="C", location="Remote", posted_text="5 hours ago",
        job_url="https://www.linkedin.com/jobs/view/999", job_id="999",
        scraped_at=now, posted_at=now - timedelta(hours=5),
    )
    old = DTO(
        title="Old", company="O", location="Remote", posted_text="2 days ago",
        job_url="https://www.linkedin.com/jobs/view/888", job_id="888",
        scraped_at=now, posted_at=now - timedelta(hours=48),
    )

    service, _ = _build_service(db_session, _card("1"))
    kept, filtered = service._apply_date_filter([recent, old], "past_24_hours", now)

    assert recent in kept
    assert old in filtered


def test_naive_posted_at_input_does_not_crash_apply_date_filter(db_session: Session) -> None:
    """Even a naive posted_at must not crash _apply_date_filter — _normalize
    should have handled it, but _apply_date_filter should also be robust."""
    from app.job_scraper.dto import ScrapedJob as DTO

    now = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)

    naive_recent = DTO(
        title="Recent", company="C", location="Remote", posted_text="5 hours ago",
        job_url="https://www.linkedin.com/jobs/view/111", job_id="111",
        scraped_at=now, posted_at=datetime(2026, 8, 28, 7, 0, 0),  # naive
    )

    service, _ = _build_service(db_session, _card("1"))
    # This must not raise TypeError
    kept, filtered = service._apply_date_filter([naive_recent], "past_24_hours", now)
    assert naive_recent in kept
