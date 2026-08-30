"""Centralized normalization & freshness policy (spec sections 2, 6, 7, 15).

Every job candidate extracted by ANY platform parser flows through these
services before persistence — the platform layer never reimplements them.
"""

from app.job_alerts.normalization.freshness import FreshnessDecision, FreshnessPolicy
from app.job_alerts.normalization.job_normalizer import JobNormalizer, RejectedJob

__all__ = ["FreshnessDecision", "FreshnessPolicy", "JobNormalizer", "RejectedJob"]

