"""共享测试工厂函数 — 供各 Phase 测试模块导入复用

抽取原则：
- 跨文件重复使用的工厂 → 集中到此模块
- 仅在单一测试文件内使用的辅助函数 → 保留在原文件
"""

from unittest.mock import AsyncMock, MagicMock

import httpx

from app.models.enums import DocumentStatus

MOCK_DIM = 1024  # DashScope text-embedding-v3 默认维度


# ==================== DB / Session（test_tasks / test_bm25 共用） ====================


def make_mock_doc(status=DocumentStatus.UPLOADED, current_stage=None, last_success_batch=0,
                  file_path="/tmp/test.pdf", file_type="pdf", kb_id=1, doc_id=1):
    """构造 mock Document 对象"""
    doc = MagicMock()
    doc.id = doc_id
    doc.kb_id = kb_id
    doc.status = status
    doc.current_stage = current_stage
    doc.last_success_batch = last_success_batch
    doc.file_path = file_path
    doc.file_type = file_type
    doc.chunk_count = 0
    doc.error_msg = None
    return doc


def make_mock_chunks(count: int = 5, doc_id: int = 1):
    """构造 mock Chunk 对象列表"""
    chunks = []
    for i in range(count):
        c = MagicMock()
        c.id = i + 1
        c.chunk_index = i
        c.content = f"chunk {i}"
        c.chroma_id = f"doc_{doc_id}_chunk_{i}"
        chunks.append(c)
    return chunks


def make_mock_embed_result(count: int = 1, dim: int = MOCK_DIM):
    """构造 EmbedResult（真实 dataclass，含 1024 维向量）"""
    from app.rag.embedder import EmbedResult
    return EmbedResult(
        embeddings=[[0.1] * dim for _ in range(count)],
        token_counts=[5] * count,
        total_tokens=count * 5,
    )


def setup_mock_db(doc, chunks=None):
    """构造完整的 mock AsyncSession"""
    db = AsyncMock()
    db.get = AsyncMock(return_value=doc)

    exec_result = MagicMock()
    if chunks is not None:
        exec_result.scalars.return_value.all.return_value = chunks
    else:
        exec_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=exec_result)

    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()

    return db


def mock_async_session_ctx(db):
    """构造 async_session() 上下文管理器"""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


# ==================== Embedding API（test_embedder / test_retriever 共用） ====================


def make_mock_embed_response(embeddings_count: int = 2, total_tokens: int = 10, dim: int = MOCK_DIM):
    """构造 DashScope Embedding API 成功响应 dict"""
    return {
        "output": {
            "embeddings": [
                {"text_index": i, "embedding": [0.1 * (i + 1)] * dim}
                for i in range(embeddings_count)
            ]
        },
        "usage": {"total_tokens": total_tokens},
        "request_id": "test-request-id",
    }


def make_mock_httpx_response(status_code: int = 200, json_data: dict | None = None):
    """构造 Mock httpx.Response"""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.return_value = make_mock_embed_response()
    response.text = "mock response text"
    return response


# ==================== ChromaDB（test_retriever 及其他 Phase 4+ 共用） ====================


def make_mock_chroma_results(ids=None, documents=None, distances=None, metadatas=None):
    """构造 ChromaDB collection.query() 返回结构"""
    if ids is None:
        ids = [["doc_1_chunk_0", "doc_1_chunk_1"]]
    if documents is None:
        documents = [["这是第一段内容", "这是第二段内容"]]
    if distances is None:
        distances = [[0.2, 0.5]]
    if metadatas is None:
        metadatas = [[
            {"kb_id": 1, "doc_id": 1, "chunk_index": 0},
            {"kb_id": 1, "doc_id": 1, "chunk_index": 1},
        ]]
    return {
        "ids": ids,
        "documents": documents,
        "distances": distances,
        "metadatas": metadatas,
    }
