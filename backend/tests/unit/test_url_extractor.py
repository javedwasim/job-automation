from app.gmail.dto import EmailLink
from app.job_alerts.extraction.url_extractor import UrlExtractor


def test_prefers_view_job_anchor_over_unsubscribe() -> None:
    links = [
        EmailLink(url="https://www.linkedin.com/comm/unsubscribe", anchor_text="Unsubscribe"),
        EmailLink(url="https://www.linkedin.com/jobs/view/123", anchor_text="View Job"),
    ]
    result = UrlExtractor().extract(links)
    assert result is not None
    assert result.url == "https://www.linkedin.com/jobs/view/123"


def test_scores_known_job_domain_higher() -> None:
    links = [
        EmailLink(url="https://example-tracker.com/redirect?x=1", anchor_text="Click here"),
        EmailLink(url="https://www.indeed.com/viewjob?jk=abc123", anchor_text="Apply Now"),
    ]
    result = UrlExtractor().extract(links)
    assert result is not None
    assert "indeed.com" in result.url


def test_returns_none_when_no_links() -> None:
    assert UrlExtractor().extract([]) is None


def test_glassdoor_job_listing_beats_review_and_salary_links() -> None:
    links = [
        EmailLink(url="https://www.glassdoor.com/Reviews/ABC-Reviews-SRCH_KE0,5.htm"),
        EmailLink(url="https://www.glassdoor.com/overview/ABC-SRCH_KE0,5.htm"),
        EmailLink(
            url="https://www.glassdoor.com/job-listing/php-developer-abc-D_JO31112586.htm",
            anchor_text="Apply Now",
        ),
    ]
    result = UrlExtractor().extract(links)
    assert result is not None
    assert "job-listing" in result.url
    assert result.direct_job_url is True


def test_glassdoor_partner_job_listing_is_direct_job_url() -> None:
    links = [
        EmailLink(
            url="https://www.glassdoor.com/partner/jobListing.htm?pos=101&src=GD_EMAIL",
            anchor_text="Apply Now",
        )
    ]
    result = UrlExtractor().extract(links)
    assert result is not None
    assert result.direct_job_url is True


def test_glassdoor_non_job_links_only_returns_none() -> None:
    links = [
        EmailLink(url="https://www.glassdoor.com/Reviews/ABC-Reviews-SRCH_KE0,5.htm"),
        EmailLink(url="https://www.glassdoor.com/blog/weekly/"),
        EmailLink(url="https://www.glassdoor.com"),
    ]
    assert UrlExtractor().extract(links) is None


def test_header_feed_link_never_outranks_job_link() -> None:
    """Regression: the LinkedIn digest header/logo link (linkedin.com/feed/)
    used to tie with job-card links and win on max() ordering, making every
    digest job point at the LinkedIn feed instead of the job posting."""
    links = [
        EmailLink(
            url="https://www.linkedin.com/comm/feed/?trk=eml-job_digest-header-0",
            anchor_text="",
        ),
        EmailLink(
            url="https://www.linkedin.com/comm/jobs/view/123456",
            anchor_text="Senior PHP Developer",
        ),
    ]
    result = UrlExtractor().extract(links)
    assert result is not None
    assert result.url.endswith("/comm/jobs/view/123456")
    assert result.confidence >= 0.9


def test_feed_link_alone_yields_no_result() -> None:
    links = [
        EmailLink(url="https://www.linkedin.com/comm/feed/", anchor_text="LinkedIn"),
        EmailLink(
            url="https://www.linkedin.com/jobs/search/?keywords=php", anchor_text="Search jobs"
        ),
        EmailLink(url="https://www.linkedin.com/comm/unsubscribe", anchor_text="Unsubscribe"),
    ]
    assert UrlExtractor().extract(links) is None


def test_bare_domain_link_is_rejected() -> None:
    links = [
        EmailLink(url="https://www.indeed.com", anchor_text="Indeed"),
        EmailLink(url="https://www.indeed.com/viewjob?jk=abc123", anchor_text="PHP Developer"),
    ]
    result = UrlExtractor().extract(links)
    assert result is not None
    assert "viewjob" in result.url


def test_clk_indeed_homepage_link_is_rejected() -> None:
    links = [
        EmailLink(url="https://clk.indeed.com/hp?from=hp_email", anchor_text="Indeed Home"),
        EmailLink(url="https://www.indeed.com/rc/clk?jk=abc123", anchor_text="Apply"),
    ]
    result = UrlExtractor().extract(links)
    assert result is not None
    assert "rc/clk" in result.url
