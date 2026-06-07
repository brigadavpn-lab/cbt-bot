"""add_unique_constraint_attempts_user_task

Revision ID: e3f1a2b4c5d6
Revises: b1a6b2c49842
Create Date: 2026-06-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f1a2b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'b1a6b2c49842'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Удаляем дубликаты (оставляем запись с меньшим id)
    op.execute("""
        DELETE FROM attempts a1
        USING attempts a2
        WHERE a1.id > a2.id
          AND a1.user_id = a2.user_id
          AND a1.task_id = a2.task_id
    """)
    op.create_unique_constraint(
        'uq_attempts_user_task',
        'attempts',
        ['user_id', 'task_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_attempts_user_task', 'attempts', type_='unique')
