from app.gmail.normalizer import normalize_email
from app.job_alerts.parsers.generic.parser import GenericParser
from app.job_alerts.parsers.linkedin.parser import LinkedInParser
from app.job_alerts.parsers.registry import ParserRegistry
from tests.fixtures.linkedin.job_alert_message import make_raw_message


def test_linkedin_parser_supports_linkedin_sender() -> None:
    email = normalize_email(make_raw_message())
    assert LinkedInParser().supports(email) is True


def test_linkedin_parser_extracts_job_id_and_url() -> None:
    email = normalize_email(make_raw_message())
    jobs = LinkedInParser().parse(email)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "linkedin"
    assert job.platform_job_id == "123456"
    assert job.job_url is not None and "linkedin.com/jobs/view/123456" in job.job_url
    assert job.received_at == email.received_at


def test_linkedin_parser_extracts_title_and_company() -> None:
    email = normalize_email(make_raw_message())
    job = LinkedInParser().parse(email)[0]
    assert job.title == "Senior Laravel Developer"
    assert job.company == "ABC Technologies"


def test_generic_parser_always_supports() -> None:
    email = normalize_email(make_raw_message(sender="alerts@some-unknown-platform.example"))
    assert GenericParser().supports(email) is True


def test_registry_falls_back_to_generic_for_unknown_sender() -> None:
    email = normalize_email(make_raw_message(sender="alerts@some-unknown-platform.example"))
    parser = ParserRegistry().get_parser(email)
    assert parser.slug == "generic"


def test_registry_picks_linkedin_parser_for_linkedin_sender() -> None:
    email = normalize_email(make_raw_message())
    parser = ParserRegistry().get_parser(email)
    assert parser.slug == "linkedin"
