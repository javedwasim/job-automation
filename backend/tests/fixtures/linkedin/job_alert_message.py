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


# Realistic LinkedIn multi-job digest HTML.  The body intentionally mixes:
#   * real job cards (3) with title/company/location/posted-date and a
#     "View Job" anchor each,
#   * navigation / footer / utility links ("Your other saved jobs",
#     "View all jobs", "Manage alerts", "Notification settings",
#     "Email preferences", "Privacy Policy", "Terms of Service",
#     "Unsubscribe", LinkedIn home, Jobs home),
#   * tracking / redirect links (LinkedIn's gld.la shortener),
#   * a logo link,
#   * partial text fragments that must never become job titles.
DIGEST_HTML = """<html><head><title>LinkedIn Job Alert</title></head><body>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td>
  <a href="https://www.linkedin.com/feed/?trk=eml-job-digest-logo">
    <img src="https://media.linkedin.com/logo.png" alt="LinkedIn" width="120" height="28">
  </a>
</td></tr></table>

<p style="font-size:16px;">5 new jobs match your alert</p>
<p>New jobs for: Senior Software Engineer</p>

<!-- ===== Job 1 ===== -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
<tr><td>
  <a href="https://www.linkedin.com/jobs/view/111000001?trk=eml-job_digest&lipi=12345&midToken=abc&midSig=def">
    <img src="https://media.linkedin.com/job1.png" alt="" width="60" height="60">
  </a>
</td><td width="12">
  <a href="https://www.linkedin.com/comm/jobs/view/111000001">Sr. Backend Engineer at CoRecruit (formerly Quil) - San Francisco, CA</a>
</td></tr>
<tr><td colspan="2">
  <span style="color:#b00020;font-weight:bold;">Promoted</span>
  &middot; Posted 2 hours ago &middot; Remote
</td></tr>
<tr><td colspan="2">
  <a href="https://www.linkedin.com/comm/jobs/view/111000001?trk=jobdetails-apply" style="background:#0a66c2;color:#fff;padding:8px 12px;text-decoration:none;">Apply now</a>
  <a href="https://www.linkedin.com/comm/jobs/view/111000001?trk=jobdetails-save" style="margin-left:8px;">Save job</a>
</td></tr>
</table>

<!-- ===== Job 2 ===== -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
<tr><td>
  <a href="https://www.linkedin.com/jobs/view/111000002">
    <img src="https://media.linkedin.com/job2.png" alt="" width="60" height="60">
  </a>
</td><td width="12">
  <a href="https://www.linkedin.com/comm/jobs/view/111000002">Lead Full-stack Software Engineer (PHP and React) at Hilton - Remote</a>
</td></tr>
<tr><td colspan="2">
  Posted 1 day ago &middot; Hybrid
</td></tr>
</table>

<!-- ===== Job 3 ===== -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;">
<tr><td>
  <a href="https://www.linkedin.com/jobs/view/111000003">
    <img src="https://media.linkedin.com/job3.png" alt="" width="60" height="60">
  </a>
</td><td width="12">
  <a href="https://www.linkedin.com/comm/jobs/view/111000003">Senior WordPress Backend Developer at Teal Media - Lahore, Pakistan</a>
</td></tr>
<tr><td colspan="2">
  Posted 3 days ago
</td></tr>
</table>

<!-- ===== Navigation / footer links ===== -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;border-top:1px solid #ccc;padding-top:16px;">
<tr><td>
  <a href="https://www.linkedin.com/jobs/view/111000001?trk=recommended-jobs">Recommended jobs</a>
  &nbsp;|&nbsp;
  <a href="https://www.linkedin.com/jobs/saved?trk=eml-saved-jobs">Your other saved jobs</a>
  &nbsp;|&nbsp;
  <a href="https://www.linkedin.com/jobs/search?trk=eml-view-all-jobs">View all jobs</a>
  &nbsp;|&nbsp;
  <a href="https://www.linkedin.com/jobs/alerts?trk=eml-manage-alerts">Manage your job alerts</a>
</td></tr>
<tr><td style="padding-top:8px;">
  <a href="https://www.linkedin.com/mynetwork?trk=eml-notifications">Notification settings</a>
  &nbsp;|&nbsp;
  <a href="https://www.linkedin.com/psettings?trk=eml-email-prefs">Email preferences</a>
  &nbsp;|&nbsp;
  <a href="https://www.linkedin.com/psettings/member-data?trk=eml-data">Privacy Policy</a>
  &nbsp;|&nbsp;
  <a href="https://www.linkedin.com/lite/terms?trk=eml-terms">Terms of Service</a>
  &nbsp;|&nbsp;
  <a href="https://gld.la/abc123">Recent jobs</a>
  &nbsp;|&nbsp;
  <a href="https://www.linkedin.com/comm/unsubscribe?trk=eml-unsubscribe">Unsubscribe</a>
</td></tr>
<tr><td style="padding-top:8px;font-size:12px;color:#666;">
  LinkedIn Corporation, 2029 Stierlin Court, Mountain View, CA 94043
</td></tr>
</table>
</body></html>"""

DIGEST_PLAIN = (
    "5 new jobs match your alert\n"
    "New jobs for: Senior Software Engineer\n"
    "\n"
    "Sr. Backend Engineer at CoRecruit (formerly Quil) - San Francisco, CA\n"
    "Promoted\n"
    "Posted 2 hours ago\n"
    "Remote\n"
    "Apply now\n"
    "Save job\n"
    "\n"
    "Lead Full-stack Software Engineer (PHP and React) at Hilton - Remote\n"
    "Posted 1 day ago\n"
    "Hybrid\n"
    "\n"
    "Senior WordPress Backend Developer at Teal Media - Lahore, Pakistan\n"
    "Posted 3 days ago\n"
    "\n"
    "Recommended jobs\n"
    "Your other saved jobs\n"
    "View all jobs\n"
    "Manage your job alerts\n"
    "Notification settings\n"
    "Email preferences\n"
    "Privacy Policy\n"
    "Terms of Service\n"
    "Unsubscribe\n"
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
    subject: str = "5 new jobs match your alert",
) -> dict:
    """A 3-job LinkedIn digest with realistic navigation/footer/tracking links.

    Spec section 21: LinkedIn multi-job digest.  Contains:
      * 3 real job cards (Sr. Backend Engineer, Lead Full-stack Engineer,
        Senior WordPress Backend Developer),
      * Promoted badge on the first job,
      * tracking parameters (lipi, midToken, midSig, trk) on job 1's URLs,
      * a /comm/ alias URL on jobs 1 and 2,
      * navigation/footer links that must NOT become jobs:
        "Your other saved jobs", "View all jobs", "Manage your job alerts",
        "Notification settings", "Email preferences", "Privacy Policy",
        "Terms of Service", "Unsubscribe", "Recommended jobs",
        a gld.la tracking link, and a logo image link,
      * Apply now / Save job CTA anchors that share job URLs.
    """
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
