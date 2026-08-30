"""JobClassifier contract + result (spec section 14)."""

from dataclasses import dataclass, field
from typing import Protocol

from app.job_alerts.dto.normalized_job import NormalizedJob


@dataclass(frozen=True)
class ClassificationResult:
    matched: bool
    categories: list[str] = field(default_factory=list)
    matched_by: str = "rules"


class JobClassifier(Protocol):
    def classify(self, job: NormalizedJob) -> ClassificationResult: ...
