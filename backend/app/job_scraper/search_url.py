"""Builds LinkedIn job-search URLs from filter values (pure function).

LinkedIn's /jobs/search endpoint encodes the filters as query parameters:

  keywords  free-text job keyword
  location  free-text location ("Remote", "Pakistan", "Lahore", ...)
  f_TPR     date-posted window (r86400 = past 24h, r604800 = week,
            r2592000 = month); omitted for "any time"
  f_JT      job type   (F full-time, P part-time, C contract, T temporary,
            I internship)
  f_WT      workplace  (1 on-site, 2 remote, 3 hybrid)

This module is the single place that knows LinkedIn's filter codes — the
service layer never sees them.
"""

from urllib.parse import urlencode

_BASE_URL = "https://www.linkedin.com/jobs/search/"

# date_posted value -> LinkedIn f_TPR token. "any" omits the filter (LinkedIn
# then returns everything, and OUR OWN date validation below decides).
DATE_POSTED_QUERY: dict[str, str | None] = {
    "any": None,
    "past_24_hours": "r86400",
    "past_week": "r604800",
    "past_month": "r2592000",
}

# job_type value -> LinkedIn f_JT token.
JOB_TYPE_QUERY: dict[str, str | None] = {
    "any": None,
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
}

# workplace value -> LinkedIn f_WT token.
WORKPLACE_QUERY: dict[str, str | None] = {
    "any": None,
    "remote": "2",
    "hybrid": "3",
    "onsite": "1",
}


def build_linkedin_search_url(
    *,
    keyword: str = "",
    location: str = "",
    date_posted: str = "any",
    job_type: str = "any",
    workplace: str = "any",
) -> str:
    """Composes the LinkedIn /jobs/search URL for the given filters.

    Unknown filter values (or "any") simply contribute no query parameter,
    which is LinkedIn's default behaviour — nothing is hard-coded to a
    single keyword/location.
    """
    params: dict[str, str] = {}
    keyword = (keyword or "").strip()
    if keyword:
        params["keywords"] = keyword
    location = (location or "").strip()
    if location:
        params["location"] = location
    if token := DATE_POSTED_QUERY.get(date_posted):
        params["f_TPR"] = token
    if token := JOB_TYPE_QUERY.get(job_type):
        params["f_JT"] = token
    if token := WORKPLACE_QUERY.get(workplace):
        params["f_WT"] = token
    query = urlencode(params)
    return f"{_BASE_URL}?{query}" if query else _BASE_URL