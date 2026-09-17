"""phase1: gmail_accounts, job_platforms, job_emails

Revision ID: e67d82dbd17c
Revises:
Create Date: 2026-08-28

"""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "e67d82dbd17c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("access_token_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("history_id", sa.String(length=64), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_gmail_accounts_email"),
    )
    op.create_index("ix_gmail_accounts_user_id", "gmail_accounts", ["user_id"])

    op.create_table(
        "job_platforms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("parser", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_job_platforms_slug"),
    )

    op.create_table(
        "job_emails",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "gmail_account_id", sa.Integer(), sa.ForeignKey("gmail_accounts.id"), nullable=False
        ),
        sa.Column("gmail_message_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=998), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("NEW", "PROCESSING", "PROCESSED", "FAILED", name="jobemailstatus"),
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("raw_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "gmail_account_id", "gmail_message_id", name="uq_job_emails_account_message"
        ),
    )
    op.create_index("ix_job_emails_gmail_account_id", "job_emails", ["gmail_account_id"])
    op.create_index("ix_job_emails_received_at", "job_emails", ["received_at"])
    op.create_index("ix_job_emails_status", "job_emails", ["status"])

    # Seed the initial trusted platforms (spec section 18).
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
                "name": "LinkedIn",
                "slug": "linkedin",
                "domain": "linkedin.com",
                "enabled": True,
                "priority": 10,
                "created_at": now,
                "updated_at": now,
            },
            {
                "name": "Indeed",
                "slug": "indeed",
                "domain": "indeed.com",
                "enabled": True,
                "priority": 20,
                "created_at": now,
                "updated_at": now,
            },
            {
                "name": "Wellfound",
                "slug": "wellfound",
                "domain": "wellfound.com",
                "enabled": True,
                "priority": 30,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_job_emails_status", table_name="job_emails")
    op.drop_index("ix_job_emails_received_at", table_name="job_emails")
    op.drop_index("ix_job_emails_gmail_account_id", table_name="job_emails")
    op.drop_table("job_emails")
    op.drop_table("job_platforms")
    op.drop_index("ix_gmail_accounts_user_id", table_name="gmail_accounts")
    op.drop_table("gmail_accounts")
    sa.Enum(name="jobemailstatus").drop(op.get_bind(), checkfirst=True)
