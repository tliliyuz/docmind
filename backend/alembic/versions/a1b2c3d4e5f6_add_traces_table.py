"""Phase 5: traces 表 — 链路追踪

Revision ID: a1b2c3d4e5f6
Revises: d2ed146c7d8e
Create Date: 2026-06-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd2ed146c7d8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('traces',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trace_id', sa.String(length=64), nullable=False, comment='UUID 追踪 ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
        sa.Column('conversation_id', sa.BigInteger(), nullable=True, comment='会话 ID（可为空）'),
        sa.Column('kb_id', sa.BigInteger(), nullable=True, comment='知识库 ID'),
        sa.Column('question', sa.Text(), nullable=True, comment='用户问题'),
        sa.Column('status', sa.String(length=32), nullable=False, comment='状态：success / error / partial'),
        sa.Column('intent_type', sa.String(length=32), nullable=True, comment='顶层字段：KNOWLEDGE / CASUAL / META'),
        sa.Column('intent_method', sa.String(length=32), nullable=True, comment='顶层字段：regex / llm_flash / llm_pro'),
        sa.Column('response_mode', sa.String(length=32), nullable=True, comment='顶层字段：RAG / DIRECT_LLM / META / CASUAL / FALLBACK'),
        sa.Column('total_duration_ms', sa.Integer(), nullable=True, comment='总耗时（毫秒）'),
        sa.Column('intent', sa.JSON(), nullable=True, comment='意图识别阶段详情'),
        sa.Column('rewrite', sa.JSON(), nullable=True, comment='问题重写阶段详情'),
        sa.Column('retrieve', sa.JSON(), nullable=True, comment='检索阶段详情（细粒度拆分：vector/bm25/fusion/match_sentence）'),
        sa.Column('rerank', sa.JSON(), nullable=True, comment='Rerank 阶段详情'),
        sa.Column('generate', sa.JSON(), nullable=True, comment='LLM 生成阶段详情（不存 output）'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息（status=error 时）'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True, comment='创建时间（UTC）'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trace_id'),
    )
    op.create_index('idx_created_at', 'traces', ['created_at'], unique=False)
    op.create_index('idx_created_status', 'traces', ['created_at', 'status'], unique=False)
    op.create_index('idx_created_intent', 'traces', ['created_at', 'intent_type'], unique=False)
    op.create_index('idx_created_response', 'traces', ['created_at', 'response_mode'], unique=False)
    op.create_index('idx_user_created', 'traces', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_user_created', table_name='traces')
    op.drop_index('idx_created_response', table_name='traces')
    op.drop_index('idx_created_intent', table_name='traces')
    op.drop_index('idx_created_status', table_name='traces')
    op.drop_index('idx_created_at', table_name='traces')
    op.drop_table('traces')
