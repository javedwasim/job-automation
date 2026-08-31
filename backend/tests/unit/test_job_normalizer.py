"""JobNormalizer (spec sections 2, 15) — centralized normalization +
validation tests.

The normalizer is the shared gate EVERY platform candidate passes through:
validation (title + identity anchor), URL canonicalization, platform job-ID
extraction, date resolution and field cleaning happen HERE, never in the
platform parsers.
"""

from datetime import UTC, datetime, timedelta

from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.normalization.job_normalizer import JobNormalizer

RECEIVED_AT = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)


def _job(**overrides) -> NormalizedJob:
    defaults = dict(
        title="Senior PHP Developer",
        company="TechCorp",
        location="Lahore, Pakistan",
        source="linkedin",
        platform_job_id=None,
        job_url="https://www.linkedin.com/jobs/view/123456?trackingId=abc",
        application_url=None,
        job_posted_at=None,
        received_at=RECEIVED_AT,
        description=None,
        source_email_id="msg-1",
    )
    defaults.update(overrides)
    return NormalizedJob(**defaults)


def test_candidate_with_title_and_url_is_valid_and_canonicalized() -> None:
    normalized = JobNormalizer().normalize(_job())

    assert normalized is not None
    assert normalized.job_url == "https://www.linkedin.com/jobs/view/123456"
    assert normalized.platform_job_id == "123456"  # extracted centrally


def test_candidate_without_title_is_rejected() -> None:
    assert JobNormalizer().normalize(_job(title="   ")) is None


def test_candidate_without_url_or_job_id_is_rejected() -> None:
    """Validation requires an identity anchor — a title alone cannot be
    deduplicated or displayed as a real posting."""
    assert JobNormalizer().normalize(_job(job_url=None, platform_job_id=None)) is None


def test_fields_are_stored_without_email_template_markup() -> None:
    """Residual email-template markup (MSO conditionals, tag fragments —
    including ones unescaped out of &lt;...&gt; entities) must never reach a
    stored field; a field that holds nothing but markup becomes empty."""
    normalized = JobNormalizer().normalize(
        _job(
            company="<!--[if (gte mso 9)|(IE)]> <table><tr><td><![endif]--> TechNova",
            location="Pakistan &lt;td&gt;(Remote)",
        )
    )

    assert normalized is not None
    assert normalized.company == "TechNova"
    assert normalized.location == "Pakistan (Remote)"
    for value in (normalized.company, normalized.location):
        for marker in ("[if", "endif", "<", ">"):
            assert marker not in value


def test_markup_only_title_is_rejected_not_stored_raw() -> None:
    """A title that carries no visible text once template markup is stripped
    is not a job — it must be rejected, never stored as raw HTML."""
    assert JobNormalizer().normalize(_job(title="<!--[if gte mso 9]><tr><![endif]-->")) is None


def test_candidate_with_job_id_but_no_url_is_kept() -> None:
    normalized = JobNormalizer().normalize(_job(job_url=None, platform_job_id="123456"))
    assert normalized is not None
    assert normalized.platform_job_id == "123456"


def test_posted_date_phrase_resolved_relative_to_received_at() -> None:
    normalized = JobNormalizer().normalize(_job(posted_date="Posted 3 hours ago"))
    assert normalized is not None
    assert normalized.job_posted_at == RECEIVED_AT - timedelta(hours=3)


def test_unknown_date_never_fabricated_and_never_received_at() -> None:
    normalized = JobNormalizer().normalize(_job(posted_date=None))
    assert normalized is not None
    assert normalized.job_posted_at is None
    assert normalized.job_posted_at != normalized.received_at


def test_fields_are_whitespace_cleaned_and_html_unescaped() -> None:
    normalized = JobNormalizer().normalize(
        _job(title="Senior  PHP &amp; Laravel  Developer", company="  TechCorp \n")
    )
    assert normalized is not None
    assert normalized.title == "Senior PHP & Laravel Developer"
    assert normalized.company == "TechCorp"


def test_rejections_carry_an_explicit_reason() -> None:
    kept, rejected = JobNormalizer().normalize_all(
        [_job(), _job(title="", job_url="https://www.linkedin.com/jobs/view/1")]
    )
    assert len(kept) == 1
    assert len(rejected) == 1
    assert rejected[0].reason == "missing title"


def test_normalize_all_passes_platform_through() -> None:
    normalized = JobNormalizer().normalize(_job(source=""), platform="indeed")
    assert normalized is not None
    assert normalized.source == "indeed"
