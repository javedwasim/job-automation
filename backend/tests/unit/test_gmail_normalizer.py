from datetime import UTC, datetime

from app.gmail.html_text import html_to_plain_text
from app.gmail.normalizer import normalize_email
from tests.fixtures.linkedin.job_alert_message import make_raw_message


def test_html_to_plain_text_strips_mso_conditional_comments() -> None:
    """Outlook/MSO conditional markup ("[if (gte mso 9)|(IE)]", <table>,
    <tr>, <td>, [endif]) is comment content — BeautifulSoup hands it back as
    a Comment node (a NavigableString subclass), so it must be skipped or it
    leaks into job fields as raw HTML."""
    html = (
        "<html><body>"
        '<!--[if (gte mso 9)|(IE)]><table width="600"><tr><td>'
        "Senior PHP Developer</td></tr></table><![endif]-->"
        "<p>TechCorp</p>"
        "</body></html>"
    )

    text = html_to_plain_text(html)

    assert "TechCorp" in text
    for marker in ("[if", "endif", "<table", "<tr>", "<td>", "Senior PHP Developer"):
        assert marker not in text


def test_normalize_email_extracts_core_fields() -> None:
    raw = make_raw_message()

    normalized = normalize_email(raw)

    assert normalized.gmail_message_id == raw["id"]
    assert normalized.thread_id == raw["threadId"]
    assert normalized.sender == "LinkedIn Job Alerts <jobs-noreply@linkedin.com>"
    assert normalized.subject == "5 new Laravel jobs near you"
    assert "Senior Laravel Developer" in normalized.plain_text
    assert normalized.html is not None and "linkedin.com/jobs/view" in normalized.html


def test_normalize_email_received_at_is_utc_and_correct() -> None:
    raw = make_raw_message(internal_date_ms=1756370100000)

    normalized = normalize_email(raw)

    assert normalized.received_at.tzinfo is not None
    assert normalized.received_at == datetime.fromtimestamp(1756370100000 / 1000, tz=UTC)


def test_normalize_email_extracts_links_with_anchor_text() -> None:
    raw = make_raw_message()

    normalized = normalize_email(raw)

    urls = {link.url: link.anchor_text for link in normalized.links}
    assert "https://www.linkedin.com/jobs/view/123456?trk=alert" in urls
    assert urls["https://www.linkedin.com/jobs/view/123456?trk=alert"] == "View Job"
    # Unsubscribe link is still extracted here — scoring/filtering it out is
    # UrlExtractor's job in Phase 3, not the normalizer's.
    assert any("unsubscribe" in url for url in urls)


def test_normalize_email_falls_back_to_plain_text_links_when_no_html() -> None:
    raw = make_raw_message()
    raw["payload"]["parts"] = [p for p in raw["payload"]["parts"] if p["mimeType"] == "text/plain"]
    raw["payload"]["parts"][0]["body"]["data"] = raw["payload"]["parts"][0]["body"]["data"]

    # Rebuild plain text to include a bare URL since the fixture's plain body has none.
    import base64

    plain_with_url = "5 new Laravel jobs near you\nhttps://www.linkedin.com/jobs/view/999\n"
    raw["payload"]["parts"][0]["body"]["data"] = (
        base64.urlsafe_b64encode(plain_with_url.encode()).decode().rstrip("=")
    )

    normalized = normalize_email(raw)

    assert normalized.html is None
    assert any(link.url == "https://www.linkedin.com/jobs/view/999" for link in normalized.links)
