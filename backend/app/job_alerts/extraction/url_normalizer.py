"""JobUrlNormalizer (spec section 8) — THE centralized, platform-aware job
URL canonicalization + platform-job-ID extraction service.

Platform parsers never normalize URLs themselves; they hand over whatever
URL the email contained and this service (shared with the fingerprint and
processing layers) produces:

  1. A canonical URL — tracking parameters stripped, fragment dropped,
     host/scheme normalized, parameter order stabilized, platform-specific
     email-redirect path variants collapsed (e.g. LinkedIn's /comm/ prefix).
  2. The platform job ID where the URL (or a required query parameter)
     carries one (e.g. LinkedIn /jobs/view/<id>, Indeed jk=<key>,
     Glassdoor _JO<id>.htm).

Per-platform knowledge lives in small, isolated `PlatformUrlRule` entries
(spec section 5: extensibility without duplication). Unknown query
parameters are KEPT — parameters are only removed when they are known
tracking noise, never blindly (some platforms require query params to
identify the actual job, e.g. Indeed's jk/vjk).
"""

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Universal tracking/noise parameters (safe to strip from any URL).
_GENERIC_TRACKING_PREFIXES = ("utm_",)
_GENERIC_TRACKING_PARAMS = frozenset(
    {
        "trk",
        "trkinfo",
        "tracking_id",
        "trackingid",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "refid",
        "referrer",
        "lipi",
        "midtoken",
        "midsig",
    }
)


@dataclass(frozen=True)
class PlatformUrlRule:
    """Small, isolated per-platform normalization strategy (spec section 8)."""

    domain: str
    # Query parameters that ARE required to identify the job — never stripped.
    required_params: frozenset[str] = field(default=frozenset())
    # Platform-specific parameters known to be tracking noise.
    tracking_params: frozenset[str] = field(default=frozenset())
    # Path segments (regex) that are email-specific aliases of the canonical
    # path — removed during canonicalization (e.g. LinkedIn's /comm/ prefix).
    alias_path_patterns: tuple[re.Pattern[str], ...] = field(default_factory=tuple)
    # Regexes whose first group captures the platform job ID.
    job_id_patterns: tuple[re.Pattern[str], ...] = field(default_factory=tuple)


_PLATFORM_RULES: dict[str, PlatformUrlRule] = {
    "linkedin": PlatformUrlRule(
        domain="linkedin.com",
        tracking_params=frozenset({"originalsubdomain", "position", "pagesize", "currentjobid"}),
        alias_path_patterns=(re.compile(r"/comm/"),),
        job_id_patterns=(re.compile(r"/jobs/view/(\d+)"),),
    ),
    "indeed": PlatformUrlRule(
        domain="indeed.com",
        required_params=frozenset({"jk", "vjk"}),
        tracking_params=frozenset({"from", "tk", "attributionid", "adid", "cmp", "sid", "co"}),
        job_id_patterns=(
            re.compile(r"[?&]jk=([a-z0-9]+)", re.IGNORECASE),
            re.compile(r"[?&]vjk=([a-z0-9]+)", re.IGNORECASE),
        ),
    ),
    "glassdoor": PlatformUrlRule(
        domain="glassdoor.com",
        tracking_params=frozenset({"src", "s", "emailtype", "guid", "acid"}),
        job_id_patterns=(re.compile(r"_JO(\d+)"),),
    ),
    "wellfound": PlatformUrlRule(
        domain="wellfound.com",
        tracking_params=frozenset({"src", "utm_medium"}),
        job_id_patterns=(re.compile(r"/job-listings/([a-z0-9-]+)", re.IGNORECASE),),
    ),
}

_DEFAULT_RULE = PlatformUrlRule(domain="")


class JobUrlNormalizer:
    """Stateless service — safe to share across parsers, processing and
    fingerprinting."""

    def canonical(self, url: str, platform: str | None = None) -> str:
        """Canonical form of a job URL: tracking stripped, fragment gone,
        scheme/host normalized, kept params sorted for stable comparison."""
        if not url:
            return url
        parsed = urlparse(url.strip())
        if not parsed.scheme and not parsed.netloc:
            return url.strip()

        rule = self._rule_for(platform, url)
        kept_params = self._kept_params(parsed, rule)

        path = parsed.path or ""
        for pattern in rule.alias_path_patterns:
            path = pattern.sub("/", path, count=1)
        # Collapse duplicate slashes produced by alias removal.
        path = re.sub(r"/{2,}", "/", path)
        # Normalize a single trailing slash: /jobs/view/123/ and
        # /jobs/view/123 are the SAME job (tracking variants frequently add
        # or drop it) and must canonicalize identically.
        if len(path) > 1:
            path = path.rstrip("/")

        return urlunparse(
            parsed._replace(
                scheme=parsed.scheme.lower() or "https",
                netloc=parsed.netloc.lower(),
                path=path,
                query=urlencode(kept_params),
                fragment="",
            )
        )

    def extract_job_id(self, url: str | None, platform: str | None = None) -> str | None:
        """Platform job ID from the URL, when the platform encodes one."""
        if not url:
            return None
        rule = self._rule_for(platform, url)
        for pattern in rule.job_id_patterns:
            if match := pattern.search(url):
                return match.group(1)
        return None

    def _rule_for(self, platform: str | None, url: str) -> PlatformUrlRule:
        if platform and platform in _PLATFORM_RULES:
            return _PLATFORM_RULES[platform]
        url_lower = url.lower()
        for rule in _PLATFORM_RULES.values():
            if rule.domain and rule.domain in url_lower:
                return rule
        return _DEFAULT_RULE

    @staticmethod
    def _kept_params(parsed, rule: PlatformUrlRule) -> list[tuple[str, str]]:
        kept: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            key_lower = key.lower()
            if key_lower in rule.required_params:
                kept.append((key, value))
                continue
            if key_lower.startswith(_GENERIC_TRACKING_PREFIXES):
                continue
            if key_lower in _GENERIC_TRACKING_PARAMS or key_lower in rule.tracking_params:
                continue
            kept.append((key, value))
        # Sorted so parameter order never changes the canonical form.
        return sorted(kept)


def normalize_job_url(url: str, platform: str | None = None) -> str:
    """Module-level convenience wrapper used by fingerprinting."""
    return JobUrlNormalizer().canonical(url, platform)


def extract_platform_job_id(url: str | None, platform: str | None = None) -> str | None:
    """Module-level convenience wrapper used by parsers' finalization."""
    return JobUrlNormalizer().extract_job_id(url, platform)

