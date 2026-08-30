import base64


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")


HTML_BODY = """
<html>
  <body>
    <p>5 new Laravel jobs near you</p>
    <a href="https://www.linkedin.com/jobs/view/123456?trk=alert">View Job</a>
    <p>Senior Laravel Developer at ABC Technologies - Remote</p>
    <a href="https://www.linkedin.com/comm/unsubscribe">Unsubscribe</a>
  </body>
</html>
"""

PLAIN_BODY = "5 new Laravel jobs near you\nSenior Laravel Developer at ABC Technologies - Remote\n"

DIGEST_HTML = """<html><body>
  <p>3 new jobs match your alert</p>
  <a href="https://www.linkedin.com/jobs/view/111000001?trk=eml-job_digest">View Job: Backend Developer</a>
  <p>Backend Developer at ABC Technologies - Remote</p>
  <p>Promoted</p>
  <p>Posted 5 hours ago</p>
  <a href="https://www.linkedin.com/comm/jobs/view/111000002?trackingId=abc123">View Job: PHP Developer</a>
  <p>PHP Developer at XYZ Solutions - Lahore, Pakistan</p>
  <p>Posted 1 day ago</p>
  <a href="https://www.linkedin.com/jobs/view/111000003?trk=eml-job_digest">View Job: Laravel Engineer</a>
  <p>Laravel Engineer at WebWorks - Karachi, Pakistan</p>
  <p>Posted 3 days ago</p>
  <a href="https://www.linkedin.com/comm/unsubscribe">Unsubscribe</a>
</body></html>"""

DIGEST_PLAIN = (
    "3 new jobs match your alert\n"
    "Backend Developer at ABC Technologies - Remote\n"
    "Promoted\n"
    "Posted 5 hours ago\n"
    "PHP Developer at XYZ Solutions - Lahore, Pakistan\n"
    "Posted 1 day ago\n"
    "Laravel Engineer at WebWorks - Karachi, Pakistan\n"
    "Posted 3 days ago\n"
)


def make_raw_message(
    message_id: str = "18d2f4a5b6c7d8e9",
    thread_id: str = "18d2f4a5b6c7d8e9",
    sender: str = "LinkedIn Job Alerts <jobs-noreply@linkedin.com>",
    subject: str = "5 new Laravel jobs near you",
    internal_date_ms: int = 1787912100000,  # 2026-08-28 10:15:00 UTC
) -> dict:
    """Builds a Gmail API `messages.get` style payload for a LinkedIn
    job-alert email, for use in normalizer/service tests."""
    return {
        "id": message_id,
        "threadId": thread_id,
        "internalDate": str(internal_date_ms),
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64(PLAIN_BODY)}},
                {"mimeType": "text/html", "body": {"data": _b64(HTML_BODY)}},
            ],
        },
    }


def make_multi_job_raw_message(
    message_id: str = "linkedin-digest-1",
    subject: str = "3 new jobs match your alert",
) -> dict:
    """A 3-job LinkedIn digest (spec section 21: LinkedIn multi-job digest).
    Includes a Promoted badge on the first job and tracking parameters on
    the second job's URL."""
    return {
        "id": message_id,
        "threadId": message_id,
        "internalDate": "1787912100000",  # 2026-08-28 10:15:00 UTC
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {
                    "name": "From",
                    "value": "LinkedIn Job Alerts <jobs-noreply@linkedin.com>",
                },
                {"name": "Subject", "value": subject},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64(DIGEST_PLAIN)}},
                {"mimeType": "text/html", "body": {"data": _b64(DIGEST_HTML)}},
            ],
        },
    }
