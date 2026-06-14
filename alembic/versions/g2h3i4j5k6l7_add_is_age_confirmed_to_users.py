"""add is_age_confirmed to users

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
"""
from alembic import op

def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_age_confirmed BOOLEAN NOT NULL DEFAULT FALSE
    """)

def downgrade() -> None:
    op.drop_column('users', 'is_age_confirmed')
