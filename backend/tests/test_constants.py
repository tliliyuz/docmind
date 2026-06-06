"""配置常量定位测试

集中管理所有配置常量的赋值验证，
防止在分散的测试文件中凑用例数（对齐 CLAUDE.md「常数重言禁分散」）。
Phase 4.1 后常量统一迁移到 app.config.settings。
"""

from app.config import settings
from app.rag.prompt_builder import SYSTEM_PROMPT_TEMPLATE


class TestConstants:
    """配置常量赋值验证"""

    def test_默认rrf_k值为60(self):
        assert settings.RRF_K == 60

    def test_默认rerank_top_k为5(self):
        assert settings.RERANK_TOP_K == 5

    def test_默认prompt_context_tokens为3000(self):
        assert settings.PROMPT_MAX_CONTEXT_TOKENS == 3000

    def test_默认最大chunk数为5(self):
        assert settings.PROMPT_MAX_CHUNKS == 5

    def test_默认chunk_size为1000(self):
        assert settings.CHUNK_SIZE == 1000

    def test_默认chunk_overlap为150(self):
        assert settings.CHUNK_OVERLAP == 150

    def test_默认bm25_top_k为10(self):
        assert settings.BM25_TOP_K == 10

    def test_默认vector_top_k为10(self):
        assert settings.VECTOR_TOP_K == 10

    def test_默认heartbeat_interval为15(self):
        assert settings.SSE_HEARTBEAT_INTERVAL == 15

    def test_默认idempotency_lock_ttl为600(self):
        assert settings.IDEMPOTENCY_LOCK_TTL == 600

    def test_prompt模板包含必要元素(self):
        """SYSTEM_PROMPT_TEMPLATE 应包含知识库助手提示和占位符"""
        assert "企业知识库助手" in SYSTEM_PROMPT_TEMPLATE
        assert "{context}" in SYSTEM_PROMPT_TEMPLATE
        assert "来源" in SYSTEM_PROMPT_TEMPLATE
