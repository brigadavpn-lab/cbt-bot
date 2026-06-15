"""add reactivation_campaigns and reactivation_log tables"""
import sqlalchemy as sa
from alembic import op

revision = 'h3i4j5k6l7m8'
down_revision = 'g2h3i4j5k6l7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'reactivation_campaigns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('days_inactive', sa.Integer(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('schedule_day', sa.String(10), nullable=True),
        sa.Column('schedule_hour', sa.Integer(), nullable=True),
        sa.Column('schedule_minute', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'reactivation_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('campaign_id', sa.Integer(),
                  sa.ForeignKey('reactivation_campaigns.id'), nullable=False),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
    )
    op.create_unique_constraint(
        'uq_reactivation_campaign_user', 'reactivation_log', ['campaign_id', 'user_id']
    )


def downgrade() -> None:
    op.drop_table('reactivation_log')
    op.drop_table('reactivation_campaigns')
