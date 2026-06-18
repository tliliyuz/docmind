"""chunks表新增(doc_id, chunk_index)复合索引

Revision ID: f5a6b7c8d9e0
Revises: 3bc9273cea34
Create Date: 2026-06-19

优化 BM25 评分后按 (doc_id, chunk_index) 批量取 chunk 原文的查询
（rag/bm25.py `_fetch_chunk_contents` 使用 tuple_.in_(pairs)）。
单列 idx_doc_id 在该复合条件查询下仅能过滤 doc_id，chunk_index 需回表比对；
复合索引可直接定位 (doc_id, chunk_index) 行，避免大 KB 场景下退化为按 doc_id 扫描。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'f5a6b7c8d9e0'
down_revision = '3bc9273cea34'
branch_labels = None
depends_on = None


def _index_exists(table_name: str, index_name: str) -> bool:
    """检查索引是否已存在（幂等辅助）"""
    bind = op.get_bind()
    result = bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :i"
    ), {"t": table_name, "i": index_name})
    return result.scalar() > 0


def upgrade() -> None:
    if not _index_exists("chunks", "idx_chunks_doc_id_chunk_index"):
        op.create_index(
            "idx_chunks_doc_id_chunk_index",
            "chunks",
            ["doc_id", "chunk_index"],
        )


def downgrade() -> None:
    if _index_exists("chunks", "idx_chunks_doc_id_chunk_index"):
        op.drop_index("idx_chunks_doc_id_chunk_index", table_name="chunks")
