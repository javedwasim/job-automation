"""Multi-job digest tests (spec sections 3, 9, 10, 21) — realistic digest
fixtures for LinkedIn, Indeed and Glassdoor, single-job AND multi-job,
asserting that EVERY job in an email is extracted with its OWN fields:

  1 email with N jobs  ->  N NormalizedJob objects
                          N distinct URLs
                          N per-job titles/companies/locations/dates

Fields are never copied between jobs (spec section 10), dates are computed
relative to the email's received_at (spec section 4), promoted jobs are
flagged but never auto-rejected (spec section 11).
"""

from datetime import UTC, datetime, timedelta

from app.gmail.normalizer import normalize_email
from app.job_alerts.parsers.glassdoor.parser import GlassdoorParser
from app.job_alerts.parsers.indeed.parser import IndeedParser
from app.job_alerts.parsers.linkedin.parser import LinkedInParser
from app.job_alerts.parsers.wellfound.parser import WellfoundParser
from tests.fixtures.glassdoor.job_alert_message import (
    make_multi_job_raw_message as make_glassdoor_multi,
)
from tests.fixtures.glassdoor.job_alert_message import (
    make_single_job_raw_message as make_glassdoor_single,
)
from tests.fixtures.indeed.job_alert_message import (
    make_multi_job_raw_message as make_indeed_multi,
)
from tests.fixtures.indeed.job_alert_message import (
    make_single_job_raw_message as make_indeed_single,
)
from tests.fixtures.linkedin.job_alert_message import (
    make_multi_job_raw_message as make_linkedin_multi,
)
from tests.fixtures.linkedin.job_alert_message import (
    make_raw_message as make_linkedin_single,
)
from tests.fixtures.wellfound import make_multi_job_raw_message as make_wellfound_multi
from tests.fixtures.wellfound import make_single_job_raw_message as make_wellfound_single

RECEIVED_AT = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)


# --- LinkedIn ---------------------------------------------------------------

def test_linkedin_single_job_email_yields_one_complete_job() -> None:
    email = normalize_email(make_linkedin_single())
    jobs = LinkedInParser().parse(email)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Laravel Developer"
    assert job.company == "ABC Technologies"
    assert job.remote_type == "remote"
    assert job.source == "linkedin"
    assert job.platform_job_id == "123456"
    assert job.job_url is not None and "/jobs/view/123456" in job.job_url
    assert job.received_at == email.received_at


def test_linkedin_multi_job_digest_extracts_every_job_and_url() -> None:
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)

    assert len(jobs) == 3
    assert [j.platform_job_id for j in jobs] == ["111000001", "111000002", "111000003"]
    assert [j.title for j in jobs] == [
        "Backend Developer",
        "PHP Developer",
        "Laravel Engineer",
    ]
    assert [j.company for j in jobs] == [
        "ABC Technologies",
        "XYZ Solutions",
        "WebWorks",
    ]
    assert [j.location for j in jobs] == [
        "Remote",
        "Lahore, Pakistan",
        "Karachi, Pakistan",
    ]
    # Every job keeps its OWN url — never the first URL reused.
    assert [j.job_url for j in jobs] == [
        "https://www.linkedin.com/jobs/view/111000001",
        "https://www.linkedin.com/jobs/view/111000002",
        "https://www.linkedin.com/jobs/view/111000003",
    ]
    assert all(j.source == "linkedin" for j in jobs)
    assert all(j.received_at == email.received_at for j in jobs)


def test_linkedin_digest_promoted_job_flagged_not_rejected() -> None:
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)

    assert jobs[0].is_promoted is True
    assert jobs[1].is_promoted is False
    assert jobs[2].is_promoted is False
    # The promoted job's actual posting date was still extracted — freshness
    # will be decided on it, not on the badge.
    assert jobs[0].job_posted_at == RECEIVED_AT - timedelta(hours=5)


def test_linkedin_digest_dates_relative_to_received_at_not_now() -> None:
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)

    assert jobs[0].job_posted_at == RECEIVED_AT - timedelta(hours=5)
    assert jobs[1].job_posted_at == RECEIVED_AT - timedelta(days=1)
    assert jobs[2].job_posted_at == RECEIVED_AT - timedelta(days=3)


# --- Indeed ------------------------------------------------------------------

def test_indeed_single_job_email_yields_one_complete_job() -> None:
    email = normalize_email(make_indeed_single())
    jobs = IndeedParser().parse(email)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "indeed"
    assert job.title == "Senior PHP Developer"
    assert job.company == "TechCorp"
    assert job.location == "Lahore, Pakistan"
    assert job.salary == "$150,000 - $180,000 a year"
    assert job.employment_type == "full-time"
    assert job.platform_job_id == "abc123def456"
    # Tracking params (from/tk) stripped, jk kept — it identifies the job.
    assert job.job_url == "https://www.indeed.com/viewjob?jk=abc123def456"
    assert job.job_posted_at == RECEIVED_AT - timedelta(hours=5)
    assert job.received_at == email.received_at


def test_indeed_multi_job_digest_extracts_every_job_and_url() -> None:
    email = normalize_email(make_indeed_multi())
    jobs = IndeedParser().parse(email)

    assert len(jobs) == 3
    assert [j.platform_job_id for j in jobs] == [
        "jobkey111111",
        "jobkey222222",
        "jobkey333333",
    ]
    assert [j.title for j in jobs] == [
        "Senior PHP Developer",
        "Backend Engineer",
        "Laravel Developer",
    ]
    assert [j.company for j in jobs] == ["TechCorp", "DataSoft", "WebWorks"]
    assert [j.location for j in jobs] == [
        "Lahore, Pakistan",
        "Remote",
        "Karachi, Pakistan",
    ]
    assert [j.remote_type for j in jobs] == [None, "remote", None]
    # Every job keeps its OWN url and OWN jk — never the first URL reused.
    assert [j.job_url for j in jobs] == [
        "https://www.indeed.com/viewjob?jk=jobkey111111",
        "https://www.indeed.com/viewjob?jk=jobkey222222",
        "https://www.indeed.com/viewjob?jk=jobkey333333",
    ]
    # Dates are per-job and relative to received_at, never "now".
    assert [j.job_posted_at for j in jobs] == [
        RECEIVED_AT - timedelta(hours=3),
        RECEIVED_AT - timedelta(days=1),
        RECEIVED_AT - timedelta(weeks=2),
    ]
    assert all(j.received_at == email.received_at for j in jobs)


def test_indeed_digest_extracts_salary_and_employment_type_per_job() -> None:
    email = normalize_email(make_indeed_multi())
    jobs = IndeedParser().parse(email)

    assert jobs[0].salary == "$150,000 - $180,000 a year"
    assert jobs[0].employment_type == "full-time"
    assert jobs[1].salary == "PKR 350,000 - 450,000 a month"
    assert jobs[1].employment_type == "contract"
    assert jobs[2].salary is None  # never copied from another job


# --- Glassdoor ---------------------------------------------------------------

def test_glassdoor_single_job_email_yields_one_complete_job() -> None:
    email = normalize_email(make_glassdoor_single())
    jobs = GlassdoorParser().parse(email)

    assert len(jobs) == 1  # the "Apply Now" partner link is not a second job
    job = jobs[0]
    assert job.source == "glassdoor"
    assert job.title == "Senior PHP Developer"
    assert job.company == "TechCorp"
    assert job.location == "Lahore, Pakistan"
    assert job.salary == "PKR 250,000 - 350,000 a month"
    assert job.employment_type == "full-time"
    assert job.platform_job_id == "31112586"
    assert job.job_url == (
        "https://www.glassdoor.com/job-listing/"
        "senior-php-developer-techcorp-D_JO31112586.htm"
    )
    assert job.job_posted_at == RECEIVED_AT - timedelta(hours=5)
    assert job.received_at == email.received_at


def test_glassdoor_multi_job_digest_extracts_every_job_and_url() -> None:
    email = normalize_email(make_glassdoor_multi())
    jobs = GlassdoorParser().parse(email)

    assert len(jobs) == 3  # the Community footer link is not a job
    assert [j.platform_job_id for j in jobs] == ["31112001", "31112002", "31112003"]
    assert [j.title for j in jobs] == [
        "Backend Developer",
        "PHP Developer",
        "Laravel Engineer",
    ]
    assert [j.company for j in jobs] == [
        "ABC Technologies",
        "XYZ Solutions",
        "WebWorks",
    ]
    assert [j.location for j in jobs] == [
        "Remote",
        "Lahore, Pakistan",
        "Karachi, Pakistan",
    ]
    assert [j.remote_type for j in jobs] == ["remote", None, None]
    # Every job keeps its OWN url/id — tracking params (src/guid) stripped.
    assert [j.job_url for j in jobs] == [
        "https://www.glassdoor.com/job-listing/backend-developer-abc-D_JO31112001.htm",
        "https://www.glassdoor.com/job-listing/php-developer-xyz-D_JO31112002.htm",
        "https://www.glassdoor.com/job-listing/laravel-engineer-webworks-D_JO31112003.htm",
    ]
    assert [j.job_posted_at for j in jobs] == [
        RECEIVED_AT - timedelta(hours=3),
        RECEIVED_AT - timedelta(days=1),
        RECEIVED_AT - timedelta(weeks=2),
    ]
    assert all(j.received_at == email.received_at for j in jobs)


# --- Wellfound ---------------------------------------------------------------


def test_wellfound_single_job_email_yields_one_complete_job() -> None:
    email = normalize_email(make_wellfound_single())
    jobs = WellfoundParser().parse(email)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "wellfound"
    assert job.title == "Senior PHP Developer"
    assert job.company == "TechCorp"
    assert job.location == "Lahore, Pakistan"
    assert job.salary == "$150,000 - $180,000 a year"
    assert job.employment_type == "full-time"
    assert job.platform_job_id == "abc123-senior-php-dev"
    assert job.job_url is not None and "/job-listings/abc123-senior-php-dev" in job.job_url
    # Wellfound alerts rarely state a posting date — job_posted_at stays NULL.
    assert job.job_posted_at is None
    assert job.received_at == email.received_at


def test_wellfound_multi_job_digest_extracts_every_job_and_url() -> None:
    email = normalize_email(make_wellfound_multi())
    jobs = WellfoundParser().parse(email)

    assert len(jobs) == 3
    assert [j.platform_job_id for j in jobs] == [
        "wellfound-111-backend",
        "wellfound-222-php",
        "wellfound-333-laravel",
    ]
    assert [j.title for j in jobs] == [
        "Backend Developer",
        "PHP Developer",
        "Laravel Engineer",
    ]
    assert [j.company for j in jobs] == [
        "ABC Technologies",
        "XYZ Solutions",
        "WebWorks",
    ]
    assert [j.location for j in jobs] == [
        "Remote",
        "Lahore, Pakistan",
        "Karachi, Pakistan",
    ]
    assert [j.remote_type for j in jobs] == ["remote", None, None]
    # Every job keeps its OWN url — never the first URL reused.
    assert [j.job_url for j in jobs] == [
        "https://wellfound.com/job-listings/wellfound-111-backend",
        "https://wellfound.com/job-listings/wellfound-222-php",
        "https://wellfound.com/job-listings/wellfound-333-laravel",
    ]
    # Wellfound rarely states a posting date — all stay NULL (never fabricated).
    assert all(j.job_posted_at is None for j in jobs)
    assert all(j.received_at == email.received_at for j in jobs)


# --- Generic (fallback) ------------------------------------------------------


def test_generic_multi_job_digest_extracts_every_job_and_url() -> None:
    """The fallback GenericParser must ALSO extract every job from a
    multi-job email — it inherits the shared block segmentation, so an
    unrecognized sender's digest with N job links yields N candidates
    (spec section 3: every supported platform, Generic included)."""
    from app.job_alerts.parsers.generic.parser import GenericParser

    email = normalize_email(_generic_multi_job_raw_message())
    jobs = GenericParser().parse(email)

    assert len(jobs) == 3
    assert [j.platform_job_id for j in jobs] == ["20001", "20002", "20003"]
    assert [j.title for j in jobs] == [
        "Backend Developer",
        "PHP Developer",
        "Laravel Engineer",
    ]
    # Every job keeps its OWN url — never the first URL reused.
    assert [j.job_url for j in jobs] == [
        "https://www.linkedin.com/jobs/view/20001",
        "https://www.linkedin.com/jobs/view/20002",
        "https://www.linkedin.com/jobs/view/20003",
    ]
    assert all(j.source == "generic" for j in jobs)
    assert all(j.received_at == email.received_at for j in jobs)


def _generic_multi_job_raw_message() -> dict:
    """A 3-job digest from an unrecognized sender — routed to GenericParser.
    The sender is unknown but the links match known job-posting patterns, so
    the shared extractor treats them as job links."""
    import base64

    def _b64(text: str) -> str:
        return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8").rstrip("=")

    plain = (
        "3 new jobs match your search\n"
        "Backend Developer at ABC Technologies - Remote\n"
        "Posted 3 hours ago\n"
        "PHP Developer at XYZ Solutions - Lahore, Pakistan\n"
        "Posted 1 day ago\n"
        "Laravel Engineer at WebWorks - Karachi, Pakistan\n"
        "Posted 2 weeks ago\n"
    )
    html = """<html><body>
      <p>3 new jobs match your search</p>
      <a href="https://www.linkedin.com/jobs/view/20001?trk=eml-job_digest">
        View Job: Backend Developer
      </a>
      <p>Backend Developer at ABC Technologies - Remote</p>
      <p>Posted 3 hours ago</p>
      <a href="https://www.linkedin.com/jobs/view/20002?trk=eml-job_digest">
        View Job: PHP Developer
      </a>
      <p>PHP Developer at XYZ Solutions - Lahore, Pakistan</p>
      <p>Posted 1 day ago</p>
      <a href="https://www.linkedin.com/jobs/view/20003?trk=eml-job_digest">
        View Job: Laravel Engineer
      </a>
      <p>Laravel Engineer at WebWorks - Karachi, Pakistan</p>
      <p>Posted 2 weeks ago</p>
      <a href="https://www.linkedin.com/comm/unsubscribe">Unsubscribe</a>
    </body></html>"""
    return {
        "id": "generic-digest-1",
        "threadId": "generic-digest-1",
        "internalDate": "1787912100000",  # 2026-08-28 10:15:00 UTC
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Careers Roundup <digest@some-unknown-platform.example>"},
                {"name": "Subject", "value": "3 new jobs match your search"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64(plain)}},
                {"mimeType": "text/html", "body": {"data": _b64(html)}},
            ],
        },
    }
