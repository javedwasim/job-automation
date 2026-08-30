"""FreshnessPolicy (spec sections 6, 7) — centralized freshness gate tests.

With MAX_JOB_AGE_HOURS=24:
  5 hours old  -> ACCEPT
 23 hours old  -> ACCEPT
 25 hours old  -> REJECT
  3 days old   -> REJECT

Age is computed against job_posted_at with received_at as the reference —
never from received_at itself, never from "now".
"""

from datetime import UTC, datetime, timedelta

from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.normalization.freshness import FreshnessPolicy

RECEIVED_AT = datetime(2026, 8, 28, 10, 15, 0, tzinfo=UTC)


def _job(*, posted_at: datetime | None, promoted: bool = False) -> NormalizedJob:
    return NormalizedJob(
        title="Senior PHP Developer",
        company="TechCorp",
        location="Lahore, Pakistan",
        source="linkedin",
        platform_job_id="123456",
        job_url="https://www.linkedin.com/jobs/view/123456",
        application_url=None,
        job_posted_at=posted_at,
        received_at=RECEIVED_AT,
        description=None,
        source_email_id="msg-1",
        is_promoted=promoted,
    )


def test_five_hours_old_accepted() -> None:
    decision = FreshnessPolicy(max_age_hours=24).decide(
        _job(posted_at=RECEIVED_AT - timedelta(hours=5))
    )
    assert decision.accepted is True
    assert decision.reason == "fresh"


def test_twenty_three_hours_old_accepted() -> None:
    decision = FreshnessPolicy(max_age_hours=24).decide(
        _job(posted_at=RECEIVED_AT - timedelta(hours=23))
    )
    assert decision.accepted is True


def test_exactly_max_age_accepted_inclusive_boundary() -> None:
    decision = FreshnessPolicy(max_age_hours=24).decide(
        _job(posted_at=RECEIVED_AT - timedelta(hours=24))
    )
    assert decision.accepted is True


def test_twenty_five_hours_old_rejected() -> None:
    decision = FreshnessPolicy(max_age_hours=24).decide(
        _job(posted_at=RECEIVED_AT - timedelta(hours=25))
    )
    assert decision.accepted is False
    assert decision.reason == "too_old"


def test_three_days_old_rejected() -> None:
    decision = FreshnessPolicy(max_age_hours=24).decide(
        _job(posted_at=RECEIVED_AT - timedelta(days=3))
    )
    assert decision.accepted is False


def test_age_measured_from_received_at_not_now() -> None:
    """An email received 2026-08-28 with 'Posted 5 hours ago' is 5 hours old
    even if the pipeline processes it days later (spec section 4/6)."""
    posted = RECEIVED_AT - timedelta(hours=5)
    decision = FreshnessPolicy(max_age_hours=24).decide(_job(posted_at=posted))
    assert decision.accepted is True


def test_promoted_job_freshness_depends_only_on_posting_age() -> None:
    """Promoted jobs are never auto-rejected (spec section 11): a fresh
    promoted job is accepted, a stale one is rejected — same as organic."""
    policy = FreshnessPolicy(max_age_hours=24)
    fresh_promoted = policy.decide(
        _job(posted_at=RECEIVED_AT - timedelta(hours=5), promoted=True)
    )
    stale_promoted = policy.decide(
        _job(posted_at=RECEIVED_AT - timedelta(days=3), promoted=True)
    )
    assert fresh_promoted.accepted is True
    assert stale_promoted.accepted is False


def test_unknown_date_kept_by_default_and_never_fabricated() -> None:
    """Spec section 7 — unknown date => keep the candidate with
    job_posted_at left NULL; do NOT default to received_at."""
    policy = FreshnessPolicy(max_age_hours=24)  # default unknown_date_policy="keep"
    decision = policy.decide(_job(posted_at=None))
    assert decision.accepted is True
    assert decision.reason == "unknown_date"
    assert decision.job.job_posted_at is None
    assert decision.job.job_posted_at != decision.job.received_at


def test_unknown_date_rejected_when_policy_configured() -> None:
    policy = FreshnessPolicy(max_age_hours=24, unknown_date_policy="reject")
    decision = policy.decide(_job(posted_at=None))
    assert decision.accepted is False
    assert decision.reason == "unknown_date"


def test_filter_splits_accepted_and_stale() -> None:
    policy = FreshnessPolicy(max_age_hours=24)
    jobs = [
        _job(posted_at=RECEIVED_AT - timedelta(hours=5)),
        _job(posted_at=RECEIVED_AT - timedelta(hours=23)),
        _job(posted_at=RECEIVED_AT - timedelta(hours=25)),
        _job(posted_at=RECEIVED_AT - timedelta(days=3)),
        _job(posted_at=None),
    ]
    accepted, rejected = policy.filter(jobs)
    assert len(accepted) == 3
    assert [d.reason for d in rejected] == ["too_old", "too_old"]
    # Unknown-date job is retained under the default "keep" policy — with
    # job_posted_at still NULL, never fabricated, never defaulted to
    # received_at (spec section 7).
    unknown = [j for j in accepted if j.job_posted_at is None]
    assert len(unknown) == 1
    assert unknown[0].received_at == RECEIVED_AT
