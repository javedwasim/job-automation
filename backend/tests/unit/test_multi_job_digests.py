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
