"""phase2-5: categories, keywords, jobs, pivot, processing_events

Revision ID: 90c0bc9bdc1a
Revises: e67d82dbd17c
Create Date: 2026-08-29

"""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "90c0bc9bdc1a"
down_revision = "e67d82dbd17c"
branch_labels = None
depends_on = None

_NOW = datetime.now(UTC)

# Initial categories + keywords (spec sections 12-13). Purely data, never
# hard-coded into classification logic — RuleBasedClassifier reads these
# rows at runtime.
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "PHP": ["php", "php developer", "php engineer"],
    "Laravel": ["laravel", "laravel developer", "laravel engineer"],
    "Backend": ["backend", "back-end", "server-side", "backend developer", "backend engineer"],
    "AI": ["ai", "artificial intelligence", "generative ai", "ai engineer", "ai developer"],
    "LLM": ["llm", "large language model", "llm engineer", "llm engineering"],
    "Python": ["python", "python developer"],
    "OpenCart": ["opencart", "open cart", "opencart developer"],
    "Machine Learning": ["machine learning", "machine learning engineer"],
    "Generative AI": ["generative ai", "generative ai engineer"],
}


def upgrade() -> None:
    op.create_table(
        "job_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_job_categories_slug"),
    )

    op.create_table(
        "job_category_keywords",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_category_id", sa.Integer(), sa.ForeignKey("job_categories.id"), nullable=False
        ),
        sa.Column("keyword", sa.String(length=150), nullable=False),
        sa.Column(
            "match_type",
            sa.Enum("exact", "word_boundary", "synonym", "negative", name="matchtype"),
            nullable=False,
            server_default="word_boundary",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_email_id", sa.Integer(), sa.ForeignKey("job_emails.id"), nullable=False),
        sa.Column("platform_id", sa.Integer(), sa.ForeignKey("job_platforms.id"), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("job_url", sa.String(length=2048), nullable=True),
        sa.Column("application_url", sa.String(length=2048), nullable=True),
        sa.Column("platform_job_id", sa.String(length=255), nullable=True),
        sa.Column("job_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "PROCESSING",
                "RELEVANT",
                "EXPORTED",
                "DUPLICATE",
                "IRRELEVANT",
                "FAILED",
                name="jobstatus",
            ),
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_jobs_fingerprint"),
    )
    op.create_index("ix_jobs_job_posted_at", "jobs", ["job_posted_at"])
    op.create_index("ix_jobs_received_at", "jobs", ["received_at"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_fingerprint", "jobs", ["fingerprint"])

    op.create_table(
        "job_category_pivot",
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column(
            "job_category_id", sa.Integer(), sa.ForeignKey("job_categories.id"), primary_key=True
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("matched_by", sa.String(length=50), nullable=True),
    )

    op.create_table(
        "processing_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_email_id", sa.Integer(), sa.ForeignKey("job_emails.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    _seed_categories_and_keywords()


def _seed_categories_and_keywords() -> None:
    job_categories = sa.table(
        "job_categories",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    job_category_keywords = sa.table(
        "job_category_keywords",
        sa.column("job_category_id", sa.Integer),
        sa.column("keyword", sa.String),
        sa.column("match_type", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    bind = op.get_bind()
    next_id = 1
    for name, keywords in _CATEGORY_KEYWORDS.items():
        slug = name.lower().replace(" ", "-")
        bind.execute(
            job_categories.insert().values(
                id=next_id,
                name=name,
                slug=slug,
                enabled=True,
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        bind.execute(
            job_category_keywords.insert(),
            [
                {
                    "job_category_id": next_id,
                    "keyword": keyword,
                    "match_type": "word_boundary",
                    "created_at": _NOW,
                    "updated_at": _NOW,
                }
                for keyword in keywords
            ],
        )
        next_id += 1


def downgrade() -> None:
    op.drop_table("processing_events")
    op.drop_table("job_category_pivot")
    op.drop_index("ix_jobs_fingerprint", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_received_at", table_name="jobs")
    op.drop_index("ix_jobs_job_posted_at", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("job_category_keywords")
    op.drop_table("job_categories")
    sa.Enum(name="jobstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="matchtype").drop(op.get_bind(), checkfirst=True)
