from datetime import UTC, datetime, timedelta

from app.job_alerts.extraction.job_posted_date_extractor import JobPostedDateExtractor

RECEIVED_AT = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)


def test_extracts_relative_hours_ago() -> None:
    extractor = JobPostedDateExtractor()
    result = extractor.extract("Posted 3 hours ago", RECEIVED_AT)
    assert result == RECEIVED_AT - timedelta(hours=3)


def test_extracts_relative_days_ago() -> None:
    extractor = JobPostedDateExtractor()
    result = extractor.extract("Posted 2 days ago", RECEIVED_AT)
    assert result == RECEIVED_AT - timedelta(days=2)


def test_extracts_yesterday() -> None:
    extractor = JobPostedDateExtractor()
    result = extractor.extract("Posted yesterday", RECEIVED_AT)
    assert result == RECEIVED_AT - timedelta(days=1)


def test_extracts_explicit_date() -> None:
    extractor = JobPostedDateExtractor()
    result = extractor.extract("Posted on Aug 28, 2026", RECEIVED_AT)
    assert result is not None
    assert (result.year, result.month, result.day) == (2026, 8, 28)


def test_missing_date_returns_none_never_fabricated() -> None:
    extractor = JobPostedDateExtractor()
    result = extractor.extract("Great opportunity, apply now!", RECEIVED_AT)
    assert result is None


def test_job_posted_at_never_defaults_to_received_at_when_unknown() -> None:
    extractor = JobPostedDateExtractor()
    result = extractor.extract("", RECEIVED_AT)
    assert result is None
    assert result != RECEIVED_AT


# --- Spec section 4: the full relative-format matrix ------------------------


def test_extracts_just_now() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("Just now", RECEIVED_AT) == RECEIVED_AT


def test_extracts_one_minute_ago() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("1 minute ago", RECEIVED_AT) == RECEIVED_AT - timedelta(minutes=1)


def test_extracts_thirty_minutes_ago() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("30 minutes ago", RECEIVED_AT) == RECEIVED_AT - timedelta(minutes=30)


def test_extracts_one_hour_ago_without_posted_prefix() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("1 hour ago", RECEIVED_AT) == RECEIVED_AT - timedelta(hours=1)


def test_extracts_five_hours_ago() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("5 hours ago", RECEIVED_AT) == RECEIVED_AT - timedelta(hours=5)


def test_extracts_one_day_ago_without_posted_prefix() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("1 day ago", RECEIVED_AT) == RECEIVED_AT - timedelta(days=1)


def test_extracts_three_days_ago_with_posted_prefix() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("Posted 3 days ago", RECEIVED_AT) == RECEIVED_AT - timedelta(days=3)


def test_extracts_one_week_ago() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("1 week ago", RECEIVED_AT) == RECEIVED_AT - timedelta(weeks=1)


def test_extracts_two_weeks_ago() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("2 weeks ago", RECEIVED_AT) == RECEIVED_AT - timedelta(weeks=2)


def test_extracts_one_month_ago() -> None:
    extractor = JobPostedDateExtractor()
    result = extractor.extract("1 month ago", RECEIVED_AT)
    assert result is not None
    # One calendar month before 2026-08-28 is 2026-07-28.
    assert (result.year, result.month, result.day) == (2026, 7, 28)


def test_extracts_posted_two_hours_ago() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("Posted 2 hours ago", RECEIVED_AT) == RECEIVED_AT - timedelta(
        hours=2
    )


def test_relative_time_uses_received_at_not_current_time() -> None:
    """The reference timestamp MUST be the email's received_at (spec section
    4): an email received 2026-08-28 10:15 containing '3 hours ago' means
    07:15 the same day — even if it is processed days later."""
    extractor = JobPostedDateExtractor()
    result = extractor.extract("Posted 3 hours ago", RECEIVED_AT)
    assert result == RECEIVED_AT - timedelta(hours=3)
    assert result != datetime.now(UTC) - timedelta(hours=3)


def test_case_insensitive_and_mixed_wording() -> None:
    extractor = JobPostedDateExtractor()
    assert extractor.extract("JUST NOW", RECEIVED_AT) == RECEIVED_AT
    assert extractor.extract("posted 45 MINUTES ago", RECEIVED_AT) == RECEIVED_AT - timedelta(
        minutes=45
    )


def test_first_relative_mention_wins_in_multi_job_text() -> None:
    extractor = JobPostedDateExtractor()
    text = "Job A posted 3 days ago. Job B posted 2 weeks ago."
    assert extractor.extract(text, RECEIVED_AT) == RECEIVED_AT - timedelta(days=3)


def test_future_posting_date_is_rejected_not_trusted() -> None:
    """A posting date after the email was received is untrusted data — never
    allowed through (spec section 4: never fabricate)."""
    extractor = JobPostedDateExtractor()
    text = "Job posted tomorrow"  # no reliable relative phrase
    assert extractor.extract(text, RECEIVED_AT) is None
