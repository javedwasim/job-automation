import base64


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


SINGLE_HTML = """<html><body>
  <p>1 new job for PHP Developers in Lahore</p>
  <p>TechCorp  4.2 ★</p>
  <a href="https://www.glassdoor.com/job-listing/senior-php-developer-techcorp-D_JO31112586.htm?src=GD_EMAIL">Senior PHP Developer</a>
  <p>Lahore, Pakistan</p>
  <p>PKR 250,000 - 350,000 a month</p>
  <p>Full-time</p>
  <p>Posted 5 hours ago</p>
  <a href="https://www.glassdoor.com/partner/jobListing.htm?pos=101&amp;ao=1135430&amp;s=58&amp;src=GD_EMAIL">Easy Apply</a>
</body></html>"""

SINGLE_PLAIN = (
    "1 new job for PHP Developers in Lahore\n"
    "TechCorp  4.2 ★\n"
    "Senior PHP Developer\n"
    "Lahore, Pakistan\n"
    "PKR 250,000 - 350,000 a month\n"
    "Full-time\n"
    "Posted 5 hours ago\n"
    "Easy Apply\n"
)

DIGEST_HTML = """<html><body>
  <p>3 new jobs match your alert</p>
  <p>Kraus Hamdani Aerospace  1.7 ★</p>
  <a href="https://www.glassdoor.com/job-listing/software-engineer-kraus-hamdani-D_JO31112001.htm?src=GD_EMAIL">Software Engineer</a>
  <p>Fernley, NV</p>
  <p>$61K - $106K (Glassdoor est.)</p>
  <p>Posted 3 hours ago</p>
  <a href="https://www.glassdoor.com/partner/easyApply.htm?pos=1&amp;src=GD_EMAIL">Easy Apply</a>
  <p>Rite Pros (ME)  4.7 ★</p>
  <a href="https://www.glassdoor.com/job-listing/full-stack-developer-rite-pros-D_JO31112002.htm?src=GD_EMAIL&amp;guid=track-me">Full Stack Developer</a>
  <p>Portland, ME</p>
  <p>$81K - $129K (Glassdoor est.)</p>
  <p>Posted 1 day ago</p>
  <a href="https://www.glassdoor.com/partner/easyApply.htm?pos=2&amp;src=GD_EMAIL">Easy Apply</a>
  <p>Valiflo</p>
  <a href="https://www.glassdoor.com/job-listing/senior-software-engineer-valiflo-D_JO31112003.htm?src=GD_EMAIL">Senior Software Engineer</a>
  <p>Logan, UT</p>
  <p>Posted 2 weeks ago</p>
  <a href="https://www.glassdoor.com/partner/easyApply.htm?pos=3&amp;src=GD_EMAIL">Easy Apply</a>
</body></html>"""

DIGEST_PLAIN = (
    "3 new jobs match your alert\n"
    "Kraus Hamdani Aerospace  1.7 ★\n"
    "Software Engineer\n"
    "Fernley, NV\n"
    "$61K - $106K (Glassdoor est.)\n"
    "Posted 3 hours ago\n"
    "Easy Apply\n"
    "Rite Pros (ME)  4.7 ★\n"
    "Full Stack Developer\n"
    "Portland, ME\n"
    "$81K - $129K (Glassdoor est.)\n"
    "Posted 1 day ago\n"
    "Easy Apply\n"
    "Valiflo\n"
    "Senior Software Engineer\n"
    "Logan, UT\n"
    "Posted 2 weeks ago\n"
    "Easy Apply\n"
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
