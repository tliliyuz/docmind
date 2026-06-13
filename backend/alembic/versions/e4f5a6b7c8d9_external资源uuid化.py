"""external资源uuid化

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否已存在（幂等辅助）"""
    bind = op.get_bind()
    result = bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
    ), {"t": table_name, "c": column_name})
    return result.scalar() > 0


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    """检查唯一约束是否已存在（幂等辅助）"""
    bind = op.get_bind()
    result = bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.table_constraints "
        "WHERE table_schema = DATABASE() AND table_name = :t "
        "AND constraint_name = :c AND constraint_type = 'UNIQUE'"
    ), {"t": table_name, "c": constraint_name})
    return result.scalar() > 0


def _add_uuid_column(table_name: str) -> None:
    """为表添加 uuid 列并回填（幂等：列已存在则仅补齐回填和约束）"""
    if not _column_exists(table_name, 'uuid'):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column(
                'uuid', sa.String(36), nullable=True,
                comment='外部暴露标识符（UUID v4），API/URL 使用'
            ))

    # 回填：无论列是新建还是已存在，都补跑一次（WHERE uuid IS NULL 保证幂等）
    op.execute(f"UPDATE {table_name} SET uuid = UUID() WHERE uuid IS NULL")

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column('uuid', type_=sa.String(36), nullable=False,
                              server_default=sa.text("(UUID())"))
        if not _constraint_exists(table_name, 'idx_uuid'):
            batch_op.create_unique_constraint('idx_uuid', ['uuid'])


def upgrade() -> None:
    # ── 1. knowledge_bases 新增 uuid 列 ──
    _add_uuid_column('knowledge_bases')

    # ── 2. documents 新增 uuid 列 ──
    _add_uuid_column('documents')

    # ── 3. conversations 新增 uuid 列 ──
    _add_uuid_column('conversations')

    # ── 4. conversations 新增 original_kb_uuid 列 ──
    if not _column_exists('conversations', 'original_kb_uuid'):
        with op.batch_alter_table('conversations') as batch_op:
            batch_op.add_column(sa.Column(
                'original_kb_uuid', sa.String(36), nullable=True,
                comment='KB 删除前的原始 UUID，用于孤儿会话审计追踪'
            ))

    # 从 knowledge_bases 表回填 original_kb_uuid
    op.execute("""
        UPDATE conversations c
        JOIN knowledge_bases kb ON c.original_kb_id = kb.id
        SET c.original_kb_uuid = kb.uuid
        WHERE c.original_kb_id IS NOT NULL
    """)


def downgrade() -> None:
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.drop_constraint('idx_uuid', type_='unique')
        batch_op.drop_column('uuid')
        batch_op.drop_column('original_kb_uuid')

    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_constraint('idx_uuid', type_='unique')
        batch_op.drop_column('uuid')

    with op.batch_alter_table('knowledge_bases') as batch_op:
        batch_op.drop_constraint('idx_uuid', type_='unique')
        batch_op.drop_column('uuid')
