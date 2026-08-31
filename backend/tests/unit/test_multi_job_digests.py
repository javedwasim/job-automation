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
    make_duplicate_links_raw_message as make_linkedin_duplicate_links,
)
from tests.fixtures.linkedin.job_alert_message import (
    make_multi_job_raw_message as make_linkedin_multi,
)
from tests.fixtures.linkedin.job_alert_message import (
    make_raw_message as make_linkedin_single,
)
from tests.fixtures.linkedin.job_alert_message import (
    make_title_anchor_raw_message as make_linkedin_title_anchor,
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
        "Sr. Backend Engineer",
        "Lead Full-stack Software Engineer (PHP and React)",
        "Senior WordPress Backend Developer",
    ]
    assert [j.company for j in jobs] == [
        "CoRecruit (formerly Quil)",
        "Hilton",
        "Teal Media",
    ]
    assert [j.location for j in jobs] == [
        "San Francisco, CA",
        "Remote",
        "Lahore, Pakistan",
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
    assert jobs[0].job_posted_at == RECEIVED_AT - timedelta(hours=2)
    assert jobs[0].title == "Sr. Backend Engineer"


def test_linkedin_digest_dates_relative_to_received_at_not_now() -> None:
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)

    assert jobs[0].job_posted_at == RECEIVED_AT - timedelta(hours=2)
    assert jobs[1].job_posted_at == RECEIVED_AT - timedelta(days=1)
    assert jobs[2].job_posted_at == RECEIVED_AT - timedelta(days=3)


def test_linkedin_regression_title_anchor_urls_embedded_directly() -> None:
    """Regression: job URLs embedded directly on title anchors (no separate
    logo/image link).

    Requirement: For every LinkedIn job block:
      1. Find the job-title <a> element.
      2. Use its visible text as title.
      3. Use its href as job_url.
      4. Extract job_id and canonicalize URL.
      5. Keep title and URL associated with the SAME job.
      6. Return EVERY job, not only the first one.

    Must NOT create jobs from navigation links (Your other saved jobs, View
    all jobs, Manage your job alerts, Unsubscribe).
    """
    email = normalize_email(make_linkedin_title_anchor())
    jobs = LinkedInParser().parse(email)

    # Verify 3 jobs extracted (not 1 from first URL, not fake jobs from nav links).
    assert len(jobs) == 3, f"Expected 3 jobs, got {len(jobs)}"

    # Verify 3 unique titles.
    titles = [j.title for j in jobs]
    assert titles == [
        "Senior Backend Engineer",
        "PHP Laravel Developer",
        "Full Stack Engineer",
    ], f"Got titles: {titles}"
    assert len(set(titles)) == 3, "Job titles must be unique"

    # Verify 3 unique canonical URLs (tracking params stripped, all normalize to /jobs/view/ID).
    urls = [j.job_url for j in jobs]
    assert [
        "https://www.linkedin.com/jobs/view/999000001",
        "https://www.linkedin.com/jobs/view/999000002",
        "https://www.linkedin.com/jobs/view/999000003",
    ] == urls, f"Got URLs: {urls}"
    assert len(set(urls)) == 3, "Job URLs must be unique"

    # Verify 3 correct job IDs.
    job_ids = [j.platform_job_id for j in jobs]
    assert job_ids == ["999000001", "999000002", "999000003"], f"Got job IDs: {job_ids}"

    # Verify companies extracted.
    companies = [j.company for j in jobs]
    assert companies == [
        "TechCorp Inc.",
        "WebDev Solutions",
        "CloudStart Ltd.",
    ], f"Got companies: {companies}"

    # Verify locations extracted.
    locations = [j.location for j in jobs]
    assert locations == [
        "San Francisco, CA",
        "Remote",
        "New York, NY",
    ], f"Got locations: {locations}"

    # Verify no navigation-link garbage becomes jobs.
    nav_phrases = ["Your other saved jobs", "View all jobs", "Manage your job alerts", "Unsubscribe"]
    for phrase in nav_phrases:
        for job in jobs:
            assert job.title != phrase, f"Navigation phrase '{phrase}' became a job title"


# --- LinkedIn garbage-link rejection (spec section 3: a URL alone is not a job) ---


# Navigation footer phrases that must NEVER become job titles or jobs.
GARBAGE_TITLES = [
    "ailable.", "still av", "ners is", "ty Part", "Equi", "ogy",
    "at Tril", "job", "ved", "Your sa",
]
GARBAGE_ANCHOR_TEXTS = [
    "Your other saved jobs", "View all jobs", "See more jobs", "Manage your job alerts",
    "Manage alerts", "Notification settings", "Email preferences", "Privacy Policy",
    "Terms of Service", "Unsubscribe", "Recommended jobs", "Recent jobs",
]


def test_linkedin_digest_rejects_garbage_navigation_links() -> None:
    """Test 1 — navigation/footer/tracking links must not become jobs."""
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)
    assert len(jobs) == 3  # exactly the 3 real jobs

    # No garbage titles appear.
    for job in jobs:
        assert job.title not in GARBAGE_TITLES
        assert job.title not in GARBAGE_ANCHOR_TEXTS

    # No navigation URLs appear.
    for job in jobs:
        url = job.job_url or ""
        assert "linkedin.com/jobs/saved" not in url
        assert "linkedin.com/jobs/search" not in url
        assert "linkedin.com/jobs/alerts" not in url
        assert "linkedin.com/mynetwork" not in url
        assert "linkedin.com/psettings" not in url
        assert "linkedin.com/feed" not in url
        assert "gld.la" not in url
        assert "unsubscribe" not in url.lower()


def test_linkedin_digest_correct_titles() -> None:
    """Test 3 — valid jobs have correct titles."""
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)
    titles = [j.title for j in jobs]
    assert "Sr. Backend Engineer" in titles
    assert "Lead Full-stack Software Engineer (PHP and React)" in titles
    assert "Senior WordPress Backend Developer" in titles


def test_linkedin_digest_correct_url_association() -> None:
    """Test 4 — title corresponds to the same job as the URL."""
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)
    for job in jobs:
        # Each job_id must correspond to the correct title.
        if job.platform_job_id == "111000001":
            assert "Sr. Backend Engineer" in (job.title or "")
        elif job.platform_job_id == "111000002":
            assert "Lead Full-stack" in (job.title or "")
        elif job.platform_job_id == "111000003":
            assert "Senior WordPress" in (job.title or "")


def test_linkedin_digest_tracking_param_dedup() -> None:
    """Test 5 — tracking params must not create duplicates."""
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)
    # Job 1 appears via /comm/ alias with tracking params — must collapse
    # to one canonical URL + one ID.
    urls = [j.job_url for j in jobs]
    # /comm/ variant and tracking params must normalize to the same canonical URL.
    assert "https://www.linkedin.com/jobs/view/111000001" in urls
    # No URL should have tracking params.
    for url in urls:
        assert "trk=" not in url
        assert "lipi=" not in url
        assert "midToken=" not in url
        assert "midSig=" not in url
        assert "/comm/" not in url
    # Exactly one record per job ID.
    job_ids = [j.platform_job_id for j in jobs]
    assert len(job_ids) == len(set(job_ids))


def test_linkedin_digest_no_duplicates() -> None:
    """All job URLs are unique after canonicalization."""
    email = normalize_email(make_linkedin_multi())
    jobs = LinkedInParser().parse(email)
    urls = [j.job_url for j in jobs]
    assert len(urls) == len(set(urls))


def test_linkedin_multi_link_card_yields_one_record_per_job_id() -> None:
    """One job reached through several links — company_logo image link,
    jobcard_body title link, job_posting CTA — PLUS the same job repeated
    as a second card via a country subdomain must produce exactly ONE
    record per /jobs/view/<job_id>, with the jobcard_body link as the
    primary (canonicalized) job link."""
    email = normalize_email(make_linkedin_duplicate_links())
    jobs = LinkedInParser().parse(email)

    # Exactly one record per job_id — never a second one for 4025123456.
    job_ids = [j.platform_job_id for j in jobs]
    assert job_ids == ["4025123456", "4025999888", "4026000111"]
    assert len(job_ids) == len(set(job_ids))

    duplicated = jobs[0]
    # The surviving link is the jobcard_body URL, canonicalized:
    # tracking stripped, /comm/ collapsed, country subdomain normalized,
    # /apply CTA variant deduplicated away.
    assert duplicated.job_url == "https://www.linkedin.com/jobs/view/4025123456"
    assert "trk=" not in (duplicated.job_url or "")

    # Correct field mapping for the duplicated job.
    assert duplicated.title == "Senior Machine Learning Engineer (Remote)"
    assert duplicated.company == "TechNova"
    assert duplicated.location == "Pakistan (Remote)"
    assert duplicated.remote_type == "remote"
    assert duplicated.source == "linkedin"

    # Posted is the card's posting date resolved against the email's own
    # received_at — never empty, never the Received timestamp.
    assert duplicated.posted_date == "1 day ago"
    assert duplicated.job_posted_at == RECEIVED_AT - timedelta(days=1)
    assert duplicated.received_at == RECEIVED_AT


def test_linkedin_mso_conditional_html_never_leaks_into_fields() -> None:
    """Outlook/MSO conditional comment markup ("[if (gte mso 9)|(IE)]",
    "<table ...>", "<tr>", "<td>", "[endif]") must never reach any stored
    field — even when the markup sits INSIDE a job-card cell."""
    forbidden = ("[if", "<table", "<tr>", "<td>", "endif", "<!--", "&lt;")
    email = normalize_email(make_linkedin_duplicate_links())
    jobs = LinkedInParser().parse(email)

    assert len(jobs) == 3
    for job in jobs:
        for value in (
            job.title,
            job.company,
            job.location,
            job.salary,
            job.employment_type,
            job.description,
        ):
            assert value is None or not any(marker in value for marker in forbidden), value

    # The card whose cell contains MSO conditional markup still maps its
    # fields to the REAL values — the template markup cannot displace them.
    by_id = {j.platform_job_id: j for j in jobs}
    job = by_id["4025999888"]
    assert job.title == "Lead Full-stack Software Engineer (PHP and React)"
    assert job.company == "Hilton"
    assert job.location == "Lahore, Punjab, Pakistan (Remote)"
    assert job.is_promoted is True
    assert job.job_posted_at == RECEIVED_AT - timedelta(weeks=2)


def test_linkedin_company_first_card_maps_title_and_company_correctly() -> None:
    """A card that renders the company line ABOVE the title line must not
    mint the company as the Title (nor the title as the Company): the
    job-title anchor's visible text wins, and company/location are
    re-derived from the remaining card lines."""
    email = normalize_email(make_linkedin_duplicate_links())
    jobs = LinkedInParser().parse(email)
    by_id = {j.platform_job_id: j for j in jobs}

    job = by_id["4026000111"]
    assert job.title == "Senior Backend Engineer (Python)"
    assert job.company == "Valiflo Technologies"
    assert job.location == "Karachi, Pakistan (Hybrid)"
    assert job.remote_type == "hybrid"
    assert job.job_posted_at == RECEIVED_AT - timedelta(days=3)
    assert job.job_url == "https://www.linkedin.com/jobs/view/4026000111"


# --- Indeed garbage-link rejection (spec section 3: a URL alone is not a job) ---


def test_title_like_rejects_text_split_fragments() -> None:
    """Test 2 — fragments produced by arbitrary text splitting are rejected
    as titles (e.g. "ailable.", "still av", "ners is")."""
    from app.job_alerts.parsers.base_parser import BaseJobAlertParser

    parser = BaseJobAlertParser.__new__(BaseJobAlertParser)
    # These are the garbage titles from the dashboard bug report.
    for garbage in ["ailable.", "still av", "ners is", "ty Part",
                     "Equi", "ogy", "at Tril", "job", "ved", "Your sa"]:
        # Short fragments with trailing punctuation are rejected.
        assert not parser._is_title_like(garbage), f"should reject: {garbage!r}"
    # Real titles survive.
    for title in ["Sr. Backend Engineer", "Lead Full-stack Software Engineer",
                   "Senior WordPress Backend Developer", "Software Engineer"]:
        assert parser._is_title_like(title), f"should accept: {title!r}"


def test_indeed_digest_rejects_garbage_navigation_links() -> None:
    """Indeed: navigation/footer/tracking links must not become jobs."""
    email = normalize_email(make_indeed_multi())
    jobs = IndeedParser().parse(email)
    assert len(jobs) == 3  # exactly the 3 real jobs (fixture-dependent)

    for job in jobs:
        assert job.title not in GARBAGE_TITLES
        url = job.job_url or ""
        assert "clk.indeed.com/hp" not in url
        assert "viewall" not in url.lower()
        assert "unsubscribe" not in url.lower()


def test_indeed_digest_correct_titles_and_urls() -> None:
    """Indeed: correct titles with correct URL association."""
    email = normalize_email(make_indeed_multi())
    jobs = IndeedParser().parse(email)
    assert len(jobs) == 3

    for job in jobs:
        assert job.title is not None
        assert len(job.title) >= 3
        assert job.platform_job_id is not None
        assert job.job_url is not None

    # URLs are unique.
    urls = [j.job_url for j in jobs]
    assert len(urls) == len(set(urls))


# --- Glassdoor garbage-link rejection (spec section 3: a URL alone is not a job) ---


def test_glassdoor_digest_rejects_garbage_navigation_links() -> None:
    """Glassdoor: navigation/footer/tracking links must not become jobs."""
    email = normalize_email(make_glassdoor_multi())
    jobs = GlassdoorParser().parse(email)
    assert len(jobs) == 3  # exactly the 3 real jobs (fixture-dependent)

    for job in jobs:
        assert job.title not in GARBAGE_TITLES
        url = job.job_url or ""
        assert "glassdoor.com/reviews" not in url
        assert "glassdoor.com/salary" not in url
        assert "glassdoor.com/profile" not in url
        assert "unsubscribe" not in url.lower()


def test_glassdoor_digest_correct_titles_and_urls() -> None:
    """Glassdoor: correct titles with correct URL association."""
    email = normalize_email(make_glassdoor_multi())
    jobs = GlassdoorParser().parse(email)
    assert len(jobs) == 3

    for job in jobs:
        assert job.title is not None
        assert len(job.title) >= 3
        assert job.platform_job_id is not None
        assert job.job_url is not None

    urls = [j.job_url for j in jobs]
    assert len(urls) == len(set(urls))


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

    assert len(jobs) == 1  # the "Easy Apply" partner link is not a second job
    job = jobs[0]
    assert job.source == "glassdoor"
    assert job.title == "Senior PHP Developer"
    assert job.company == "TechCorp  4.2 ★"
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

    assert len(jobs) == 3
    assert [j.platform_job_id for j in jobs] == ["31112001", "31112002", "31112003"]
    assert [j.title for j in jobs] == [
        "Software Engineer",
        "Full Stack Developer",
        "Senior Software Engineer",
    ]
    assert [j.company for j in jobs] == [
        "Kraus Hamdani Aerospace  1.7 ★",
        "Rite Pros (ME)  4.7 ★",
        "Valiflo",
    ]
    assert [j.location for j in jobs] == [
        "Fernley, NV",
        "Portland, ME",
        "Logan, UT",
    ]
    assert [j.remote_type for j in jobs] == [None, None, None]
    # Every job keeps its OWN url/id — tracking params (src/guid) stripped.
    assert [j.job_url for j in jobs] == [
        "https://www.glassdoor.com/job-listing/software-engineer-kraus-hamdani-D_JO31112001.htm",
        "https://www.glassdoor.com/job-listing/full-stack-developer-rite-pros-D_JO31112002.htm",
        "https://www.glassdoor.com/job-listing/senior-software-engineer-valiflo-D_JO31112003.htm",
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
