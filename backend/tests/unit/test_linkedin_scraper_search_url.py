"""LinkedIn search-URL builder tests.

Every filter maps to LinkedIn's own query parameters; nothing is hard-coded
for a particular keyword/location, so the scraper supports any search the
user types (the dashboard defaults are demonstrative, not enforced here).
"""

from app.job_scraper.search_url import build_linkedin_search_url


def test_keyword_and_location_only() -> None:
    url = build_linkedin_search_url(keyword="PHP Developer", location="Remote")
    assert url == "https://www.linkedin.com/jobs/search/?keywords=PHP+Developer&location=Remote"


def test_date_posted_maps_to_linkedin_window_tokens() -> None:
    assert "f_TPR=r86400" in build_linkedin_search_url(date_posted="past_24_hours")
    assert "f_TPR=r604800" in build_linkedin_search_url(date_posted="past_week")
    assert "f_TPR=r2592000" in build_linkedin_search_url(date_posted="past_month")
    assert "f_TPR" not in build_linkedin_search_url(date_posted="any")


def test_job_type_maps_to_linkedin_tokens() -> None:
    assert "f_JT=F" in build_linkedin_search_url(job_type="full_time")
    assert "f_JT=P" in build_linkedin_search_url(job_type="part_time")
    assert "f_JT=C" in build_linkedin_search_url(job_type="contract")
    assert "f_JT=T" in build_linkedin_search_url(job_type="temporary")
    assert "f_JT=I" in build_linkedin_search_url(job_type="internship")
    assert "f_JT" not in build_linkedin_search_url(job_type="any")


def test_workplace_maps_to_linkedin_tokens() -> None:
    assert "f_WT=2" in build_linkedin_search_url(workplace="remote")
    assert "f_WT=3" in build_linkedin_search_url(workplace="hybrid")
    assert "f_WT=1" in build_linkedin_search_url(workplace="onsite")
    assert "f_WT" not in build_linkedin_search_url(workplace="any")


def test_all_filters_combined() -> None:
    url = build_linkedin_search_url(
        keyword="Data Engineer",
        location="Lahore",
        date_posted="past_week",
        job_type="full_time",
        workplace="hybrid",
    )
    assert url == (
        "https://www.linkedin.com/jobs/search/?keywords=Data+Engineer&location=Lahore"
        "&f_TPR=r604800&f_JT=F&f_WT=3"
    )


def test_unknown_filter_values_safely_omit_the_parameter() -> None:
    url = build_linkedin_search_url(keyword="Engineer", date_posted="bogus", job_type="bogus", workplace="bogus")
    assert url == "https://www.linkedin.com/jobs/search/?keywords=Engineer"


def test_no_filters_yields_plain_search_url() -> None:
    assert build_linkedin_search_url() == "https://www.linkedin.com/jobs/search/"
