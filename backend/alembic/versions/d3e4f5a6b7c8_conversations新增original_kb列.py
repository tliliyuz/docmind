"""conversations 新增 original_kb_id + original_kb_name 列

Revision ID: d3e4f5a6b7c8
Revises: c5d6e7f8a9b0
Create Date: 2026-06-13

变更:
- conversations 表新增 original_kb_id BIGINT NULL（KB 删除前的原始 kb_id，用于孤儿会话检测）
- conversations 表新增 original_kb_name VARCHAR(128) NULL（KB 删除前的原始名称，用于 Banner 展示）
- 存量数据无需回填（已被 FK SET NULL 清空的 kb_id 不可恢复，新列默认 NULL）

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('original_kb_id', sa.BigInteger(), nullable=True, comment='KB 删除前的原始 kb_id，用于孤儿会话检测'))
    op.add_column('conversations', sa.Column('original_kb_name', sa.String(128), nullable=True, comment='KB 删除前的原始名称，用于孤儿会话 Banner 展示'))


def downgrade() -> None:
    op.drop_column('conversations', 'original_kb_name')
    op.drop_column('conversations', 'original_kb_id')
