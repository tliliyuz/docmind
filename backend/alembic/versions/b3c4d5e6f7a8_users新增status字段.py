"""users 表新增 status 字段

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column(
        'status',
        sa.Enum('active', 'disabled', name='user_status'),
        server_default=sa.text("'active'"),
        nullable=False,
        comment='active（正常）/ disabled（禁用）',
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'status')
