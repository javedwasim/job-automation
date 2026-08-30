"""UrlExtractor (spec section 16) — picks the most likely job URL out of an
email's links using anchor-text and platform-domain scoring.

Real job-alert emails contain plenty of links that are NOT job links — the
header logo (which points at linkedin.com/comm/feed/), "view all jobs",
account/notification pages, Indeed's clk.indeed.com/hp homepage link, bare
domains, unsubscribe, etc. Those must never win (or even tie with) a real
job link: the LinkedIn digest header link scoring a tie with job-card links
used to make every digest job point at linkedin.com/feed/.
"""

import re
from dataclasses import dataclass

from app.gmail.dto import EmailLink
from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer

# Shared instance for canonical dedup keys in extract_job_links().
_URL_NORMALIZER = JobUrlNormalizer()

_POSITIVE_ANCHOR_PHRASES = [
    "apply now",
    "apply",
    "view job",
    "view position",
    "job details",
    "see job",
]
_NEGATIVE_ANCHOR_PHRASES = [
    "unsubscribe",
    "manage preferences",
    "privacy policy",
    "help center",
    "view all",
    "see all",
    "sign in",
    "sign up",
    "join now",
]

# URL substrings that identify non-job destinations (nav/header/footer links,
# account pages, marketing pages). Anything matching is rejected outright.
_NEGATIVE_URL_PATTERNS = (
    "linkedin.com/feed",
    "linkedin.com/comm/feed",
    "linkedin.com/home",
    "linkedin.com/jobs/search",
    "linkedin.com/comm/jobs/search",
    "linkedin.com/jobs/browse",
    "linkedin.com/my-items",
    "linkedin.com/notifications",
    "linkedin.com/messaging",
    "linkedin.com/help",
    "linkedin.com/comm/help",
    "linkedin.com/psettings",
    "linkedin.com/uas",
    "linkedin.com/safety",
    "clk.indeed.com/hp",
    "gld.la",  # LinkedIn's email redirect shortener used by non-job links
    # Glassdoor non-job destinations (review/salary/community digests, nav).
    "glassdoor.com/reviews",
    "glassdoor.com/overview",
    "glassdoor.com/salary",
    "glassdoor.com/community",
    "glassdoor.com/blog",
    "glassdoor.com/awards",
    "glassdoor.com/index.htm",
    "glassdoor.com/profile",
    "glassdoor.com/employers",
    "glassdoor.com/research",
)

# Regexes that identify a genuine job-posting URL on a known platform. These
# get a decisive bonus so they always outrank generic platform-domain links.
_JOB_URL_PATTERNS = (
    re.compile(r"linkedin\.com/(?:comm/)?jobs/view/\d+"),
    re.compile(r"indeed\.com/(?:viewjob\?|rc/clk)"),
    re.compile(r"wellfound\.com/(?:jobs|role|job-listings)/"),
    re.compile(r"greenhouse\.io/jobs/\d+"),
    re.compile(r"lever\.co/[a-z0-9-]+/", re.IGNORECASE),
    re.compile(r"myworkdayjobs\.com/\S+/job/\S+", re.IGNORECASE),
    re.compile(r"ziprecruiter\.com/(?:jobs|c)/"),
    re.compile(r"dice\.com/(?:jobs/)?detail/", re.IGNORECASE),
    re.compile(r"glassdoor\.com/(?:job-listing/|partner/joblisting\.htm)", re.IGNORECASE),
)

# A URL with no path at all (https://www.indeed.com, https://linkedin.com) is
# a homepage/logo link, never a job link.
_BARE_DOMAIN_RE = re.compile(r"https?://[^/]+/?$", re.IGNORECASE)

_POSITIVE_ANCHOR_BONUS = 0.4
_JOB_URL_BONUS = 0.6
_PLATFORM_DOMAIN_WEIGHT = 0.3
_KNOWN_JOB_DOMAINS = ("linkedin.com", "indeed.com", "wellfound.com", "glassdoor.com")


@dataclass(frozen=True)
class UrlExtractionResult:
    url: str
    confidence: float
    reason: str
    # True when the URL matched a known job-posting URL pattern — lets the
    # GenericParser (which sees arbitrary emails) avoid fabricating jobs
    # from newsletters that happen to contain ordinary links.
    direct_job_url: bool = False


class UrlExtractor:
    def extract(self, links: list[EmailLink]) -> UrlExtractionResult | None:
        candidates: list[UrlExtractionResult] = []

        for link in links:
            anchor_lower = link.anchor_text.lower()
            url_lower = link.url.lower()

            if any(neg in anchor_lower for neg in _NEGATIVE_ANCHOR_PHRASES):
                continue
            if any(neg in url_lower for neg in _NEGATIVE_URL_PATTERNS):
                continue
            if _BARE_DOMAIN_RE.match(link.url):
                continue

            score = 0.5  # baseline: it's a link in a job-alert email
            reasons: list[str] = []

            for phrase in _POSITIVE_ANCHOR_PHRASES:
                if phrase in anchor_lower:
                    score += _POSITIVE_ANCHOR_BONUS
                    reasons.append(f'"{link.anchor_text}" anchor')
                    break

            for domain in _KNOWN_JOB_DOMAINS:
                if domain in url_lower:
                    score += _PLATFORM_DOMAIN_WEIGHT
                    reasons.append(f"{domain} URL")
                    break

            direct_job_url = False
            for pattern in _JOB_URL_PATTERNS:
                if pattern.search(link.url):
                    score += _JOB_URL_BONUS
                    direct_job_url = True
                    reasons.append("direct job-posting URL")
                    break

            score = min(score, 0.99)
            reason = " + ".join(reasons) if reasons else "generic link, no strong signal"
            candidates.append(
                UrlExtractionResult(
                    url=link.url,
                    confidence=round(score, 2),
                    reason=reason,
                    direct_job_url=direct_job_url,
                )
            )

        if not candidates:
            return None

        return max(candidates, key=lambda c: c.confidence)

    def extract_job_links(self, links: list[EmailLink]) -> list[EmailLink]:
        """ALL links pointing at genuine job postings (spec section 9), in
        email order, deduplicated by URL, junk links (nav/footer/unsubscribe)
        excluded. Platform parsers use this so a digest with N jobs yields N
        candidate URLs — never just the first one."""
        seen: set[str] = set()
        job_links: list[EmailLink] = []

        for link in links:
            anchor_lower = link.anchor_text.lower()
            url_lower = link.url.lower()

            if any(neg in anchor_lower for neg in _NEGATIVE_ANCHOR_PHRASES):
                continue
            if any(neg in url_lower for neg in _NEGATIVE_URL_PATTERNS):
                continue
            if _BARE_DOMAIN_RE.match(link.url):
                continue
            if not any(pattern.search(link.url) for pattern in _JOB_URL_PATTERNS):
                continue

            # Canonical key for dedup — the same job reached via two links
            # (title link + "Apply now" button, or with different tracking
            # params) must count once. Canonicalization (tracking stripped,
            # aliases collapsed) makes this exact instead of best-effort.
            key = _URL_NORMALIZER.canonical(link.url)
            if key in seen:
                continue
            seen.add(key)
            job_links.append(link)

        return job_links
