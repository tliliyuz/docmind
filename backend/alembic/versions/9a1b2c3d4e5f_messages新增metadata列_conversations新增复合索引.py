"""messages新增metadata列 + conversations新增复合索引

Revision ID: 9a1b2c3d4e5f
Revises: 8fa3ea12b75e
Create Date: 2026-06-05

变更:
- messages 表新增 metadata JSON NULL DEFAULT NULL 列（Phase 5+ Tool Call / Web Search / Agent 预留）
- conversations 表新增 (user_id, updated_at) 复合索引（Phase 4 会话列表按更新时间倒序查询）

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '8fa3ea12b75e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. messages 表新增 metadata JSON 列
    op.add_column('messages', sa.Column(
        'metadata',
        sa.JSON(),
        nullable=True,
        server_default=sa.text('NULL'),
        comment='扩展元数据：未来 Tool Call / Web Search / Agent 等场景的非结构化数据'
    ))

    # 2. conversations 表新增 (user_id, updated_at) 复合索引
    #    加速「当前用户的会话列表按更新时间倒序」查询（Phase 4 Sidebar）
    op.create_index(
        'idx_conversations_user_updated',
        'conversations',
        ['user_id', 'updated_at'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_conversations_user_updated', table_name='conversations')
    op.drop_column('messages', 'metadata')
