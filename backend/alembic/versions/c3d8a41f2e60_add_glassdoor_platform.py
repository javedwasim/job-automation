"""Add Glassdoor platform row (spec section 43 — new platforms are additive
rows in the database-driven registry, never pipeline edits).

Revision ID: c3d8a41f2e60
Revises: 90c0bc9bdc1a
Create Date: 2026-08-29
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "c3d8a41f2e60"
down_revision = "90c0bc9bdc1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM job_platforms WHERE slug = 'glassdoor'")
    ).scalar()
    if exists:
        return
    now = datetime.now(UTC)
    job_platforms = sa.table(
        "job_platforms",
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("domain", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("priority", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        job_platforms,
        [
            {
                "name": "Glassdoor",
                "slug": "glassdoor",
                "domain": "glassdoor.com",
                "enabled": True,
                "priority": 40,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM job_platforms WHERE slug = 'glassdoor'"))