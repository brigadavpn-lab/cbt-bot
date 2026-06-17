"""cascade delete reactivation_log when campaign is deleted"""
from alembic import op

revision = 'i4j5k6l7m8n9'
down_revision = 'h3i4j5k6l7m8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        'reactivation_log_campaign_id_fkey',
        'reactivation_log',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'reactivation_log_campaign_id_fkey',
        'reactivation_log', 'reactivation_campaigns',
        ['campaign_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint(
        'reactivation_log_campaign_id_fkey',
        'reactivation_log',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'reactivation_log_campaign_id_fkey',
        'reactivation_log', 'reactivation_campaigns',
        ['campaign_id'], ['id'],
    )
