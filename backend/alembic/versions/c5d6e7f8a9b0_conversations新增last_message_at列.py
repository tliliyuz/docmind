"""conversations 新增 last_message_at 列 + 排序索引

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-06-13

变更:
- conversations 表新增 last_message_at DATETIME NULL DEFAULT NULL 列
  （最后一次产生消息的时间，用于列表排序，解决 FK SET NULL 污染 updated_at 导致排序错乱问题）
- conversations 表新增 (user_id, last_message_at) 复合索引
- 存量数据回填：last_message_at = 会话内最后一条消息的 created_at，无消息则取 created_at

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. conversations 表新增 last_message_at 列
    op.add_column('conversations', sa.Column(
        'last_message_at',
        sa.DateTime(),
        nullable=True,
        server_default=sa.text('NULL'),
        comment='最后一次产生消息的时间，用于列表排序。仅 send_message/assistant_reply 更新',
    ))

    # 2. 新增 (user_id, last_message_at) 复合索引
    op.create_index(
        'idx_conversations_user_last_msg',
        'conversations',
        ['user_id', 'last_message_at'],
    )

    # 3. 存量数据回填：取会话内最后一条消息的 created_at
    #    无消息的会话保持 NULL（前端排序时 NULL 自然沉底）
    op.execute("""
        UPDATE conversations c
        SET c.last_message_at = (
            SELECT MAX(m.created_at)
            FROM messages m
            WHERE m.conversation_id = c.id
        )
        WHERE c.message_count > 0
    """)

    # 4. 对于无消息但已存在的会话，降级为 created_at
    op.execute("""
        UPDATE conversations
        SET last_message_at = created_at
        WHERE last_message_at IS NULL
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_conversations_user_last_msg', table_name='conversations')
    op.drop_column('conversations', 'last_message_at')
