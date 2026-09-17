"""Glassdoor title-link extraction regression test (spec section 13).

CRITICAL FIX: In the real Glassdoor email format, job title is the clickable
link, and company name appears BEFORE the title in the email structure.

This test ensures the parser correctly extracts:
  1. Title from the <a> anchor text
  2. Company from the preceding <p> tag
  3. Location from the following content
  4. URL from the title anchor href

Also asserts that every job has all required fields and no field swapping occurs.
"""

from app.gmail.normalizer import normalize_email
from app.job_alerts.parsers.glassdoor.parser import GlassdoorParser
from tests.fixtures.glassdoor.job_alert_message import (
    make_multi_job_raw_message,
    make_single_job_raw_message,
)


def test_glassdoor_multi_job_digest_extracts_three_complete_jobs() -> None:
    """3 jobs from Glassdoor digest → 3 independent records with title/
    company/location/url all correctly associated."""
    email = normalize_email(make_multi_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    # Exactly 3 jobs extracted.
    assert len(jobs) == 3

    # Job 1: Software Engineer at Kraus Hamdani Aerospace in Fernley, NV
    assert jobs[0].title == "Software Engineer"
    assert jobs[0].company == "Kraus Hamdani Aerospace  1.7 ★"
    assert jobs[0].location == "Fernley, NV"
    assert "D_JO31112001" in jobs[0].job_url
    assert jobs[0].salary == "$61K - $106K"

    # Job 2: Full Stack Developer at Rite Pros in Portland, ME
    assert jobs[1].title == "Full Stack Developer"
    assert jobs[1].company == "Rite Pros (ME)  4.7 ★"
    assert jobs[1].location == "Portland, ME"
    assert "D_JO31112002" in jobs[1].job_url
    assert jobs[1].salary == "$81K - $129K"

    # Job 3: Senior Software Engineer at Valiflo in Logan, UT
    assert jobs[2].title == "Senior Software Engineer"
    assert jobs[2].company == "Valiflo"
    assert jobs[2].location == "Logan, UT"
    assert "D_JO31112003" in jobs[2].job_url


def test_glassdoor_single_job_email_extracts_correctly() -> None:
    """1 job from single-job Glassdoor alert → 1 complete record."""
    email = normalize_email(make_single_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    assert len(jobs) == 1
    assert jobs[0].title == "Senior PHP Developer"
    assert jobs[0].company == "TechCorp  4.2 ★"
    assert jobs[0].location == "Lahore, Pakistan"
    assert "D_JO31112586" in jobs[0].job_url
    assert jobs[0].salary == "PKR 250,000 - 350,000 a month"


def test_glassdoor_no_company_title_swapping() -> None:
    """Assert company and title are never swapped or confused."""
    email = normalize_email(make_multi_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    # Verify no job has company == title (which would indicate swapping).
    for i, job in enumerate(jobs, 1):
        assert job.company != job.title, f"Job {i} has company == title (swapping detected)"
        # Company should not be a typical job title keyword.
        assert "developer" not in job.company.lower() or "rite" in job.company.lower(), \
            f"Job {i} company looks like a title: {job.company}"


def test_glassdoor_all_jobs_have_required_fields() -> None:
    """Every job must have title, location, and job_url. Company is expected."""
    email = normalize_email(make_multi_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    for i, job in enumerate(jobs, 1):
        assert job.title and len(job.title) >= 3, \
            f"Job {i} missing or too-short title: {job.title!r}"
        assert job.company and len(job.company) >= 2, \
            f"Job {i} missing company: {job.company!r}"
        assert job.location and len(job.location) >= 2, \
            f"Job {i} missing location: {job.location!r}"
        assert job.job_url and job.job_url.startswith("http"), \
            f"Job {i} missing or invalid URL: {job.job_url!r}"


def test_glassdoor_each_job_has_distinct_url() -> None:
    """No two jobs share the same URL (dedup/fingerprinting prerequisite)."""
    email = normalize_email(make_multi_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    urls = {job.job_url for job in jobs}
    assert len(urls) == len(jobs), \
        f"Duplicate URLs detected: {len(jobs)} jobs but only {len(urls)} distinct URLs"


def test_glassdoor_each_job_has_distinct_title_and_company() -> None:
    """No two jobs should have identical title/company pairs."""
    email = normalize_email(make_multi_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    pairs = {(job.title, job.company) for job in jobs}
    assert len(pairs) == len(jobs), \
        f"Duplicate title/company pairs: {len(jobs)} jobs but {len(pairs)} distinct pairs"


def test_glassdoor_no_empty_fields() -> None:
    """No job should have None title, company, location, or job_url."""
    email = normalize_email(make_multi_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    for i, job in enumerate(jobs, 1):
        assert job.title is not None, f"Job {i} has None title"
        assert job.company is not None, f"Job {i} has None company"
        assert job.location is not None, f"Job {i} has None location"
        assert job.job_url is not None, f"Job {i} has None job_url"


def test_glassdoor_correct_job_ids_extracted() -> None:
    """Each job must have its own platform job ID extracted from URL."""
    email = normalize_email(make_multi_job_raw_message())
    parser = GlassdoorParser()
    jobs = parser.parse(email)

    # The parser extracts _JO IDs from URLs during finalization.
    assert len(jobs) == 3
    # Job IDs should be distinct.
    ids = {job.platform_job_id for job in jobs}
    assert len(ids) == 3, f"Expected 3 distinct job IDs, got {len(ids)}"
