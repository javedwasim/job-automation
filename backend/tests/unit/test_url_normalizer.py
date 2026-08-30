"""JobUrlNormalizer (spec section 8) — centralized, platform-aware URL
canonicalization + job-ID extraction tests.

Key requirement: a URL carrying tracking parameters and its clean canonical
form must normalize to the SAME canonical URL and the SAME platform job ID,
while parameters that identify the job (Indeed's jk/vjk) are never stripped.
"""

from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer


def test_linkedin_tracking_parameters_stripped() -> None:
    normalizer = JobUrlNormalizer()
    # The trailing-slash and no-trailing-slash forms are the SAME job
    # (email tracking variants add/drop it), so the canonical form is the
    # no-trailing-slash one.
    assert (
        normalizer.canonical("https://www.linkedin.com/jobs/view/123456789/?trackingId=abc")
        == "https://www.linkedin.com/jobs/view/123456789"
    )


def test_linkedin_comm_alias_and_clean_url_normalize_identically() -> None:
    """/comm/jobs/view/<id> with lipi tracking and /jobs/view/<id>/ must be
    ONE identity (spec: tracking parameters must not create duplicates)."""
    normalizer = JobUrlNormalizer()
    tracked = (
        "https://www.linkedin.com/comm/jobs/view/4456676018"
        "?lipi=urn%3Ali%3Apage%3Aemail_job_digest&midToken=AQGx&midSig=abc&trk=x"
    )
    clean = "https://www.linkedin.com/jobs/view/4456676018/"
    assert normalizer.canonical(tracked) == normalizer.canonical(clean) == (
        "https://www.linkedin.com/jobs/view/4456676018"
    )
    assert normalizer.extract_job_id(tracked) == normalizer.extract_job_id(clean) == (
        "4456676018"
    )


def test_linkedin_trk_and_utm_stripped() -> None:
    normalizer = JobUrlNormalizer()
    assert (
        normalizer.canonical(
            "https://www.linkedin.com/jobs/view/123?trk=eml-job_digest&utm_source=email"
        )
        == "https://www.linkedin.com/jobs/view/123"
    )


def test_linkedin_comm_email_alias_collapses_to_canonical_path() -> None:
    """LinkedIn alert emails link to /comm/jobs/view/<id>; the canonical
    public path is /jobs/view/<id> (spec section 8 example)."""
    normalizer = JobUrlNormalizer()
    assert (
        normalizer.canonical("https://www.linkedin.com/comm/jobs/view/111000002")
        == "https://www.linkedin.com/jobs/view/111000002"
    )


def test_linkedin_job_id_extracted_from_comm_alias_url() -> None:
    normalizer = JobUrlNormalizer()
    assert normalizer.extract_job_id("https://www.linkedin.com/comm/jobs/view/111000002") == (
        "111000002"
    )


def test_tracked_and_clean_urls_normalize_identically() -> None:
    """Spec section 20: 'URL with tracking parameters' and 'canonical URL'
    produce the same normalized URL and job ID."""
    normalizer = JobUrlNormalizer()
    tracked = "https://www.linkedin.com/jobs/view/123456789/?trackingId=abc&trk=x&utm_campaign=y"
    clean = "https://www.linkedin.com/jobs/view/123456789/"
    assert normalizer.canonical(tracked) == normalizer.canonical(clean)
    assert normalizer.extract_job_id(tracked) == normalizer.extract_job_id(clean) == "123456789"


def test_indeed_job_key_parameter_is_required_never_stripped() -> None:
    """jk/vjk identify the actual job — they must survive normalization
    (spec section 8: do NOT remove query params blindly)."""
    normalizer = JobUrlNormalizer()
    url = "https://www.indeed.com/viewjob?jk=jobkey111111&from=alertemail&tk=1h9z2x"
    canonical = normalizer.canonical(url, "indeed")
    assert "jk=jobkey111111" in canonical
    assert "from=" not in canonical
    assert "tk=" not in canonical
    assert normalizer.extract_job_id(url, "indeed") == "jobkey111111"


def test_indeed_vjk_job_key_preserved_and_extracted() -> None:
    normalizer = JobUrlNormalizer()
    url = "https://www.indeed.com/rc/clk?jk=abc123&vjk=def456&from=email"
    assert normalizer.extract_job_id(url, "indeed") == "abc123"
    canonical = normalizer.canonical(url, "indeed")
    assert "vjk=def456" in canonical


def test_glassdoor_job_id_extracted_from_listing_filename() -> None:
    normalizer = JobUrlNormalizer()
    url = "https://www.glassdoor.com/job-listing/php-developer-xyz-D_JO31112002.htm"
    assert normalizer.extract_job_id(url, "glassdoor") == "31112002"


def test_glassdoor_tracking_parameters_stripped() -> None:
    normalizer = JobUrlNormalizer()
    canonical = normalizer.canonical(
        "https://www.glassdoor.com/job-listing/dev-D_JO31112002.htm?src=GD_EMAIL&guid=track-me",
        "glassdoor",
    )
    assert canonical == "https://www.glassdoor.com/job-listing/dev-D_JO31112002.htm"


def test_parameter_order_never_changes_the_canonical_form() -> None:
    normalizer = JobUrlNormalizer()
    a = normalizer.canonical("https://x.example/viewjob?jk=1&foo=bar", "indeed")
    b = normalizer.canonical("https://x.example/viewjob?foo=bar&jk=1", "indeed")
    assert a == b


def test_fragment_and_uppercase_host_normalized() -> None:
    normalizer = JobUrlNormalizer()
    assert (
        normalizer.canonical("HTTPS://WWW.LinkedIn.COM/jobs/view/42#posted")
        == "https://www.linkedin.com/jobs/view/42"
    )


def test_unknown_platform_keeps_unknown_params_and_yields_no_id() -> None:
    """Unknown parameters are kept (they may be required to identify the
    job) and no platform job ID is guessed."""
    normalizer = JobUrlNormalizer()
    url = "https://jobs.example.com/listing/99?token=keepme"
    assert normalizer.canonical(url) == "https://jobs.example.com/listing/99?token=keepme"
    assert normalizer.extract_job_id(url) is None


def test_empty_inputs_are_safe() -> None:
    normalizer = JobUrlNormalizer()
    assert normalizer.canonical("") == ""
    assert normalizer.extract_job_id(None) is None
    assert normalizer.extract_job_id("") is None
