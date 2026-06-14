"""配置常量约束关系测试

集中验证配置常量之间的约束关系（而非单个值的硬编码重言式），
防止在分散的测试文件中凑用例数（对齐 CLAUDE.md「常数重言禁分散」）。
Phase 4.1 后常量统一迁移到 app.config.settings。
"""

import pytest

from app.config import settings
from app.rag.prompt_builder import SYSTEM_PROMPT_TEMPLATE


class TestConstantsConstraints:
    """配置常量约束关系验证"""

    def test_chunk_overlap_小于_chunk_size(self):
        """overlap 必须小于 chunk_size，否则分块无意义"""
        assert settings.CHUNK_OVERLAP < settings.CHUNK_SIZE

    def test_rerank_top_k_不超过检索总量(self):
        """rerank 取 top-k 不应超过双路检索返回的总量"""
        dual_retrieval_total = settings.BM25_TOP_K + settings.VECTOR_TOP_K
        assert settings.RERANK_TOP_K <= dual_retrieval_total

    def test_heartbeat_interval_小于_60秒(self):
        """SSE 心跳间隔应小于 60 秒，防止连接超时"""
        assert 0 < settings.SSE_HEARTBEAT_INTERVAL < 60

    def test_幂等锁_TTL_为正数(self):
        assert settings.IDEMPOTENCY_LOCK_TTL > 0

    @pytest.mark.parametrize("key", [
        "RRF_K", "RERANK_TOP_K", "PROMPT_MAX_CONTEXT_TOKENS",
        "PROMPT_MAX_CHUNKS", "CHUNK_SIZE", "CHUNK_OVERLAP",
        "BM25_TOP_K", "VECTOR_TOP_K", "SSE_HEARTBEAT_INTERVAL",
        "IDEMPOTENCY_LOCK_TTL",
    ])
    def test_核心配置项均为正数(self, key):
        assert getattr(settings, key) > 0


class TestPromptTemplate:
    """Prompt 模板业务约束验证"""

    def test_prompt模板包含助手身份和上下文占位符(self):
        assert "企业知识库助手" in SYSTEM_PROMPT_TEMPLATE
        assert "{context}" in SYSTEM_PROMPT_TEMPLATE
        assert "来源" in SYSTEM_PROMPT_TEMPLATE
