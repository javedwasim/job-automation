import base64


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


SINGLE_HTML = """<html><body>
  <p>1 new job in Lahore, Pakistan</p>
  <a href="https://www.indeed.com/viewjob?jk=abc123def456&amp;from=alertemail&amp;tk=1h9z2x">Senior PHP Developer</a>
  <p>Senior PHP Developer</p>
  <p>TechCorp - Lahore, Pakistan</p>
  <p>$150,000 - $180,000 a year</p>
  <p>Full-time</p>
  <p>Posted 5 hours ago</p>
  <a href="https://www.indeed.com/unsubscribe?email=x">Unsubscribe</a>
</body></html>"""

SINGLE_PLAIN = (
    "1 new job in Lahore, Pakistan\n"
    "Senior PHP Developer\n"
    "TechCorp - Lahore, Pakistan\n"
    "$150,000 - $180,000 a year\n"
    "Full-time\n"
    "Posted 5 hours ago\n"
)

DIGEST_HTML = """<html><body>
  <p>5 new jobs match your search</p>
  <a href="https://www.indeed.com/viewjob?jk=jobkey111111&amp;from=alertemail">Senior PHP Developer</a>
  <p>Senior PHP Developer</p>
  <p>TechCorp - Lahore, Pakistan</p>
  <p>$150,000 - $180,000 a year</p>
  <p>Full-time</p>
  <p>Posted 3 hours ago</p>
  <a href="https://www.indeed.com/viewjob?jk=jobkey222222&amp;from=alertemail">Backend Engineer</a>
  <p>Backend Engineer</p>
  <p>DataSoft - Remote</p>
  <p>PKR 350,000 - 450,000 a month</p>
  <p>Contract</p>
  <p>Posted 1 day ago</p>
  <a href="https://www.indeed.com/viewjob?jk=jobkey333333&amp;from=alertemail">Laravel Developer</a>
  <p>Laravel Developer</p>
  <p>WebWorks - Karachi, Pakistan</p>
  <p>Posted 2 weeks ago</p>
  <a href="https://www.indeed.com/unsubscribe?email=x">Unsubscribe</a>
</body></html>"""

DIGEST_PLAIN = (
    "5 new jobs match your search\n"
    "Senior PHP Developer\n"
    "TechCorp - Lahore, Pakistan\n"
    "$150,000 - $180,000 a year\n"
    "Full-time\n"
    "Posted 3 hours ago\n"
    "Backend Engineer\n"
    "DataSoft - Remote\n"
    "PKR 350,000 - 450,000 a month\n"
    "Contract\n"
    "Posted 1 day ago\n"
    "Laravel Developer\n"
    "WebWorks - Karachi, Pakistan\n"
    "Posted 2 weeks ago\n"
)


def _make_raw_message(
    *,
    message_id: str,
    subject: str,
    html: str,
    plain: str,
    sender: str = "Indeed Job Alerts <jobs-alerts@indeed.com>",
    internal_date_ms: int = 1787912100000,
) -> dict:
    """Builds a Gmail API `messages.get` style payload for an Indeed job
    alert email, for use in parser and pipeline tests."""
    return {
        "id": message_id,
        "threadId": message_id,
        "internalDate": str(internal_date_ms),
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64(plain)}},
                {"mimeType": "text/html", "body": {"data": _b64(html)}},
            ],
        },
    }


def make_single_job_raw_message(message_id: str = "indeed-single-1") -> dict:
    """A single-job Indeed alert (spec section 21: Indeed single-job email)."""
    return _make_raw_message(
        message_id=message_id,
        subject="1 new job in Lahore, Pakistan",
        html=SINGLE_HTML,
        plain=SINGLE_PLAIN,
    )


def make_multi_job_raw_message(message_id: str = "indeed-digest-1") -> dict:
    """A 3-job Indeed digest (spec section 21: Indeed multi-job digest)."""
    return _make_raw_message(
        message_id=message_id,
        subject="5 new jobs match your search",
        html=DIGEST_HTML,
        plain=DIGEST_PLAIN,
    )
