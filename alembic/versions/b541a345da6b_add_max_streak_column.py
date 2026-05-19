"""Add max_streak column

Revision ID: b541a345da6b
Revises: cf87594fdd9b
Create Date: 2025-12-06 00:04:48.270242

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b541a345da6b"
down_revision: str | Sequence[str] | None = "cf87594fdd9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("max_streak", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "max_streak")
