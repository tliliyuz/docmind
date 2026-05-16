"""补充user.role、document.status、conversation.title的server_default

Revision ID: 04b3e0425da8
Revises: 42097bdbd61a
Create Date: 2026-05-16 15:20:10.485823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04b3e0425da8'
down_revision: Union[str, Sequence[str], None] = '42097bdbd61a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """补充 server_default，与 SQLAlchemy 模型 default 值同步"""
    op.alter_column(
        'users', 'role',
        existing_type=sa.Enum('user', 'admin', name='user_role'),
        server_default=sa.text("'user'"),
        existing_nullable=False,
    )
    # documents.status 在 42097bdbd61a 中已通过 raw SQL 设置了 DEFAULT 'uploaded'，
    # 此处用 alter_column 确保 Alembic 元数据层也一致（幂等）
    op.alter_column(
        'documents', 'status',
        existing_type=sa.Enum(
            'uploaded', 'parsing', 'chunking', 'embedding', 'vector_storing',
            'completed', 'success_with_warnings', 'partial_failed', 'failed', 'deleting',
            name='document_status'
        ),
        server_default=sa.text("'uploaded'"),
        existing_nullable=False,
    )
    op.alter_column(
        'conversations', 'title',
        existing_type=sa.String(length=256),
        server_default=sa.text("'新对话'"),
        existing_nullable=False,
    )


def downgrade() -> None:
    """移除 server_default"""
    op.alter_column(
        'conversations', 'title',
        existing_type=sa.String(length=256),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        'documents', 'status',
        existing_type=sa.Enum(
            'uploaded', 'parsing', 'chunking', 'embedding', 'vector_storing',
            'completed', 'success_with_warnings', 'partial_failed', 'failed', 'deleting',
            name='document_status'
        ),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        'users', 'role',
        existing_type=sa.Enum('user', 'admin', name='user_role'),
        server_default=None,
        existing_nullable=False,
    )
