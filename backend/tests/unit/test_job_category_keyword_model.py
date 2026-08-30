"""Regression tests for the MatchType DB representation.

Migration 90c0bc9bdc1a creates `job_category_keywords.match_type` as
sa.Enum("exact", "word_boundary", "synonym", "negative") — i.e. the enum's
lowercase *values* — and seeds every row with "word_boundary". The ORM model
must therefore persist/read values too; the default name-based mapping made
every lazy load of category.keywords raise LookupError, classification always
crashed (silently swallowed by the ingestion service), and no Job rows were
ever persisted.
"""

from datetime import UTC, datetime

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.jobs.models.job_category import JobCategory
from app.jobs.models.job_category_keyword import JobCategoryKeyword, MatchType

NOW = datetime.now(UTC)


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_orm_write_read_round_trips_lowercase_value() -> None:
    with _session() as session:
        category = JobCategory(
            name="Laravel", slug="laravel", enabled=True, created_at=NOW, updated_at=NOW
        )
        session.add(category)
        session.flush()
        session.add(
            JobCategoryKeyword(
                job_category_id=category.id,
                keyword="laravel",
                match_type=MatchType.WORD_BOUNDARY,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()

        stored = session.execute(text("SELECT match_type FROM job_category_keywords")).scalar_one()
        assert stored == "word_boundary"  # matches the migration's DDL labels

        session.expire_all()  # force re-hydration from the DB
        keyword = session.scalars(select(JobCategoryKeyword)).one()
        assert keyword.match_type is MatchType.WORD_BOUNDARY


def test_migration_seeded_row_hydrates() -> None:
    """Replicates migration 90c0bc9bdc1a's raw insert of the server_default."""
    with _session() as session:
        category = JobCategory(name="PHP", slug="php", enabled=True, created_at=NOW, updated_at=NOW)
        session.add(category)
        session.flush()
        session.execute(
            text(
                "INSERT INTO job_category_keywords "
                "(job_category_id, keyword, match_type, created_at, updated_at) "
                "VALUES (:cid, 'php developer', 'word_boundary', :now, :now)"
            ),
            {"cid": category.id, "now": NOW.isoformat(" ")},
        )
        session.commit()

        session.expire_all()
        keyword = session.scalars(select(JobCategoryKeyword)).one()
        assert keyword.match_type is MatchType.WORD_BOUNDARY


def test_all_match_type_members_round_trip() -> None:
    with _session() as session:
        category = JobCategory(
            name="Backend", slug="backend", enabled=True, created_at=NOW, updated_at=NOW
        )
        session.add(category)
        session.flush()
        for member in MatchType:
            session.add(
                JobCategoryKeyword(
                    job_category_id=category.id,
                    keyword=f"kw-{member.value}",
                    match_type=member,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        session.commit()

        session.expire_all()
        keywords = session.scalars(select(JobCategoryKeyword)).all()
        assert {k.keyword: k.match_type for k in keywords} == {
            f"kw-{member.value}": member for member in MatchType
        }
