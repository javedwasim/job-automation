import time

from app.gmail.client import build_lookback_query


def test_lookback_query_includes_after_epoch_seconds() -> None:
    before = int(time.time() - 24 * 3600)

    query = build_lookback_query(lookback_hours=24)

    assert query.startswith("after:")
    after_value = int(query.split("after:")[1].split(" ")[0])
    # allow a couple seconds of test execution drift
    assert abs(after_value - before) < 5


def test_lookback_query_has_no_sender_filters_by_default() -> None:
    """The query must not restrict senders: job alerts from ANY platform are
    ingested (spec sections 20-21). Only explicitly excluded domains may be
    negated."""
    query = build_lookback_query(lookback_hours=24)
    assert "from:" not in query
    assert " OR " not in query


def test_lookback_query_includes_category_when_configured() -> None:
    query = build_lookback_query(lookback_hours=24, gmail_category="updates")
    assert "category:updates" in query


def test_lookback_query_omits_category_when_disabled() -> None:
    query = build_lookback_query(lookback_hours=24, gmail_category="")
    assert "category:" not in query


def test_lookback_query_negates_excluded_domains() -> None:
    query = build_lookback_query(lookback_hours=24, excluded_domains=["glassdoor.com"])
    assert "-from:glassdoor.com" in query
