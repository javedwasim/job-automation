import base64


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


SINGLE_HTML = """<html><body>
  <p>1 new job for PHP Developers</p>
  <a href="https://wellfound.com/job-listings/abc123-senior-php-dev?src=email">
    Senior PHP Developer
  </a>
  <p>Senior PHP Developer</p>
  <p>TechCorp</p>
  <p>Lahore, Pakistan</p>
  <p>$150,000 - $180,000 a year</p>
  <p>Full-time</p>
</body></html>"""

SINGLE_PLAIN = (
    "1 new job for PHP Developers\n"
    "Senior PHP Developer\n"
    "TechCorp\n"
    "Lahore, Pakistan\n"
    "$150,000 - $180,000 a year\n"
    "Full-time\n"
)

DIGEST_HTML = """<html><body>
  <p>3 new jobs match your alert</p>
  <a href="https://wellfound.com/job-listings/wellfound-111-backend?src=email">Backend Developer</a>
  <p>Backend Developer</p>
  <p>ABC Technologies</p>
  <p>Remote</p>
  <a href="https://wellfound.com/job-listings/wellfound-222-php?src=email">PHP Developer</a>
  <p>PHP Developer</p>
  <p>XYZ Solutions</p>
  <p>Lahore, Pakistan</p>
  <a href="https://wellfound.com/job-listings/wellfound-333-laravel?src=email">Laravel Engineer</a>
  <p>Laravel Engineer</p>
  <p>WebWorks</p>
  <p>Karachi, Pakistan</p>
</body></html>"""

DIGEST_PLAIN = (
    "3 new jobs match your alert\n"
    "Backend Developer\n"
    "ABC Technologies\n"
    "Remote\n"
    "PHP Developer\n"
    "XYZ Solutions\n"
    "Lahore, Pakistan\n"
    "Laravel Engineer\n"
    "WebWorks\n"
    "Karachi, Pakistan\n"
)


def _make_raw_message(
    *,
    message_id: str,
    subject: str,
    html: str,
    plain: str,
    sender: str = "Wellfound <notifications@wellfound.com>",
    internal_date_ms: int = 1787912100000,
) -> dict:
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


def make_single_job_raw_message(message_id: str = "wellfound-single-1") -> dict:
    return _make_raw_message(
        message_id=message_id,
        subject="1 new job for PHP Developers",
        html=SINGLE_HTML,
        plain=SINGLE_PLAIN,
    )


def make_multi_job_raw_message(message_id: str = "wellfound-digest-1") -> dict:
    return _make_raw_message(
        message_id=message_id,
        subject="3 new jobs match your alert",
        html=DIGEST_HTML,
        plain=DIGEST_PLAIN,
    )
