"""add timezone to users

Revision ID: 76e12b222415
Revises: 8335d1205196
Create Date: 2026-07-28 22:22:37.594809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76e12b222415'
down_revision: Union[str, Sequence[str], None] = '8335d1205196'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills existing rows (production already has users) —
    # a plain NOT NULL add_column with no default errors on Postgres the
    # moment the table isn't empty.
    op.add_column('users', sa.Column(
        'timezone', sa.String(length=64), nullable=False,
        server_default='America/New_York',
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'timezone')
