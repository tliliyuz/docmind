"""Phase 3 模块常量定位测试

集中管理所有 DEFAULT_* 常量和关键模板字符串的赋值验证，
防止在分散的测试文件中凑用例数（对齐 CLAUDE.md「常数重言禁分散」）。
"""

from app.rag.fusion import DEFAULT_RRF_K
from app.rag.prompt_builder import (
    DEFAULT_MAX_CHUNKS,
    DEFAULT_MAX_CONTEXT_TOKENS,
    SYSTEM_PROMPT_TEMPLATE,
)
from app.rag.reranker import DEFAULT_RERANK_TOP_K


class TestConstants:
    """模块常量赋值验证"""

    def test_默认rrf_k值为60(self):
        assert DEFAULT_RRF_K == 60

    def test_默认rerank_top_k为5(self):
        assert DEFAULT_RERANK_TOP_K == 5

    def test_默认token上限为3000(self):
        assert DEFAULT_MAX_CONTEXT_TOKENS == 3000

    def test_默认最大chunk数为5(self):
        assert DEFAULT_MAX_CHUNKS == 5

    def test_prompt模板包含必要元素(self):
        """SYSTEM_PROMPT_TEMPLATE 应包含知识库助手提示和占位符"""
        assert "企业知识库助手" in SYSTEM_PROMPT_TEMPLATE
        assert "{context}" in SYSTEM_PROMPT_TEMPLATE
        assert "来源" in SYSTEM_PROMPT_TEMPLATE
