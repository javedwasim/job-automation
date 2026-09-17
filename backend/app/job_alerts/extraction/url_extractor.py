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
# Multi-word navigational/footer phrases. Also see _NEGATIVE_ANCHOR_WORDS
# (word-boundary single tokens). Matching is on the normalized (lowercased,
# whitespace-collapsed) anchor text.
_NEGATIVE_ANCHOR_PHRASES = [
    "unsubscribe",
    "manage preferences",
    "email preferences",
    "notification settings",
    "notifications settings",
    "manage your job alerts",
    "manage your alerts",
    "manage job alerts",
    "job alert settings",
    "privacy policy",
    "terms of use",
    "help center",
    "view all jobs",
    "see all jobs",
    "see more jobs",
    "view more jobs",
    "view all",
    "see all",
    "see more",
    "view more",
    "more jobs",
    "your other saved jobs",
    "saved jobs",
    "saved job",
    "jobs home",
    "job search",
    "search jobs",
    "recommended jobs",
    "sign in",
    "sign up",
    "log in",
    "create account",
    "join now",
    "linkedin home",
    "visit linkedin",
    "open to work",
    "career advice",
    "manage other jobs",
]
# Single tokens that mark navigation when they appear as whole words, e.g.
# "Manage", "Settings", "Saved", "Recommended", "Privacy".
_NEGATIVE_ANCHOR_WORDS = (
    "manage",
    "settings",
    "privacy",
    "terms",
    "saved",
    "recommended",
    "notifications",
    "unsubscribe",
)


def _is_nav_anchor(anchor_text: str) -> bool:
    """True when the anchor text belongs to a navigation/footer/utility link
    (unsubscribe / email preferences / "Your other saved jobs" / "View all
    jobs" / ...). Such links must never become job candidates even when the
    destination URL happens to look like a job-posting URL."""
    lowered = " ".join((anchor_text or "").lower().split())
    if not lowered:
        return False
    for phrase in _NEGATIVE_ANCHOR_PHRASES:
        if phrase in lowered:
            return True
    for token in _NEGATIVE_ANCHOR_WORDS:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            return True
    return False

# URL substrings that identify non-job destinations (nav/header/footer links,
# account pages, marketing pages). Anything matching is rejected outright.
# NOTE: no bare "linkedin.com/jobs" entry — that string is a prefix of the
# real job URLs (…/jobs/view/<id>) and must never reject them.
_NEGATIVE_URL_PATTERNS = (
    "linkedin.com/feed",
    "linkedin.com/comm/feed",
    "linkedin.com/home",
    "linkedin.com/jobs/search",
    "linkedin.com/comm/jobs/search",
    "linkedin.com/jobs/browse",
    "linkedin.com/jobs/saved",
    "linkedin.com/jobs/collections",
    "linkedin.com/jobs/alerts",
    "linkedin.com/in/",
    "linkedin.com/company/",
    "linkedin.com/mynetwork",
    "linkedin.com/groups",
    "linkedin.com/posts/",
    "linkedin.com/my-items",
    "linkedin.com/notifications",
    "linkedin.com/messaging",
    "linkedin.com/help",
    "linkedin.com/comm/help",
    "linkedin.com/psettings",
    "linkedin.com/uas",
    "linkedin.com/safety",
    "linkedin.com/learning",
    "linkedin.com/sales",
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


def is_supported_job_url(url: str) -> bool:
    """True when the URL matches a recognized job-posting URL pattern.

    Used by the centralized normalizer's validation gate: a candidate whose
    URL carries no job identity (no platform job ID) AND matches none of these
    supported patterns is not a job listing — it must never become a Job row.
    """
    return bool(url) and any(pattern.search(url) for pattern in _JOB_URL_PATTERNS)

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

            if _is_nav_anchor(link.anchor_text):
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
        email order. Junk links (nav/footer/unsubscribe/"Your other saved
        jobs"/tracking-only) are excluded, and links whose URL is NOT a
        supported job-posting URL can never become a candidate — a URL is
        necessary but never sufficient to create a job (spec section 3).

        Deduplication is by canonical URL (tracking stripped, /comm/ aliases
        collapsed), so the same job reached via a logo link, a title link and
        an \"Apply now\" button — each carrying different tracking params —
        counts ONCE. When a canonical URL appears multiple times the copy
        with real anchor text (the job title) is preferred over the empty
        logo link.
        """
        # canonical url -> best link copy (ordered: first-seen order kept).
        best: dict[str, EmailLink] = {}

        for link in links:
            url_lower = link.url.lower()
            if _is_nav_anchor(link.anchor_text):
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
            current = best.get(key)
            # When two links resolve to the same canonical job URL, keep the
            # one with the longest anchor text — the job-title link beats
            # the empty logo link AND a short "Apply now" button, regardless
            # of which appeared first in the email (spec section 9: each job
            # keeps its own URL with correct title association).
            if current is None or (
                len(link.anchor_text.strip()) > len(current.anchor_text.strip())
            ):
                best[key] = link

        return list(best.values())
