from datetime import UTC, datetime

from app.gmail.dto import EmailLink, NormalizedEmail
from app.job_alerts.parsers.glassdoor.parser import GlassdoorParser
from app.job_alerts.parsers.registry import ParserRegistry


def make_glassdoor_email(
    links: list[EmailLink],
    subject: str = "12 new jobs for PHP Developers in Lahore | Glassdoor",
    plain_text: str = "12 new jobs match your alert",
) -> NormalizedEmail:
    return NormalizedEmail(
        gmail_message_id="gd-msg-1",
        thread_id=None,
        sender="Glassdoor Job Alerts <job-alerts@glassdoor.com>",
        subject=subject,
        received_at=datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
        plain_text=plain_text,
        html=None,
        links=links,
    )


def test_glassdoor_parser_supports_glassdoor_sender() -> None:
    assert GlassdoorParser().supports(make_glassdoor_email([])) is True


def test_registry_picks_glassdoor_parser_for_glassdoor_sender() -> None:
    parser = ParserRegistry().get_parser(make_glassdoor_email([]))
    assert parser.slug == "glassdoor"


def test_glassdoor_parser_extracts_job_listing_url_and_id() -> None:
    email = make_glassdoor_email(
        [
            EmailLink(url="https://www.glassdoor.com/overview/ABC-Reviews-SRCH_KE0,5.htm"),
            EmailLink(
                url=(
                    "https://www.glassdoor.com/partner/jobListing.htm"
                    "?pos=101&ao=1135430&s=58&src=GD_EMAIL"
                ),
                anchor_text="Senior Backend Developer at TechCorp",
            ),
        ],
        plain_text=(
            "12 new jobs match your alert\n"
            "Senior Backend Developer at TechCorp\n"
            "Lahore, Pakistan\n"
            "Posted 3 hours ago\n"
            "Apply Now"
        ),
    )
    jobs = GlassdoorParser().parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "glassdoor"
    assert "glassdoor.com/partner/jobListing.htm" in (job.job_url or "")
    assert job.platform_job_id is None  # partner links carry no _JO id
    assert job.title == "Senior Backend Developer"
    assert job.company == "TechCorp"
    assert job.location == "Lahore, Pakistan"
    assert job.received_at == email.received_at


def test_glassdoor_parser_extracts_job_id_from_listing_path() -> None:
    email = make_glassdoor_email(
        [
            EmailLink(
                url="https://www.glassdoor.com/job-listing/php-developer-abc-D_JO31112586.htm",
                anchor_text="PHP Developer at ABC",
            )
        ],
        plain_text=(
            "PHP Developer at ABC\n"
            "Lahore, Pakistan\n"
            "Easy Apply\n"
            "Posted 1 day ago"
        ),
    )
    job = GlassdoorParser().parse(email)[0]
    assert job.platform_job_id == "31112586"
    assert job.title == "PHP Developer"
    assert job.company == "ABC"


def test_glassdoor_digest_header_only_email_does_not_fabricate_pseudo_job() -> None:
    """Spec sections 3/18: a digest header is NOT a job. The old behavior
    minted one pseudo-job titled '12 new jobs for PHP Developers in Lahore'
    from the subject — that must never happen; blocks without job-like
    content produce zero candidates."""
    email = make_glassdoor_email(
        [
            EmailLink(
                url=(
                    "https://www.glassdoor.com/partner/jobListing.htm"
                    "?pos=101&ao=1135430&s=58&src=GD_EMAIL"
                ),
                anchor_text="Apply Now",
            ),
        ],
        plain_text="12 new jobs match your alert",
    )
    assert GlassdoorParser().parse(email) == []


def test_glassdoor_parser_ignores_non_job_emails() -> None:
    email = make_glassdoor_email(
        [
            EmailLink(url="https://www.glassdoor.com/Reviews/ABC-Reviews-SRCH_KE0,5.htm"),
            EmailLink(url="https://www.glassdoor.com/Salary/Lahore-Salary-SRCH_IL.0,6_IC.htm"),
            EmailLink(url="https://www.glassdoor.com/blog/weekly/"),
        ]
    )
    assert GlassdoorParser().parse(email) == []