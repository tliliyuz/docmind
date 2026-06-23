"""CoarseRanker 粗排层单元测试 — ADR-024

覆盖 CoarseRanker.rank() 核心逻辑：
- 正常过滤 / 全通过 / 全拒绝 / 空候选 / 边界值 / 排序验证
- 异常降级 / embedding 透传 / 配置项一致性
"""

import math
from unittest.mock import patch

import pytest

from app.rag.coarse_ranker import CoarseRanker
from app.rag.retriever import RetrievalOutput, RetrievalResult


# ==================== 测试辅助函数 ====================


def _make_result(
    doc_id: int,
    chunk_index: int,
    content: str,
    score: float = 0.0,
    embedding: list[float] | None = None,
    page: int | None = None,
    doc_name: str = "",
) -> RetrievalResult:
    """构造 RetrievalResult 测试数据"""
    return RetrievalResult(
        doc_id=doc_id,
        chunk_index=chunk_index,
        content=content,
        score=score,
        page=page,
        doc_name=doc_name,
        embedding=embedding,
    )


def _make_output(
    results: list[RetrievalResult],
    query_embedding: list[float] | None = None,
) -> RetrievalOutput:
    """构造 RetrievalOutput 测试数据"""
    return RetrievalOutput(
        results=results,
        total=len(results),
        stats={"test": True},
        fusion_method="rrf",
        query_embedding=query_embedding,
    )


# 简化的 4 维向量（便于手算验证余弦相似度）
QV = [1.0, 0.0, 0.0, 0.0]  # query vector — 沿 x 轴
EMB_SAME = [1.0, 0.0, 0.0, 0.0]    # 完全相同 → cosine_sim = 1.0
EMB_ORTH = [0.0, 1.0, 0.0, 0.0]    # 正交 → cosine_sim = 0.0
EMB_OPPO = [-1.0, 0.0, 0.0, 0.0]   # 相反 → cosine_sim = -1.0
EMB_45DEG = [1.0, 1.0, 0.0, 0.0]   # 45° → cosine_sim ≈ 0.7071
EMB_60DEG = [0.5, 0.866, 0.0, 0.0] # 60° → cosine_sim ≈ 0.5


# ==================== 正常过滤测试 ====================


class TestCoarseRankerNormalFilter:
    """正常过滤场景"""

    @patch("app.rag.coarse_ranker.settings")
    def test_部分候选低于阈值被过滤(self, mock_settings):
        """P55-CR.1: 10 候选，部分低于阈值 → 过滤低分 + 排序 + 截断"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "高相关", score=1.0, embedding=EMB_SAME),   # sim=1.0 ✓
            _make_result(2, 0, "中相关", score=0.8, embedding=EMB_45DEG),  # sim≈0.707 ✓
            _make_result(3, 0, "低相关", score=0.5, embedding=EMB_60DEG),  # sim=0.5 ✓
            _make_result(4, 0, "正交", score=0.3, embedding=EMB_ORTH),      # sim≈0.0 ✗
            _make_result(5, 0, "相反", score=0.1, embedding=EMB_OPPO),      # sim=-1.0 ✗
            _make_result(6, 0, "高相关2", score=0.9, embedding=EMB_45DEG),  # sim≈0.707 ✓
            _make_result(7, 0, "无embedding", score=0.6, embedding=None),   # sim=阈值 ✓
            _make_result(8, 0, "低相关2", score=0.4, embedding=EMB_ORTH),   # sim≈0.0 ✗
            _make_result(9, 0, "中相关2", score=0.7, embedding=EMB_60DEG),  # sim=0.5 ✓
            _make_result(10, 0, "高相关3", score=0.85, embedding=EMB_SAME), # sim=1.0 ✓
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        # 过滤后应有 7 条（3 条低于 0.3 被过滤：chunk 4/5/8）
        assert result.total == 7
        assert len(result.results) == 7

        # 排序验证：第一条相似度最高（1.0）
        assert result.results[0].doc_id in (1, 10)  # sim=1.0 的两条

        # 无 embedding 的不应被过滤
        no_emb_ids = {r.doc_id for r in result.results if r.embedding is None}
        assert 7 in no_emb_ids

        # 低于阈值的确认不在结果中
        result_ids = {r.doc_id for r in result.results}
        assert 4 not in result_ids  # sim≈0.0
        assert 5 not in result_ids  # sim=-1.0
        assert 8 not in result_ids  # sim≈0.0

    @patch("app.rag.coarse_ranker.settings")
    def test_全部高于阈值全部保留(self, mock_settings):
        """P55-CR.2: 全部高于阈值 → 全部保留，按相似度降序"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.8, embedding=EMB_45DEG),  # sim≈0.707
            _make_result(2, 0, "B", score=0.9, embedding=EMB_SAME),   # sim=1.0
            _make_result(3, 0, "C", score=0.7, embedding=EMB_60DEG),  # sim=0.5
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        assert result.total == 3
        assert len(result.results) == 3

        # 按相似度降序：B(sim=1.0) > A(sim≈0.707) > C(sim=0.5)
        assert result.results[0].doc_id == 2  # sim=1.0
        assert result.results[1].doc_id == 1  # sim≈0.707
        assert result.results[2].doc_id == 3  # sim=0.5


# ==================== 降级与回退测试 ====================


class TestCoarseRankerFallback:
    """降级回退场景"""

    @patch("app.rag.coarse_ranker.settings")
    def test_全部低于阈值降级返回前top_k(self, mock_settings):
        """P55-CR.3: 全部低于阈值 → 返回原始结果的前 COARSE_TOP_K"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.5
        mock_settings.COARSE_TOP_K = 3

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.8, embedding=EMB_ORTH),  # sim≈0.0 < 0.5
            _make_result(2, 0, "B", score=0.7, embedding=EMB_OPPO),  # sim=-1.0 < 0.5
            _make_result(3, 0, "C", score=0.6, embedding=EMB_ORTH),  # sim≈0.0 < 0.5
            _make_result(4, 0, "D", score=0.5, embedding=EMB_ORTH),  # sim≈0.0 < 0.5
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        # 全部被过滤 → 降级返回原始前 3 条（保持原始顺序）
        assert result.total == 3
        assert len(result.results) == 3
        assert [r.doc_id for r in result.results] == [1, 2, 3]

    @patch("app.rag.coarse_ranker.settings")
    def test_空候选直接返回(self, mock_settings):
        """P55-CR.4: 输入 [] → 返回 []，不抛异常"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        output = _make_output([])
        result = ranker.rank(QV, output)

        assert result.total == 0
        assert result.results == []

    @patch("app.rag.coarse_ranker.settings")
    def test_候选不足top_k全部保留(self, mock_settings):
        """P55-CR.5: 3 候选，COARSE_TOP_K=15 → 返回全部，不截断"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.9, embedding=EMB_SAME),
            _make_result(2, 0, "B", score=0.8, embedding=EMB_45DEG),
            _make_result(3, 0, "C", score=0.7, embedding=EMB_60DEG),
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        assert result.total == 3
        assert len(result.results) == 3

    @patch("app.rag.coarse_ranker.settings")
    def test_异常降级返回原始结果(self, mock_settings):
        """P55-CR.8: 异常 → 返回原始候选列表，不抛异常"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.9, embedding=[1.0, 2.0, 3.0]),
        ]
        # query_embedding 维度不匹配（3 维 vs chunk 4 维）→ 触发异常
        bad_query_vec = [1.0, 2.0]  # 仅 2 维

        output = _make_output(results, query_embedding=bad_query_vec)
        # 不应抛异常
        result = ranker.rank(bad_query_vec, output)

        # 降级：返回原始结果
        assert result.total == 1
        assert result.results == results

    @patch("app.rag.coarse_ranker.settings")
    def test_已禁用时直接透传(self, mock_settings):
        """COARSE_RANK_ENABLED=False → 直接返回原始结果"""
        mock_settings.COARSE_RANK_ENABLED = False
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.5, embedding=EMB_ORTH),
            _make_result(2, 0, "B", score=0.8, embedding=EMB_SAME),
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        # 透传：保持原始顺序和内容
        assert result.results == results
        assert result.total == 2


# ==================== 边界值测试 ====================


class TestCoarseRankerBoundary:
    """边界值测试"""

    @patch("app.rag.coarse_ranker.settings")
    def test_阈值为零只做截断不过滤(self, mock_settings):
        """P55-CR.6: THRESHOLD=0 → 只做 top_k 截断，不过滤"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.0
        mock_settings.COARSE_TOP_K = 2

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.8, embedding=EMB_OPPO),  # sim=-1.0
            _make_result(2, 0, "B", score=0.9, embedding=EMB_SAME),   # sim=1.0
            _make_result(3, 0, "C", score=0.7, embedding=EMB_45DEG),  # sim≈0.707
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        # 全部通过阈值（0.0），截断到 top_2
        assert result.total == 2
        # 排序：B(1.0) > C(0.707)
        assert result.results[0].doc_id == 2
        assert result.results[1].doc_id == 3

    @patch("app.rag.coarse_ranker.settings")
    def test_相似度排序验证(self, mock_settings):
        """P55-CR.7: 输出严格按 cosine_sim 降序"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = -1.0  # 全部通过
        mock_settings.COARSE_TOP_K = 10

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "最低", score=0.1, embedding=EMB_OPPO),   # sim=-1.0
            _make_result(2, 0, "中等", score=0.6, embedding=EMB_60DEG),  # sim=0.5
            _make_result(3, 0, "最高", score=0.9, embedding=EMB_SAME),   # sim=1.0
            _make_result(4, 0, "偏高", score=0.8, embedding=EMB_45DEG),  # sim≈0.707
            _make_result(5, 0, "零", score=0.3, embedding=EMB_ORTH),     # sim≈0.0
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        sims = []
        query_norm = ranker._l2_normalize(QV)
        for r in result.results:
            emb_norm = ranker._l2_normalize(r.embedding)
            sims.append(ranker._dot_product(query_norm, emb_norm))

        # 严格降序
        for i in range(len(sims) - 1):
            assert sims[i] >= sims[i + 1], f"索引 {i} ({sims[i]}) 不小于 {i+1} ({sims[i+1]})"

        # 第一个应该是最高的
        assert result.results[0].doc_id == 3  # sim=1.0

    @patch("app.rag.coarse_ranker.settings")
    def test_filtered_below_rerank_top_k(self, mock_settings):
        """P55-CR.9: 过滤后仅剩 2 条（< RERANK_TOP_K=5）→ 返回过滤结果"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.6  # 较高阈值
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.9, embedding=EMB_SAME),   # sim=1.0 ✓
            _make_result(2, 0, "B", score=0.8, embedding=EMB_45DEG),  # sim≈0.707 ✓
            _make_result(3, 0, "C", score=0.7, embedding=EMB_60DEG),  # sim=0.5 ✗
            _make_result(4, 0, "D", score=0.6, embedding=EMB_ORTH),   # sim≈0.0 ✗
            _make_result(5, 0, "E", score=0.5, embedding=EMB_OPPO),   # sim=-1.0 ✗
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        # 仅 2 条通过阈值
        assert result.total == 2


# ==================== 数据完整性测试 ====================


class TestCoarseRankerDataIntegrity:
    """数据完整性与透传"""

    @patch("app.rag.coarse_ranker.settings")
    def test_embedding正确透传未修改(self, mock_settings):
        """P55-CR.10: 输出结果的 embedding 字段正确透传，未被修改"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        original_emb = [0.1, 0.2, 0.3, 0.4]
        results = [
            _make_result(1, 0, "A", score=0.9, embedding=original_emb),
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        assert result.total == 1
        assert result.results[0].embedding == original_emb
        # 验证是同一个引用（未被复制/修改）
        assert result.results[0].embedding is original_emb

    @patch("app.rag.coarse_ranker.settings")
    def test_输出保留原始元数据(self, mock_settings):
        """输出 RetrievalOutput 保留 stats 和 fusion_method"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 15

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.9, embedding=EMB_SAME),
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        assert result.stats == {"test": True}
        assert result.fusion_method == "rrf"
        assert result.query_embedding == QV

    @patch("app.rag.coarse_ranker.settings")
    def test_top_k截断验证(self, mock_settings):
        """COARSE_TOP_K=3，5 条候选全部通过阈值 → 截断到 3 条"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.3
        mock_settings.COARSE_TOP_K = 3

        ranker = CoarseRanker()
        results = [
            _make_result(1, 0, "A", score=0.6, embedding=EMB_60DEG),  # sim=0.5
            _make_result(2, 0, "B", score=0.9, embedding=EMB_SAME),   # sim=1.0
            _make_result(3, 0, "C", score=0.7, embedding=EMB_45DEG),  # sim≈0.707
            _make_result(4, 0, "D", score=0.8, embedding=EMB_45DEG),  # sim≈0.707
            _make_result(5, 0, "E", score=0.5, embedding=EMB_60DEG),  # sim=0.5
        ]

        output = _make_output(results, query_embedding=QV)
        result = ranker.rank(QV, output)

        assert result.total == 3
        # 前 3 条应为最高相似度的
        assert result.results[0].doc_id == 2  # sim=1.0
        # 3 和 4 相似度相同（≈0.707），顺序稳定即可


# ==================== 配置项测试 ====================


class TestCoarseRankerConfig:
    """配置项一致性测试"""

    @patch("app.rag.coarse_ranker.settings")
    def test_配置项从settings读取(self, mock_settings):
        """P55-CR.11: COARSE_RANK_ENABLED/THRESHOLD/TOP_K 从 config 读取"""
        mock_settings.COARSE_RANK_ENABLED = True
        mock_settings.COARSE_RANK_THRESHOLD = 0.25
        mock_settings.COARSE_TOP_K = 12

        ranker = CoarseRanker()

        assert ranker._enabled is True
        assert ranker._threshold == 0.25
        assert ranker._top_k == 12

    @patch("app.rag.coarse_ranker.settings")
    def test_配置项修改后新实例生效(self, mock_settings):
        """修改 settings 后新建 CoarseRanker 实例使用新值"""
        mock_settings.COARSE_RANK_ENABLED = False
        ranker1 = CoarseRanker()
        assert ranker1._enabled is False

        mock_settings.COARSE_RANK_ENABLED = True
        ranker2 = CoarseRanker()
        assert ranker2._enabled is True


# ==================== 余弦相似度计算单元测试 ====================


class TestCoarseRankerCosineSimilarity:
    """余弦相似度基础计算验证"""

    def test_l2_normalize_单位向量不变(self):
        """L2 归一化：单位向量保持不变"""
        ranker = CoarseRanker()
        vec = [1.0, 0.0, 0.0]
        normalized = ranker._l2_normalize(vec)
        assert normalized == pytest.approx(vec)

    def test_l2_normalize_非单位向量(self):
        """L2 归一化：非单位向量正确归一"""
        ranker = CoarseRanker()
        vec = [3.0, 4.0]  # L2 = 5
        normalized = ranker._l2_normalize(vec)
        assert normalized == pytest.approx([0.6, 0.8])

    def test_l2_normalize_零向量(self):
        """L2 归一化：零向量返回自身（防御性）"""
        ranker = CoarseRanker()
        vec = [0.0, 0.0, 0.0]
        normalized = ranker._l2_normalize(vec)
        assert normalized == vec

    def test_dot_product(self):
        """点积计算"""
        ranker = CoarseRanker()
        result = ranker._dot_product([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
        assert result == 32.0  # 1*4 + 2*5 + 3*6

    def test_cosine_similarity_exact(self):
        """余弦相似度：手算验证"""
        ranker = CoarseRanker()
        a_norm = ranker._l2_normalize([1.0, 0.0])
        b_norm = ranker._l2_normalize([0.5, math.sqrt(0.75)])  # 60°
        sim = ranker._dot_product(a_norm, b_norm)
        assert sim == pytest.approx(0.5, abs=1e-6)

    def test_cosine_similarity_identical(self):
        """余弦相似度：完全相同 = 1.0"""
        ranker = CoarseRanker()
        a_norm = ranker._l2_normalize([0.3, 0.4, 0.5, 0.6])
        b_norm = ranker._l2_normalize([0.3, 0.4, 0.5, 0.6])
        sim = ranker._dot_product(a_norm, b_norm)
        assert sim == pytest.approx(1.0, abs=1e-6)
