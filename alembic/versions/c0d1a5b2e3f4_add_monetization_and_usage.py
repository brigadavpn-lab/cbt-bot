"""add monetization and usage logging

Revision ID: c0d1a5b2e3f4
Revises: b541a345da6b
Create Date: 2026-05-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c0d1a5b2e3f4"
down_revision: str | Sequence[str] | None = "b541a345da6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users: new columns
    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
    )
    op.add_column(
        "users",
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "situation_requests_today",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "generator_requests_today",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("users", sa.Column("last_reset_date", sa.Date(), nullable=True))

    # payment_logs
    op.create_table(
        "payment_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=False),
        sa.Column("plan_key", sa.String(), nullable=False),
        sa.Column("amount_rub", sa.Integer(), nullable=True),
        sa.Column("amount_stars", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("external_payment_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_payment_logs_tg_id", "payment_logs", ["tg_id"])
    op.create_index(
        "ix_payment_logs_external_payment_id",
        "payment_logs",
        ["external_payment_id"],
        unique=True,
    )

    # usage_logs
    op.create_table(
        "usage_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("feature", sa.String(), nullable=False),
        sa.Column(
            "model",
            sa.String(),
            nullable=False,
            server_default="claude-sonnet-4-6",
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cache_read_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "cache_creation_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_usage_logs_tg_id", "usage_logs", ["tg_id"])
    op.create_index("ix_usage_logs_created_at", "usage_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_logs_created_at", table_name="usage_logs")
    op.drop_index("ix_usage_logs_tg_id", table_name="usage_logs")
    op.drop_table("usage_logs")

    op.drop_index("ix_payment_logs_external_payment_id", table_name="payment_logs")
    op.drop_index("ix_payment_logs_tg_id", table_name="payment_logs")
    op.drop_table("payment_logs")

    op.drop_column("users", "last_reset_date")
    op.drop_column("users", "generator_requests_today")
    op.drop_column("users", "situation_requests_today")
    op.drop_column("users", "plan_expires_at")
    op.drop_column("users", "plan")
    op.drop_column("users", "full_name")
    op.drop_column("users", "username")
