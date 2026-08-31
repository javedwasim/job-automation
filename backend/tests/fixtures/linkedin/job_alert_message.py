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


# Regression fixture: LinkedIn digest where job URLs are embedded DIRECTLY
# on the job title anchors (no separate logo/image link). The parser MUST:
# 1. Identify each title anchor as the job link
# 2. Use its visible text as the title
# 3. Extract the canonical URL and job ID
# 4. Not create duplicate jobs from navigation links
TITLE_ANCHOR_HTML = """<html><head><title>LinkedIn Job Alert</title></head><body>
<p>3 new jobs for: Software Engineer</p>

<!-- ===== Job 1 ===== -->
<div style="margin:16px 0; padding:12px; border:1px solid #ddd;">
  <a href="https://www.linkedin.com/jobs/view/999000001?trk=email-digest&lipi=abc&midToken=def&midSig=ghi">
    Senior Backend Engineer
  </a>
  <p>TechCorp Inc. - San Francisco, CA</p>
  <p>Posted 2 hours ago</p>
</div>

<!-- ===== Job 2 ===== -->
<div style="margin:16px 0; padding:12px; border:1px solid #ddd;">
  <a href="https://www.linkedin.com/jobs/view/999000002?trk=email-digest">
    PHP Laravel Developer
  </a>
  <p>WebDev Solutions - Remote</p>
  <p>Posted 1 day ago</p>
</div>

<!-- ===== Job 3 ===== -->
<div style="margin:16px 0; padding:12px; border:1px solid #ddd;">
  <a href="https://www.linkedin.com/jobs/view/999000003">
    Full Stack Engineer
  </a>
  <p>CloudStart Ltd. - New York, NY</p>
  <p>Posted 3 days ago</p>
</div>

<!-- ===== Navigation links that must NOT become jobs ===== -->
<div style="margin-top:24px; padding-top:12px; border-top:1px solid #ccc;">
  <a href="https://www.linkedin.com/jobs/saved">Your other saved jobs</a> |
  <a href="https://www.linkedin.com/jobs/search">View all jobs</a> |
  <a href="https://www.linkedin.com/jobs/alerts">Manage your job alerts</a> |
  <a href="https://www.linkedin.com/comm/unsubscribe">Unsubscribe</a>
</div>
</body></html>"""

TITLE_ANCHOR_PLAIN = (
    "3 new jobs for: Software Engineer\n"
    "\n"
    "Senior Backend Engineer\n"
    "TechCorp Inc. - San Francisco, CA\n"
    "Posted 2 hours ago\n"
    "\n"
    "PHP Laravel Developer\n"
    "WebDev Solutions - Remote\n"
    "Posted 1 day ago\n"
    "\n"
    "Full Stack Engineer\n"
    "CloudStart Ltd. - New York, NY\n"
    "Posted 3 days ago\n"
    "\n"
    "Your other saved jobs\n"
    "View all jobs\n"
    "Manage your job alerts\n"
    "Unsubscribe\n"
)


def make_title_anchor_raw_message(
    message_id: str = "linkedin-digest-title-anchor",
    subject: str = "3 new jobs for: Software Engineer",
) -> dict:
    """Regression fixture: LinkedIn digest where job URLs are embedded directly
    on title anchors (no separate logo/image link).

    Spec: "For every LinkedIn job block: 1. Find the job-title <a> element.
    2. Use its visible text as title. 3. Use its href as job_url."

    Verifies:
      * 3 jobs extracted (not 1 from first URL)
      * 3 unique titles (Senior Backend Engineer, PHP Laravel Developer, Full Stack Engineer)
      * 3 unique canonical URLs (all tracking params stripped)
      * 3 correct job IDs (999000001, 999000002, 999000003)
      * Navigation links are NOT converted to jobs (Your other saved jobs, View all jobs, etc.)
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
                {"mimeType": "text/plain", "body": {"data": _b64(TITLE_ANCHOR_PLAIN)}},
                {"mimeType": "text/html", "body": {"data": _b64(TITLE_ANCHOR_HTML)}},
            ],
        },
    }


# Realistic LinkedIn digest that reproduces the duplicate/mapping bugs:
#   * ONE job reached through several links — the company_logo image link,
#     the jobcard_body title link and the job_posting CTA link (whose
#     /apply path canonicalizes differently from the title link, so BOTH
#     must collapse into one record keyed by the /jobs/view/<job_id> id),
#   * the SAME job repeated as a second card via a country subdomain
#     (pk.linkedin.com), a trailing slash and originalSubdomain param,
#   * Outlook/MSO conditional comment markup around the layout AND inside
#     a job-card cell ("[if (gte mso 9)|(IE)]", <table>/<tr>/<td>, [endif])
#     that must never leak into any stored field,
#   * LinkedIn's "Pakistan (Remote)" location wording (never a Company),
#   * a card that renders the company line ABOVE the title line (which must
#     not mint the company as the Title), and a "(Hybrid)" location.
DUPLICATE_LINKS_HTML = """<html><head><title>LinkedIn Job Alert</title></head><body>
<!--[if (gte mso 9)|(IE)]>
<table width="600" align="center" cellpadding="0" cellspacing="0" border="0"><tr><td>
<![endif]-->
<p>3 new jobs match your alert</p>

<!-- ===== Job 1: three links for the SAME job ===== -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="60" valign="top">
  <a href="https://www.linkedin.com/comm/jobs/view/4025123456?trk=eml-job_digest-company_logo&amp;lipi=abc">
    <img src="https://media.licdn.com/technova.png" width="48" height="48" alt="TechNova logo">
  </a>
</td><td valign="top">
  <a href="https://www.linkedin.com/comm/jobs/view/4025123456?trk=eml-job_digest-jobcard_body&amp;lipi=abc">Senior Machine Learning Engineer (Remote)</a>
  <p>TechNova</p>
  <p>Pakistan (Remote)</p>
  <p>1 day ago &middot; 25 applicants</p>
</td></tr>
<tr><td colspan="2" style="padding-top:8px;">
  <a href="https://www.linkedin.com/jobs/view/4025123456/apply?trk=eml-job_digest-job_posting" style="background:#0a66c2;color:#fff;padding:8px 12px;">View job</a>
</td></tr></table>

<!-- ===== Job 1 again: the SAME job repeated via a country-subdomain card ===== -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="60" valign="top">
  <a href="https://www.linkedin.com/jobs/view/4025123456/?trk=eml-job_digest-jobcard_body&amp;originalSubdomain=pk">
    <img src="https://media.licdn.com/technova.png" width="48" height="48" alt="">
  </a>
</td><td valign="top">
  <a href="https://pk.linkedin.com/jobs/view/4025123456?trk=eml-job_digest-jobcard_body">Senior Machine Learning Engineer (Remote)</a>
  <p>TechNova</p>
  <p>Pakistan (Remote)</p>
  <p>1 day ago</p>
</td></tr></table>

<!-- ===== Job 2: MSO conditional markup INSIDE the card cell ===== -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td valign="top">
  <!--[if gte mso 9]><table><tr><td>Hilton</td></tr></table><![endif]-->
  <a href="https://www.linkedin.com/comm/jobs/view/4025999888?trk=eml-job_digest-jobcard_body">Lead Full-stack Software Engineer (PHP and React)</a>
  <p>Hilton</p>
  <p>Lahore, Punjab, Pakistan (Remote)</p>
  <p>2 weeks ago &middot; Promoted</p>
</td></tr></table>

<!-- ===== Job 3: company line rendered ABOVE the title line ===== -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td valign="top">
  <p>Valiflo Technologies</p>
  <a href="https://www.linkedin.com/jobs/view/4026000111?trk=eml-job_digest-jobcard_body">Senior Backend Engineer (Python)</a>
  <p>Karachi, Pakistan (Hybrid)</p>
  <p>3 days ago</p>
</td></tr></table>

<!--[if (gte mso 9)|(IE)]>
</td></tr></table>
<![endif]-->
<table role="presentation" width="100%"><tr><td style="font-size:12px;">
  <a href="https://www.linkedin.com/jobs/saved?trk=eml-saved-jobs">Your other saved jobs</a> |
  <a href="https://www.linkedin.com/comm/unsubscribe?trk=eml-unsubscribe">Unsubscribe</a>
</td></tr></table>
</body></html>"""

DUPLICATE_LINKS_PLAIN = (
    "3 new jobs match your alert\n"
    "Senior Machine Learning Engineer (Remote)\n"
    "TechNova\n"
    "Pakistan (Remote)\n"
    "1 day ago · 25 applicants\n"
    "View job\n"
    "Senior Machine Learning Engineer (Remote)\n"
    "TechNova\n"
    "Pakistan (Remote)\n"
    "1 day ago\n"
    "Lead Full-stack Software Engineer (PHP and React)\n"
    "Hilton\n"
    "Lahore, Punjab, Pakistan (Remote)\n"
    "2 weeks ago · Promoted\n"
    "Valiflo Technologies\n"
    "Senior Backend Engineer (Python)\n"
    "Karachi, Pakistan (Hybrid)\n"
    "3 days ago\n"
    "Your other saved jobs\n"
    "Unsubscribe\n"
)


def make_duplicate_links_raw_message(
    message_id: str = "linkedin-digest-duplicate-links",
    subject: str = "3 new jobs match your alert",
) -> dict:
    """Regression fixture for the dashboard bug report:

      * exactly ONE record per job_id no matter how many links (jobcard_body,
        job_posting, company_logo, /comm/ aliases, country subdomains)
        point at the same job,
      * jobcard_body preferred as the primary job link,
      * Title = actual job title, Company = actual company name, and
        location text such as "Pakistan (Remote)" never in Company,
      * Posted = the card's posting date ("1 day ago"), never empty and
        never the email Received timestamp,
      * no MSO conditional HTML in any stored field.
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
                {"mimeType": "text/plain", "body": {"data": _b64(DUPLICATE_LINKS_PLAIN)}},
                {"mimeType": "text/html", "body": {"data": _b64(DUPLICATE_LINKS_HTML)}},
            ],
        },
    }

