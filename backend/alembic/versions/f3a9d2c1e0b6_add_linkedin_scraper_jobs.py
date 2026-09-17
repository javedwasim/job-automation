"""Add scraped_jobs table for the independent LinkedIn scraper.

Revision ID: f3a9d2c1e0b6
Revises: d4e9f2a7b3c1
Create Date: 2026-08-31

The scraper persists to its OWN table so its results never disturb or
overwrite Gmail-derived jobs. Unique indexes on job_id and the canonical
job_url are the dedup guard at the database level.
"""

import sqlalchemy as sa
from alembic import op

revision = "f3a9d2c1e0b6"
down_revision = "d4e9f2a7b3c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scraped_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=True),
        sa.Column("job_url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("posted_text", sa.String(length=100), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scraped_jobs_job_id", "scraped_jobs", ["job_id"], unique=True)
    op.create_index("ix_scraped_jobs_job_url", "scraped_jobs", ["job_url"], unique=True)
    op.create_index("ix_scraped_jobs_source", "scraped_jobs", ["source"], unique=False)
    op.create_index("ix_scraped_jobs_scraped_at", "scraped_jobs", ["scraped_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scraped_jobs_scraped_at", table_name="scraped_jobs")
    op.drop_index("ix_scraped_jobs_source", table_name="scraped_jobs")
    op.drop_index("ix_scraped_jobs_job_url", table_name="scraped_jobs")
    op.drop_index("ix_scraped_jobs_job_id", table_name="scraped_jobs")
    op.drop_table("scraped_jobs")