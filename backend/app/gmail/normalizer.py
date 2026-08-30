"""
Turns a raw Gmail API `messages.get` response into a NormalizedEmail.

This is the only module that should know the shape of Gmail's API payload —
everything downstream (platform parsers, in later phases) works with
NormalizedEmail instead.
"""

import base64
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from app.gmail.dto import EmailLink, NormalizedEmail


def _decode_body_data(data: str) -> str:
    """Gmail base64url-encodes body parts, with padding sometimes stripped."""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _iter_parts(payload: dict) -> list[dict]:
    """Flattens Gmail's (possibly nested multipart) payload into a flat list
    of leaf parts."""
    parts = payload.get("parts")
    if not parts:
        return [payload]
    flattened: list[dict] = []
    for part in parts:
        flattened.extend(_iter_parts(part))
    return flattened


def _extract_bodies(payload: dict) -> tuple[str, str | None]:
    """Returns (plain_text, html) extracted from a Gmail message payload."""
    plain_text = ""
    html: str | None = None

    for part in _iter_parts(payload):
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if not data:
            continue
        decoded = _decode_body_data(data)
        if mime_type == "text/plain" and not plain_text:
            plain_text = decoded
        elif mime_type == "text/html" and html is None:
            html = decoded

    return plain_text, html


def _extract_links(html: str | None, plain_text: str) -> list[EmailLink]:
    links: list[EmailLink] = []
    seen: set[str] = set()

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            url = (href if isinstance(href, str) else str(href)).strip()
            if not url or url in seen or not url.startswith(("http://", "https://")):
                continue
            seen.add(url)
            anchor_text = anchor.get_text(strip=True)
            links.append(EmailLink(url=url, anchor_text=anchor_text))

    if not links and plain_text:
        # Generic fallback for plain-text-only alerts (spec section 11, Generic Parser).
        import re

        for match in re.finditer(r"https?://\S+", plain_text):
            url = match.group(0).rstrip(").,>\"'")
            if url not in seen:
                seen.add(url)
                links.append(EmailLink(url=url))

    return links


def _get_header(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def normalize_email(raw_message: dict) -> NormalizedEmail:
    """raw_message is the dict returned by Gmail API's
    `users.messages.get(..., format="full")`.
    """
    payload = raw_message.get("payload", {})
    headers = payload.get("headers", [])

    sender = _get_header(headers, "From")
    subject = _get_header(headers, "Subject")

    # internalDate is epoch milliseconds (UTC), set by Gmail itself — this is
    # the authoritative received_at, not a header we could get from spoofed content.
    internal_date_ms = int(raw_message.get("internalDate", "0"))
    received_at = datetime.fromtimestamp(internal_date_ms / 1000, tz=UTC)

    plain_text, html = _extract_bodies(payload)
    links = _extract_links(html, plain_text)

    return NormalizedEmail(
        gmail_message_id=raw_message["id"],
        thread_id=raw_message.get("threadId"),
        sender=sender,
        subject=subject,
        received_at=received_at,
        plain_text=plain_text,
        html=html,
        links=links,
    )
