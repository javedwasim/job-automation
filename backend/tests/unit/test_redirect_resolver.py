import pytest

from app.job_alerts.extraction.redirect_resolver import RedirectResolver, SSRFError


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/internal",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",  # cloud metadata endpoint
        "http://10.0.0.5/internal",
        "http://192.168.1.1/router",
        "ftp://example.com/file",
    ],
)
def test_validate_url_is_safe_rejects_unsafe_targets(url: str) -> None:
    resolver = RedirectResolver()
    with pytest.raises(SSRFError):
        resolver._validate_url_is_safe(url)


def test_validate_url_is_safe_allows_public_https() -> None:
    resolver = RedirectResolver()
    # example.com resolves publicly; should not raise.
    resolver._validate_url_is_safe("https://example.com/jobs/123")
