from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EmailLink:
    """A single link found in a job-alert email, with the anchor text it was
    found under — used later by UrlExtractor (Phase 3) to score candidate
    job URLs (e.g. anchor text "View Job" vs "Unsubscribe").
    """

    url: str
    anchor_text: str = ""


@dataclass(frozen=True)
class NormalizedEmail:
    """Platform-independent representation of a Gmail message.

    Platform parsers (Phase 2+) consume this, never the raw Gmail API
    response — that's what keeps Gmail integration independent from
    platform parsing (spec section 7).
    """

    gmail_message_id: str
    thread_id: str | None
    sender: str
    subject: str
    received_at: datetime  # must be timezone-aware, from Gmail's internalDate
    plain_text: str
    html: str | None
    links: list[EmailLink] = field(default_factory=list)
