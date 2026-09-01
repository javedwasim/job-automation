"""LinkedIn scraper card-parser tests - the CRITICAL extraction rule:

    ONE job card, however many links it contains  ->  exactly ONE job.

Covers:
  1 card  with 3+ links  ->   1 job
 10 cards with 30 links  ->  10 jobs
  field mapping (Title, Company, Posted, Job Link, Job ID)
  a malformed card never stops the scrape
  multiple layout variants (job-card-container + base-search-card)

source code here is the single place that splits the page into cards, so
link count can NEVER determine job count.
"""

from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup

from app.job_scraper.card_parser import find_job_cards, parse_job_card, parse_jobs_html

SCRAPED_AT = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)


def _job_card(
    *,
    job_id: str,
    title: str = "Senior Machine Learning Engineer (Remote)",
    company: str = "TechNova",
    location: str = "Pakistan (Remote)",
    posted: str = "1 week ago",
    href: str | None = None,
    extra_links: int = 2,
) -> str:
    """A realistic modern-layout LinkedIn job card: title link PLUS
    'extra_links' more job links (apply CTA, logo, tracking) - all for the
    SAME job."""
    link = href or f"https://www.linkedin.com/jobs/view/{job_id}?trk=eml-job_digest-jobcard_body"
    extras = ""
    for i in range(extra_links):
        extras += f'\n<a class="aux-{i}" href="https://www.linkedin.com/jobs/view/{job_id}/apply?trk=apply-{i}">Apply now</a>'
    return f"""
    <li class="job-card-container" data-occludable-job-id="{job_id}">
      <div class="job-card-container">
        <a class="job-card-list__title--link" href="{link}">
          <span aria-hidden="true">{title}</span>
        </a>
        <div class="job-card-container__primary-description">
          <span class="job-card-container__company-name">{company}</span>
        </div>
        <div class="job-card-container__metadata">
          <div class="job-card-container__metadata-sibling">{location}</div>
        </div>
        <div class="job-card-container__footer">
          <span class="job-card-container__listed-time">{posted}</span>
        </div>
        <a class="company-brand-link" href="https://www.linkedin.com/company/technova">
          <img src="logo.png" alt="logo"/>
        </a>{extras}
      </div>
    </li>"""


def _page(*cards: str) -> str:
    return f"<html><body><ul>{''.join(cards)}</ul></body></html>"


# --- one card = one job -------------------------------------------------------


def test_one_card_with_three_links_yields_exactly_one_job() -> None:
    jobs = parse_jobs_html(_page(_job_card(job_id="4025123456", extra_links=3)))
    assert len(jobs) == 1

    job = jobs[0]
    assert job.title == "Senior Machine Learning Engineer (Remote)"
    assert job.company == "TechNova"
    assert job.location == "Pakistan (Remote)"
    assert job.posted_text == "1 week ago"
    assert job.job_id == "4025123456"
    # Exactly one canonical job URL - tracking stripped, /comm/ collapsed.
    assert job.job_url == "https://www.linkedin.com/jobs/view/4025123456"


def test_ten_cards_with_thirty_links_yield_exactly_ten_jobs() -> None:
    cards = [_job_card(job_id=f"40{j:06d}", company=f"Company {j}", extra_links=3) for j in range(1, 11)]
    jobs = parse_jobs_html(_page(*cards))

    assert len(jobs) == 10
    assert {j.job_id for j in jobs} == {f"40{j:06d}" for j in range(1, 11)}
    assert len({j.job_url for j in jobs}) == 10


def test_number_of_links_never_changes_job_count_within_a_card() -> None:
    base = parse_jobs_html(_page(_job_card(job_id="4025123456", extra_links=1)))
    many = parse_jobs_html(_page(_job_card(job_id="4025123456", extra_links=8)))
    assert len(base) == 1
    assert len(many) == 1


# --- field mapping -------------------------------------------------------------


def test_field_mapping_title_company_posted_link_id() -> None:
    job = parse_jobs_html(
        _page(
            _job_card(
                job_id="4025999888",
                title="Lead Full-stack Software Engineer (PHP and React)",
                company="Hilton",
                location="Lahore, Punjab, Pakistan (Remote)",
                posted="2 days ago",
            )
        )
    )[0]

    assert job.title == "Lead Full-stack Software Engineer (PHP and React)"
    assert job.company == "Hilton"
    assert job.location == "Lahore, Punjab, Pakistan (Remote)"
    assert job.posted_text == "2 days ago"
    assert job.job_id == "4025999888"
    assert job.job_url == "https://www.linkedin.com/jobs/view/4025999888"


def test_posted_is_normalized_to_timestamp() -> None:
    job = parse_jobs_html(_page(_job_card(job_id="111", posted="5 hours ago")), scraped_at=SCRAPED_AT)[0]
    assert job.posted_text == "5 hours ago"
    assert job.posted_at == SCRAPED_AT - timedelta(hours=5)


def test_company_never_mistaken_for_title_and_vice_versa() -> None:
    job = parse_jobs_html(
        _page(_job_card(job_id="222", company="ACME Corp", location="Remote", posted="1 day ago"))
    )[0]
    assert job.title == "Senior Machine Learning Engineer (Remote)"
    assert job.company == "ACME Corp"
    assert job.location == "Remote"
    assert "ACME" not in job.title
    assert "Remote" not in (job.company or "")


def test_job_id_extracted_from_url_when_attribute_missing() -> None:
    card = _job_card(job_id="4025123456").replace('data-occludable-job-id="4025123456"', "")
    soup = BeautifulSoup(card, "html.parser")
    job = parse_job_card(soup.find("li"), scraped_at=SCRAPED_AT)
    assert job is not None
    assert job.job_id == "4025123456"


def test_base_search_card_layout_is_supported() -> None:
    html = """
    <div class="base-card base-search-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/4027777111/">
        <span class="sr-only">Senior Laravel Developer - ABC Tech - Remote</span>
      </a>
      <div class="base-search-card__info">
        <h3 class="base-search-card__title">Senior Laravel Developer</h3>
        <h4 class="base-search-card__subtitle">ABC Tech</h4>
        <div class="base-search-card__metadata">
          <p class="job-search-card__location">Remote</p>
          <time class="job-search-card__listdate">18 hours ago</time>
        </div>
      </div>
    </div>"""
    jobs = parse_jobs_html(html)
    assert len(jobs) == 1
    assert jobs[0].title == "Senior Laravel Developer"
    assert jobs[0].company == "ABC Tech"
    assert jobs[0].location == "Remote"
    assert jobs[0].posted_text == "18 hours ago"
    assert jobs[0].job_url == "https://www.linkedin.com/jobs/view/4027777111"
    assert jobs[0].job_id == "4027777111"


# --- robustness -----------------------------------------------------------------


def test_malformed_card_is_skipped_without_stopping_the_scrape() -> None:
    bad = """
    <li class="job-card-container" data-occludable-job-id="9999">
      <div class="job-card-container">
        <a class="job-card-list__title--link" href="https://www.linkedin.com/jobs/view/9999"></a>
      </div>
    </li>"""
    good = _job_card(job_id="4025123456", posted="3 hours ago")
    jobs = parse_jobs_html(_page(bad, good))
    assert len(jobs) == 1
    assert jobs[0].job_id == "4025123456"


def test_empty_or_no_card_page_yields_no_jobs() -> None:
    assert parse_jobs_html("<html><body><p>No matching jobs found.</p></body></html>") == []
    assert parse_jobs_html("") == []
    assert find_job_cards(BeautifulSoup("<ul></ul>", "html.parser")) == []
