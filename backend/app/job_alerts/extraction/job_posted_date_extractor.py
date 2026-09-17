"""
JobPostedDateExtractor (spec sections 4, 5, 7) — THE shared, platform-
independent posting-date extraction service. Every platform parser delegates
here; none of them may reimplement relative-date math.

Priority order:
  1. Explicit platform posting timestamp (parsers pass it straight through
     as job_posted_at if the platform gives one)
  2. Explicit posting date in the text ("Posted Aug 28, 2026", ISO dates)
  3. Relative posting time ("Posted 3 hours ago", "3 hours ago", "Just now",
     "2 weeks ago", "Posted yesterday", ...)
  4. NULL — never fabricated, never silently replaced with received_at.

The reference timestamp for every relative phrase is ALWAYS the email's own
received_at (spec section 4) — an email received 2026-08-30 10:00 containing
"3 hours ago" means 2026-08-30 07:00, even if it is processed days later.
Using "now" instead would silently rewrite history.
"""

import re
from datetime import UTC, datetime, timedelta

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

# Explicit absolute date: "Posted on Aug 28, 2026", "Posted Aug 28 2026".
_EXPLICIT_DATE_RE = re.compile(
    r"posted\s+(?:on\s+)?([A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})", re.IGNORECASE
)
# Explicit ISO date: "Posted 2026-08-28".
_EXPLICIT_ISO_RE = re.compile(r"posted\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})", re.IGNORECASE)

# Combined relative phrase: leftmost match in the text wins, so a block that
# mentions "3 days ago" before "2 weeks ago" resolves to the first mention.
# Handles "Just now", "1 minute ago", "30 minutes ago", "1 hour ago",
# "5 hours ago", "1 day ago", "3 days ago", "1 week ago", "2 weeks ago",
# "1 month ago", "1 year ago" — each with or without a "Posted (on)" prefix.
_RELATIVE_AGO_RE = re.compile(
    r"(?:posted\s*:?\s*)?"
    r"(?:(\d+)\s*(minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\s+ago"
    r"|just\s+now)",
    re.IGNORECASE,
)

# Only trust yesterday/today when explicitly tied to posting.
_YESTERDAY_RE = re.compile(r"posted\s+yesterday", re.IGNORECASE)
_TODAY_RE = re.compile(r"posted\s+today|new\s+job\s+posted\s+today", re.IGNORECASE)

_UNIT_ALIASES = {
    "minute": "minutes",
    "minutes": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "hour": "hours",
    "hours": "hours",
    "hr": "hours",
    "hrs": "hours",
    "day": "days",
    "days": "days",
    "week": "weeks",
    "weeks": "weeks",
    "month": "months",
    "months": "months",
    "year": "years",
    "years": "years",
}


class JobPostedDateExtractor:
    """Stateless — every method takes received_at explicitly so relative
    phrases ("3 hours ago") resolve against the email's own received time,
    not "now" (which would be wrong for emails processed late)."""

    def extract(self, text: str, received_at: datetime) -> datetime | None:
        if not text:
            return None

        explicit = self._extract_explicit_date(text)
        if explicit is not None:
            return self._guard_future(explicit, received_at)

        relative = self._extract_relative(text, received_at)
        if relative is not None:
            return self._guard_future(relative, received_at)

        return None

    def _extract_explicit_date(self, text: str) -> datetime | None:
        for pattern in (_EXPLICIT_DATE_RE, _EXPLICIT_ISO_RE):
            match = pattern.search(text)
            if not match:
                continue
            try:
                parsed = dateutil_parser.parse(match.group(1))
            except (ValueError, OverflowError):
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        return None

    def _extract_relative(self, text: str, received_at: datetime) -> datetime | None:
        for match in _RELATIVE_AGO_RE.finditer(text):
            # "just now" alternative -> group(1)/group(2) are None.
            if match.group(1) is None:
                return received_at
            amount = int(match.group(1))
            unit = _UNIT_ALIASES.get(match.group(2).lower())
            if unit == "minutes":
                return received_at - timedelta(minutes=amount)
            if unit == "hours":
                return received_at - timedelta(hours=amount)
            if unit == "days":
                return received_at - timedelta(days=amount)
            if unit == "weeks":
                return received_at - timedelta(weeks=amount)
            if unit == "months":
                return received_at - relativedelta(months=amount)
            if unit == "years":
                return received_at - relativedelta(years=amount)
        if _YESTERDAY_RE.search(text):
            return received_at - timedelta(days=1)
        if _TODAY_RE.search(text):
            return received_at
        return None

    @staticmethod
    def _guard_future(posted_at: datetime, received_at: datetime) -> datetime | None:
        """A posting date after the email was received is bad/untrusted data —
        never let it through (spec section 4: never fabricate)."""
        if posted_at > received_at:
            return None
        return posted_at

