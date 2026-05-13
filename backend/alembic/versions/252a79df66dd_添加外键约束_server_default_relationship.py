"""添加外键约束、server_default、relationship

Revision ID: 252a79df66dd
Revises: 7588fa83e017
Create Date: 2026-05-12 23:34:58.444469

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '252a79df66dd'
down_revision: Union[str, Sequence[str], None] = '7588fa83e017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 补充 server_default，确保直接 SQL 插入也安全
    op.alter_column('knowledge_bases', 'chunk_count', existing_type=sa.Integer(), server_default=sa.text("'0'"))
    op.alter_column('knowledge_bases', 'doc_count', existing_type=sa.Integer(), server_default=sa.text("'0'"))
    op.alter_column('documents', 'chunk_count', existing_type=sa.Integer(), server_default=sa.text("'0'"))
    op.alter_column('chunks', 'token_count', existing_type=sa.Integer(), server_default=sa.text("'0'"))
    op.alter_column('conversations', 'message_count', existing_type=sa.Integer(), server_default=sa.text("'0'"))
    op.alter_column('messages', 'token_count', existing_type=sa.Integer(), server_default=sa.text("'0'"))

    # 添加外键约束（与 DATABASE.md §4 外键策略一致）
    op.create_foreign_key(None, 'chunks', 'knowledge_bases', ['kb_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'chunks', 'documents', ['doc_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'conversations', 'knowledge_bases', ['kb_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'conversations', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'documents', 'knowledge_bases', ['kb_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'knowledge_bases', 'users', ['user_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key(None, 'messages', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # 移除外键
    op.drop_constraint(None, 'messages', type_='foreignkey')
    op.drop_constraint(None, 'knowledge_bases', type_='foreignkey')
    op.drop_constraint(None, 'documents', type_='foreignkey')
    op.drop_constraint(None, 'conversations', type_='foreignkey')
    op.drop_constraint(None, 'conversations', type_='foreignkey')
    op.drop_constraint(None, 'chunks', type_='foreignkey')
    op.drop_constraint(None, 'chunks', type_='foreignkey')

    # 移除 server_default
    op.alter_column('messages', 'token_count', existing_type=sa.Integer(), server_default=None)
    op.alter_column('conversations', 'message_count', existing_type=sa.Integer(), server_default=None)
    op.alter_column('chunks', 'token_count', existing_type=sa.Integer(), server_default=None)
    op.alter_column('documents', 'chunk_count', existing_type=sa.Integer(), server_default=None)
    op.alter_column('knowledge_bases', 'doc_count', existing_type=sa.Integer(), server_default=None)
    op.alter_column('knowledge_bases', 'chunk_count', existing_type=sa.Integer(), server_default=None)
    # ### end Alembic commands ###
