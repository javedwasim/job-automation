from datetime import UTC, datetime

from app.job_alerts.classification.rule_based_classifier import RuleBasedClassifier
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.jobs.models.job_category import JobCategory
from app.jobs.models.job_category_keyword import JobCategoryKeyword, MatchType

NOW = datetime.now(UTC)


def _category(name: str, keywords: list[str], negative: list[str] | None = None) -> JobCategory:
    category = JobCategory(
        name=name, slug=name.lower(), enabled=True, created_at=NOW, updated_at=NOW
    )
    category.keywords = [
        JobCategoryKeyword(
            keyword=k, match_type=MatchType.WORD_BOUNDARY, created_at=NOW, updated_at=NOW
        )
        for k in keywords
    ] + [
        JobCategoryKeyword(keyword=k, match_type=MatchType.NEGATIVE, created_at=NOW, updated_at=NOW)
        for k in (negative or [])
    ]
    return category


def _job(title: str, description: str = "") -> NormalizedJob:
    return NormalizedJob(
        title=title,
        company=None,
        location=None,
        source="generic",
        platform_job_id=None,
        job_url=None,
        application_url=None,
        job_posted_at=None,
        received_at=NOW,
        description=description,
        source_email_id="msg-1",
    )


def test_classifies_job_into_multiple_matching_categories() -> None:
    categories = [
        _category("Laravel", ["laravel"]),
        _category("PHP", ["php"]),
        _category("Backend", ["backend"]),
    ]
    classifier = RuleBasedClassifier(categories)

    result = classifier.classify(_job("Senior Laravel Backend Developer", "PHP and Laravel role"))

    assert result.matched is True
    assert set(result.categories) == {"Laravel", "PHP", "Backend"}
    assert result.matched_by == "rules"


def test_irrelevant_job_does_not_match() -> None:
    categories = [_category("Laravel", ["laravel"])]
    classifier = RuleBasedClassifier(categories)

    result = classifier.classify(_job("Marketing Manager", "Social media and campaigns"))

    assert result.matched is False
    assert result.categories == []


def test_word_boundary_matching_avoids_false_positive() -> None:
    # "ai" as a substring of "said" or "maintain" must NOT match.
    categories = [_category("AI", ["ai"])]
    classifier = RuleBasedClassifier(categories)

    result = classifier.classify(_job("Maintenance Technician", "He said the role is remote"))

    assert result.matched is False


def test_negative_keyword_excludes_category() -> None:
    categories = [_category("PHP", ["php"], negative=["wordpress"])]
    classifier = RuleBasedClassifier(categories)

    result = classifier.classify(_job("WordPress PHP Developer", "Manage WordPress php plugins"))

    assert result.matched is False


def test_disabled_category_is_ignored() -> None:
    category = _category("Laravel", ["laravel"])
    category.enabled = False
    classifier = RuleBasedClassifier([category])

    result = classifier.classify(_job("Laravel Developer"))

    assert result.matched is False
