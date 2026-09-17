from app.jobs.fingerprinting.job_fingerprint_service import JobFingerprintService, normalize_job_url


def test_normalize_job_url_strips_utm_and_tracking_params() -> None:
    url = "https://www.linkedin.com/jobs/view/123?utm_source=email&utm_medium=alert&trk=abc"
    assert normalize_job_url(url) == "https://www.linkedin.com/jobs/view/123"


def test_same_job_different_tracking_params_fingerprints_identically() -> None:
    service = JobFingerprintService()
    fp1 = service.fingerprint(
        platform="linkedin",
        job_url="https://www.linkedin.com/jobs/view/123?utm_source=a",
        title="Senior Laravel Developer",
        company="ABC",
    )
    fp2 = service.fingerprint(
        platform="linkedin",
        job_url="https://www.linkedin.com/jobs/view/123?utm_source=b&trk=xyz",
        title="Senior Laravel Developer",
        company="ABC",
    )
    assert fp1 == fp2


def test_different_jobs_fingerprint_differently() -> None:
    service = JobFingerprintService()
    fp1 = service.fingerprint(
        platform="linkedin",
        job_url="https://www.linkedin.com/jobs/view/123",
        title="A",
        company="X",
    )
    fp2 = service.fingerprint(
        platform="linkedin",
        job_url="https://www.linkedin.com/jobs/view/456",
        title="B",
        company="Y",
    )
    assert fp1 != fp2


def test_falls_back_to_title_company_when_no_url() -> None:
    service = JobFingerprintService()
    fp1 = service.fingerprint(platform="generic", job_url=None, title="Backend Dev", company="Acme")
    fp2 = service.fingerprint(platform="generic", job_url=None, title="Backend Dev", company="Acme")
    assert fp1 == fp2
