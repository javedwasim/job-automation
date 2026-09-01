"""Pure, browser-free LinkedIn job-card parsing (spec: ONE CARD = ONE JOB).

The scraper collects every job CARD on the LinkedIn search-results page and
parses each card ONCE. A card may contain any number of anchors - job-title
link, job-detail link, company link, company logo, tracking/auxiliary links
- but they all belong to the same job and yield exactly ONE `ScrapedJob`.

These are pure HTML functions (no Playwright), so the one-card-one-job rule
and every field mapping is covered by deterministic unit tests.
"""

import re
from datetime import UTC, datetime
from html import unescape

from bs4 import BeautifulSoup, Tag

from app.job_alerts.extraction.job_posted_date_extractor import JobPostedDateExtractor
from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer
from app.job_scraper.dto import ScrapedJob

_URL_NORMALIZER = JobUrlNormalizer()
_DATE_EXTRACTOR = JobPostedDateExtractor()

_WHITESPACE_RE = re.compile(r"\s+")
# LinkedIn sr-only full-link text looks like "Title - Company - Location";
# only ever used as a title FALLBACK, and only the first segment is kept.
_SR_ONLY_SEP_RE = re.compile(r"\s+-\s+")
# Card text that is the posted-age line - never a location/company value.
_POSTED_PHRASE_RE = re.compile(
    r"\b(just now|\d+\s*(?:minute|hour|day|week|month|year)s?\s+ago)\b", re.IGNORECASE
)

# Card selectors, in priority order. The first set that matches becomes the
# card list - later (nested) selectors never double-count the same cards.
_CARD_SELECTORS = (
    "li[data-occludable-job-id]",
    "li[data-job-id]",
    "div.base-search-card",
    "div.job-card-container",
)

# Ordered candidate selectors per field, scoped to ONE card element. The
# first node yielding usable text wins.
_JOB_LINK_SELECTORS = (
    "a.base-card__full-link",
    "a.job-card-list__title--link",
    "a.job-card-container__link",
    'a[href*="/jobs/view/"]',
)
_TITLE_SELECTORS = (
    "a.job-card-list__title--link span[aria-hidden='true']",
    "h3.base-search-card__title",
    "span.job-card-list__title",
    "a.job-card-container__link span",
    "h3",
)
_COMPANY_SELECTORS = (
    "span.job-card-container__company-name",
    "span.job-card-container__primary-description",
    "h4.base-search-card__subtitle",
    "div.base-search-card__subtitle h4",
)
_LOCATION_SELECTORS = (
    "div.job-card-container__metadata-sibling",
    "li.job-card-container__metadata-item",
    "span.job-card-container__metadata-item",
    "p.job-search-card__location",
    "div.base-search-card__metadata p.job-search-card__location",
)
_POSTED_SELECTORS = (
    "span.job-card-container__listed-time",
    "time.job-search-card__listdate",
    "p.job-search-card__listdate",
    "time",
)


def find_job_cards(soup: BeautifulSoup | Tag) -> list[Tag]:
    """Every job CARD in the results page, in document order. Card-level
    objects only - the parser never iterates individual links."""
    for selector in _CARD_SELECTORS:
        cards = soup.select(selector)
        if cards:
            return cards
    return []


def parse_jobs_html(html: str, *, scraped_at: datetime | None = None) -> list[ScrapedJob]:
    """Parses a whole search-results page into one `ScrapedJob` per card.
    A malformed card (no usable title) is skipped WITHOUT stopping the
    scrape; the remaining cards still parse."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[ScrapedJob] = []
    for card in find_job_cards(soup):
        job = parse_job_card(card, scraped_at=scraped_at)
        if job is not None:
            jobs.append(job)
    return jobs


def parse_job_card(card: Tag, *, scraped_at: datetime | None = None) -> ScrapedJob | None:
    """Extracts the single job described by one card element.

    Guaranteed to inspect the card at most once and to return at most one
    job - regardless of how many <a> elements the card contains.
    """
    reference = scraped_at or datetime.now(UTC)

    job_url = _extract_job_link(card)
    job_id = _clean(card.get("data-occludable-job-id")) or _clean(card.get("data-job-id"))
    if not job_id and job_url:
        job_id = _URL_NORMALIZER.extract_job_id(job_url, "linkedin")

    title = _extract_title(card, job_url)
    if not title:
        return None

    company = _first_clean(card, _COMPANY_SELECTORS)
    location = _extract_location(card)
    posted_text, posted_at = _extract_posted(card, reference)

    return ScrapedJob(
        title=title,
        company=company,
        location=location,
        posted_text=posted_text,
        job_url=_URL_NORMALIZER.canonical(job_url, "linkedin") if job_url else None,
        job_id=job_id,
        scraped_at=reference,
        posted_at=posted_at,
    )


# --- per-field extraction ----------------------------------------------------


def _extract_job_link(card: Tag) -> str | None:
    """The ONE canonical job-detail URL for this card. Job links are
    preferred over company/logo/auxiliary links by selector order; the
    first matching anchor wins - selecting a link never mints a job."""
    for selector in _JOB_LINK_SELECTORS:
        anchor = card.select_one(selector)
        if anchor is None:
            continue
        href = _clean(anchor.get("href"))
        if href:
            return href
    return None


def _extract_title(card: Tag, job_url: str | None) -> str | None:
    for selector in _TITLE_SELECTORS:
        node = card.select_one(selector)
        if node is None:
            continue
        text = _clean(node.get_text(" ", strip=True))
        if text:
            return text
    # Last-resort: visible text of the job link itself, with the sr-only
    # "Title - Company - Location" tail trimmed to the title only.
    if job_url:
        anchor = card.select_one('a[href*="/jobs/view/"]')
        text = _clean(anchor.get_text(" ", strip=True)) if anchor else None
        if text:
            parts = [part.strip() for part in _SR_ONLY_SEP_RE.split(text) if part.strip()]
            if len(parts) >= 2:
                return parts[0]
            return text
    return None


def _extract_location(card: Tag) -> str | None:
    for selector in _LOCATION_SELECTORS:
        node = card.select_one(selector)
        if node is None:
            continue
        text = _clean(node.get_text(" ", strip=True))
        # A location line must never be the posted-age line.
        if text and not _POSTED_PHRASE_RE.search(text):
            return text
    return None


def _extract_posted(card: Tag, reference: datetime) -> tuple[str | None, datetime | None]:
    for selector in _POSTED_SELECTORS:
        node = card.select_one(selector)
        if node is None:
            continue
        text = _clean(node.get_text(" ", strip=True))
        datetime_attr = _clean(node.get("datetime")) if hasattr(node, "get") else None
        if not text and datetime_attr:
            text = datetime_attr
        if not text:
            continue
        posted_at = _parse_iso(datetime_attr) if datetime_attr else None
        if posted_at is None:
            posted_at = _DATE_EXTRACTOR.extract(text, reference)
        return text, posted_at
    return None, None


def _first_clean(card: Tag, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        node = card.select_one(selector)
        if node is None:
            continue
        text = _clean(node.get_text(" ", strip=True))
        if text and not _POSTED_PHRASE_RE.search(text):
            return text
    return None


def _clean(value: object | None) -> str | None:
    if not value:
        return None
    text = str(value)
    cleaned = _WHITESPACE_RE.sub(" ", unescape(text)).strip()
    return cleaned or None


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string from a LinkedIn ``<time datetime="...">``
    attribute, always returning a timezone-aware UTC datetime.

    LinkedIn date attributes are frequently bare dates (``2024-01-15``) with no
    offset, which ``datetime.fromisoformat`` would return as a naive value. A
    naive ``posted_at`` later crashes the date filter when compared to the
    scraper's UTC-aware ``scraped_at`` (spec: prefer timezone-aware UTC
    internally, never blindly strip tzinfo). Naive strings are interpreted as
    UTC — the same convention the shared ``JobPostedDateExtractor`` uses for
    explicit dates.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
