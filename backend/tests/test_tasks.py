"""Celery 入库流水线任务测试 — 断点恢复 + last_success_batch 续传 + 阶段检测"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingest.tasks import (
    RESUMABLE_STAGES,
    _ingest_document_async,
)
from app.models.enums import DocumentStatus
from tests.helpers import (
    make_mock_doc,
    make_mock_chunks,
    make_mock_embed_result,
    setup_mock_db,
    mock_async_session_ctx,
)


# ==================== RESUMABLE_STAGES ====================


class TestResumableStages:
    """断点恢复阶段常量测试"""

    def test_chunking_done_为可恢复阶段(self):
        assert "chunking_done" in RESUMABLE_STAGES

    def test_embedding_为可恢复阶段(self):
        assert "embedding" in RESUMABLE_STAGES

    def test_vector_storing_为可恢复阶段(self):
        assert "vector_storing" in RESUMABLE_STAGES

    def test_parsing_不在可恢复阶段(self):
        assert "parsing" not in RESUMABLE_STAGES

    def test_chunking_不在可恢复阶段(self):
        assert "chunking" not in RESUMABLE_STAGES


# ==================== 阶段恢复 ====================


class TestStageResume:
    """阶段检测与断点恢复测试"""

    @pytest.mark.asyncio
    async def test_chunking_done阶段_跳过解析分块进入embedding(self):
        """文档 current_stage=chunking_done，应跳过解析+分块，直接进入 Embedding 从 batch 0 开始"""
        doc = make_mock_doc(
            status=DocumentStatus.CHUNKING,
            current_stage="chunking_done",
            last_success_batch=0,
        )
        chunks = make_mock_chunks(5)
        embed_result = make_mock_embed_result(5)
        db = setup_mock_db(doc, chunks)

        with patch("app.ingest.tasks.async_session", return_value=mock_async_session_ctx(db)):
            with patch("app.ingest.tasks.acquire_idempotency_lock", return_value=True):
                with patch("app.ingest.tasks.release_idempotency_lock"):
                    with patch("app.ingest.tasks.embed_chunks", AsyncMock(return_value=embed_result)):
                        with patch("app.ingest.tasks.get_collection"):
                            with patch("app.ingest.tasks.parse_document") as mock_parse:
                                result = await _ingest_document_async(1)
                                mock_parse.assert_not_called()

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_vector_storing阶段_清理chroma并重做embedding(self):
        """文档 current_stage=vector_storing，应清理 ChromaDB + 从 batch 0 重做 Embedding"""
        doc = make_mock_doc(
            status=DocumentStatus.VECTOR_STORING,
            current_stage="vector_storing",
            last_success_batch=3,
        )
        chunks = make_mock_chunks(5)
        embed_result = make_mock_embed_result(5)
        db = setup_mock_db(doc, chunks)

        mock_collection = MagicMock()

        with patch("app.ingest.tasks.async_session", return_value=mock_async_session_ctx(db)):
            with patch("app.ingest.tasks.acquire_idempotency_lock", return_value=True):
                with patch("app.ingest.tasks.release_idempotency_lock"):
                    with patch("app.ingest.tasks.embed_chunks", AsyncMock(return_value=embed_result)):
                        with patch("app.ingest.tasks.get_collection", return_value=mock_collection):
                            result = await _ingest_document_async(1)

        # 验证 ChromaDB 清理被调用
        mock_collection.delete.assert_called_with(where={"doc_id": 1})
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_vector_storing阶段_chroma清理失败标记FAILED(self):
        """vector_storing 阶段 ChromaDB 清理失败应标记 FAILED 并返回"""
        doc = make_mock_doc(
            status=DocumentStatus.VECTOR_STORING,
            current_stage="vector_storing",
            last_success_batch=3,
        )
        chunks = make_mock_chunks(5)
        db = setup_mock_db(doc, chunks)

        mock_collection = MagicMock()
        mock_collection.delete.side_effect = RuntimeError("ChromaDB connection failed")

        with patch("app.ingest.tasks.async_session", return_value=mock_async_session_ctx(db)):
            with patch("app.ingest.tasks.acquire_idempotency_lock", return_value=True):
                with patch("app.ingest.tasks.release_idempotency_lock"):
                    with patch("app.ingest.tasks.get_collection", return_value=mock_collection):
                        result = await _ingest_document_async(1)

        assert result["status"] == "failed"
        assert doc.status == DocumentStatus.FAILED
        assert "ChromaDB" in doc.error_msg


# ==================== last_success_batch checkpoint ====================


class TestLastSuccessBatchCheckpoint:
    """last_success_batch checkpoint 更新测试"""

    @pytest.mark.asyncio
    async def test_embedding每批成功后更新last_success_batch(self):
        """验证 embedding 阶段每批成功后会更新 doc.last_success_batch"""
        doc = make_mock_doc(
            status=DocumentStatus.EMBEDDING,
            current_stage="embedding",
            last_success_batch=0,
        )
        # 6 chunks, batch_size=2 → 3 batches
        chunks = make_mock_chunks(6)
        embed_result = make_mock_embed_result(2)  # each batch has 2 chunks
        db = setup_mock_db(doc, chunks)

        # 6 chunks / batch_size=2 = 3 batches
        # 每批完成后 commit 一次（更新 last_success_batch）
        # 全部完成后 commit 一次（最终状态 + token 回写 + KB 统计）
        # 预期至少 4 次 commit: 3 per-batch + 1 final

        with patch("app.ingest.tasks.async_session", return_value=mock_async_session_ctx(db)):
            with patch("app.ingest.tasks.acquire_idempotency_lock", return_value=True):
                with patch("app.ingest.tasks.release_idempotency_lock"):
                    with patch("app.ingest.tasks.embed_chunks", AsyncMock(return_value=embed_result)):
                        with patch("app.ingest.tasks.get_collection"):
                            with patch("app.ingest.tasks.settings") as mock_settings:
                                mock_settings.EMBED_BATCH_SIZE = 2
                                mock_settings.CHROMA_BATCH_SIZE = 20
                                result = await _ingest_document_async(1)

        assert result["status"] == "completed"
        # 3 per-batch commits + 1 final commit = 4
        assert db.commit.call_count >= 4

    @pytest.mark.asyncio
    async def test_last_success_batch为0时从第一批开始(self):
        """last_success_batch=0 时，embedding 从第 0 批开始"""
        doc = make_mock_doc(
            status=DocumentStatus.EMBEDDING,
            current_stage="embedding",
            last_success_batch=0,
        )
        chunks = make_mock_chunks(3)
        embed_result = make_mock_embed_result(3)
        db = setup_mock_db(doc, chunks)

        with patch("app.ingest.tasks.async_session", return_value=mock_async_session_ctx(db)):
            with patch("app.ingest.tasks.acquire_idempotency_lock", return_value=True):
                with patch("app.ingest.tasks.release_idempotency_lock"):
                    mock_embed = AsyncMock(return_value=embed_result)
                    with patch("app.ingest.tasks.embed_chunks", mock_embed):
                        with patch("app.ingest.tasks.get_collection"):
                            result = await _ingest_document_async(1)

        assert result["status"] == "completed"
        # 3 chunks, batch_size 默认 20 → 1 batch
        assert mock_embed.call_count == 1


# ==================== 幂等锁集成 ====================


class TestIdempotencyLockIntegration:
    """幂等锁与流水线集成测试"""

    @pytest.mark.asyncio
    async def test_锁被占用时返回locked(self):
        """幂等锁已被占用时，任务应返回 locked 状态"""
        with patch("app.ingest.tasks.acquire_idempotency_lock", return_value=False):
            with patch("app.ingest.tasks.release_idempotency_lock"):
                result = await _ingest_document_async(1)

        assert result["status"] == "locked"
        assert result["doc_id"] == 1
