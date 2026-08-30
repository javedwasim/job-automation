"""FreshnessPolicy (spec sections 6, 7) — THE shared freshness gate.

Age is calculated from `job_posted_at`, NEVER from `received_at`, and the
reference timestamp for the age is the email's own received time (so the
policy is deterministic and cannot be gamed by delayed processing).

Unknown posting dates are handled by an explicit, centralized policy
(UNKNOWN_DATE_POLICY):
  - "keep" (default): the candidate is RETAINED with job_posted_at=NULL —
    the date is never fabricated and never defaulted to received_at — and
    the job is exempt from age filtering.
  - "reject": unknown-date candidates are dropped instead.
"""

from dataclasses import dataclass

from app.job_alerts.dto.normalized_job import NormalizedJob

KEEP_UNKNOWN_DATE = "keep"
REJECT_UNKNOWN_DATE = "reject"


@dataclass(frozen=True)
class FreshnessDecision:
    job: NormalizedJob
    accepted: bool
    reason: str  # "fresh" | "too_old" | "unknown_date"


class FreshnessPolicy:
    def __init__(self, max_age_hours: int = 24, unknown_date_policy: str = KEEP_UNKNOWN_DATE):
        self._max_age_hours = max_age_hours
        self._unknown_date_policy = unknown_date_policy

    @property
    def max_age_hours(self) -> int:
        return self._max_age_hours

    def decide(self, job: NormalizedJob) -> FreshnessDecision:
        if job.job_posted_at is None:
            # Spec section 7 — explicit unknown-date policy, never fabricate.
            accepted = self._unknown_date_policy != REJECT_UNKNOWN_DATE
            return FreshnessDecision(
                job=job,
                accepted=accepted,
                reason="unknown_date",
            )

        age = job.received_at - job.job_posted_at
        age_hours = age.total_seconds() / 3600
        if age_hours <= self._max_age_hours:
            return FreshnessDecision(job=job, accepted=True, reason="fresh")
        return FreshnessDecision(job=job, accepted=False, reason="too_old")

    def filter(
        self, jobs: list[NormalizedJob]
    ) -> tuple[list[NormalizedJob], list[FreshnessDecision]]:
        """Splits candidates into (accepted, rejected-by-freshness) so the
        pipeline can record explicit events for every filtered job."""
        accepted: list[NormalizedJob] = []
        rejected: list[FreshnessDecision] = []
        for job in jobs:
            decision = self.decide(job)
            if decision.accepted:
                accepted.append(job)
            else:
                rejected.append(decision)
        return accepted, rejected
