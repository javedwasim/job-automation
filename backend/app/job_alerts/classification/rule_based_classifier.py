"""RuleBasedClassifier (spec section 14) — keyword/synonym matching against
configurable categories loaded from the database. No LLM required."""

import re

from app.job_alerts.classification.contracts import ClassificationResult
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.jobs.models.job_category import JobCategory
from app.jobs.models.job_category_keyword import MatchType


class RuleBasedClassifier:
    def __init__(self, categories: list[JobCategory]) -> None:
        self._categories = [c for c in categories if c.enabled]

    def classify(self, job: NormalizedJob) -> ClassificationResult:
        haystack = " ".join(filter(None, [job.title, job.description])).lower()

        matched_categories: list[str] = []

        for category in self._categories:
            negative_keywords = [k for k in category.keywords if k.match_type == MatchType.NEGATIVE]
            if any(self._keyword_matches(k.keyword, haystack) for k in negative_keywords):
                continue

            positive_keywords = [k for k in category.keywords if k.match_type != MatchType.NEGATIVE]
            if any(self._keyword_matches(k.keyword, haystack) for k in positive_keywords):
                matched_categories.append(category.name)

        return ClassificationResult(
            matched=bool(matched_categories), categories=matched_categories, matched_by="rules"
        )

    def _keyword_matches(self, keyword: str, haystack: str) -> bool:
        # Word-boundary matching by default avoids naive-substring false
        # positives (spec section 13) — e.g. "ai" shouldn't match "said".
        pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
        return re.search(pattern, haystack) is not None
