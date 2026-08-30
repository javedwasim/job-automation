"""add remote_type/salary/employment_type to jobs (spec sections 2, 11-13)

Purely additive, non-destructive: three nullable String columns so the
structured signals platform emails actually state (remote type, salary,
employment type) can be persisted per job. Existing rows keep NULL —
nothing is backfilled, nothing is dropped.

Revision ID: d4e9f2a7b3c1
Revises: c3d8a41f2e60
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e9f2a7b3c1"
down_revision = "c3d8a41f2e60"
branch_labels = None
depends_on = None

_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("remote_type", sa.String(length=50)),
    ("salary", sa.String(length=100)),
    ("employment_type", sa.String(length=50)),
]


def _existing_columns(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns("jobs")}


def upgrade() -> None:
    bind = op.get_bind()
    present = _existing_columns(bind)
    for name, column_type in _COLUMNS:
        if name not in present:
            op.add_column("jobs", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    present = _existing_columns(op.get_bind())
    for name, _ in _COLUMNS:
        if name in present:
            op.drop_column("jobs", name)
