import base64


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


SINGLE_HTML = """<html><body>
  <p>1 new job for PHP Developers in Lahore</p>
  <a href="https://www.glassdoor.com/job-listing/senior-php-developer-techcorp-D_JO31112586.htm?src=GD_EMAIL">Senior PHP Developer</a>
  <p>Senior PHP Developer</p>
  <p>TechCorp</p>
  <p>Lahore, Pakistan</p>
  <p>PKR 250,000 - 350,000 a month</p>
  <p>Full-time</p>
  <p>Posted 5 hours ago</p>
  <a href="https://www.glassdoor.com/partner/jobListing.htm?pos=101&amp;ao=1135430&amp;s=58&amp;src=GD_EMAIL">Apply Now</a>
</body></html>"""

SINGLE_PLAIN = (
    "1 new job for PHP Developers in Lahore\n"
    "Senior PHP Developer\n"
    "TechCorp\n"
    "Lahore, Pakistan\n"
    "PKR 250,000 - 350,000 a month\n"
    "Full-time\n"
    "Posted 5 hours ago\n"
    "Apply Now\n"
)

DIGEST_HTML = """<html><body>
  <p>3 new jobs match your alert</p>
  <a href="https://www.glassdoor.com/job-listing/backend-developer-abc-D_JO31112001.htm?src=GD_EMAIL">Backend Developer</a>
  <p>Backend Developer</p>
  <p>ABC Technologies</p>
  <p>Remote</p>
  <p>Posted 3 hours ago</p>
  <a href="https://www.glassdoor.com/job-listing/php-developer-xyz-D_JO31112002.htm?src=GD_EMAIL&amp;guid=track-me">PHP Developer</a>
  <p>PHP Developer</p>
  <p>XYZ Solutions</p>
  <p>Lahore, Pakistan</p>
  <p>Posted 1 day ago</p>
  <a href="https://www.glassdoor.com/job-listing/laravel-engineer-webworks-D_JO31112003.htm?src=GD_EMAIL">Laravel Engineer</a>
  <p>Laravel Engineer</p>
  <p>WebWorks</p>
  <p>Karachi, Pakistan</p>
  <p>Posted 2 weeks ago</p>
  <a href="https://www.glassdoor.com/community/index.htm">Community</a>
</body></html>"""

DIGEST_PLAIN = (
    "3 new jobs match your alert\n"
    "Backend Developer\n"
    "ABC Technologies\n"
    "Remote\n"
    "Posted 3 hours ago\n"
    "PHP Developer\n"
    "XYZ Solutions\n"
    "Lahore, Pakistan\n"
    "Posted 1 day ago\n"
    "Laravel Engineer\n"
    "WebWorks\n"
    "Karachi, Pakistan\n"
    "Posted 2 weeks ago\n"
)


def _make_raw_message(
    *,
    message_id: str,
    subject: str,
    html: str,
    plain: str,
    sender: str = "Glassdoor Job Alerts <job-alerts@glassdoor.com>",
    internal_date_ms: int = 1787912100000,
) -> dict:
    """Builds a Gmail API `messages.get` style payload for a Glassdoor job
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


def make_single_job_raw_message(message_id: str = "glassdoor-single-1") -> dict:
    """A single-job Glassdoor alert (spec section 21: Glassdoor single-job email)."""
    return _make_raw_message(
        message_id=message_id,
        subject="1 new job for PHP Developers in Lahore",
        html=SINGLE_HTML,
        plain=SINGLE_PLAIN,
    )


def make_multi_job_raw_message(message_id: str = "glassdoor-digest-1") -> dict:
    """A 3-job Glassdoor digest (spec section 21: Glassdoor multi-job digest)."""
    return _make_raw_message(
        message_id=message_id,
        subject="3 new jobs match your alert",
        html=DIGEST_HTML,
        plain=DIGEST_PLAIN,
    )
