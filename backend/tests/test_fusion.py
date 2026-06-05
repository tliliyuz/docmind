"""RRF 多路融合排序单元测试 — 覆盖核心融合逻辑

对齐 ROADMAP.md §5.5 Phase 3 测试：
- k=60 标准合并
- 单路为空
- 两路均空
- 排名相同处理
- 多路融合
- 参数化 k 值
"""

import pytest

from app.rag.fusion import rrf_fusion
from app.rag.retriever import RetrievalOutput, RetrievalResult


def _make_result(doc_id: int, chunk_index: int, content: str, score: float = 0.0) -> RetrievalResult:
    """构造 RetrievalResult 测试数据"""
    return RetrievalResult(
        doc_id=doc_id,
        chunk_index=chunk_index,
        content=content,
        score=score,
    )


def _make_output(results: list[RetrievalResult]) -> RetrievalOutput:
    """构造 RetrievalOutput 测试数据"""
    return RetrievalOutput(results=results, total=len(results))


# ==================== rrf_fusion 核心逻辑测试 ====================


class TestRrfFusion:
    """rrf_fusion 核心逻辑测试"""

    def test_两路标准合并(self):
        """两路结果正常融合，按 RRF 分数降序排列"""
        # 向量检索结果
        vector_results = _make_output([
            _make_result(1, 0, "文档A", 0.9),
            _make_result(1, 1, "文档B", 0.8),
            _make_result(2, 0, "文档C", 0.7),
        ])

        # BM25 检索结果
        bm25_results = _make_output([
            _make_result(1, 0, "文档A", 5.0),  # 排名第1
            _make_result(2, 0, "文档C", 3.0),  # 排名第2
            _make_result(1, 1, "文档B", 2.0),  # 排名第3
        ])

        result = rrf_fusion(vector_results, bm25_results, k=60)

        assert result.total == 3
        assert len(result.results) == 3

        # 验证 RRF 分数计算
        # 文档A: 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.03279
        # 文档B: 1/(60+2) + 1/(60+3) = 1/62 + 1/63 ≈ 0.03226
        # 文档C: 1/(60+3) + 1/(60+2) = 1/63 + 1/62 ≈ 0.03226

        # 文档A 应该排在第一位（两路都是第1名）
        assert result.results[0].doc_id == 1
        assert result.results[0].chunk_index == 0
        assert abs(result.results[0].score - (1/61 + 1/61)) < 1e-6

        # 文档B 和 文档C 分数相同，但顺序可能因排序稳定性而异
        scores = [r.score for r in result.results[1:]]
        assert all(abs(s - (1/62 + 1/63)) < 1e-6 for s in scores)

    def test_单路为空返回另一路(self):
        """单路为空时，直接返回另一路结果"""
        vector_results = _make_output([
            _make_result(1, 0, "文档A", 0.9),
            _make_result(1, 1, "文档B", 0.8),
        ])

        empty_results = _make_output([])

        result = rrf_fusion(vector_results, empty_results, k=60)

        assert result.total == 2
        assert len(result.results) == 2
        assert result.results[0].doc_id == 1
        assert result.results[0].chunk_index == 0

    def test_两路均为空返回空结果(self):
        """两路均为空时，返回空结果"""
        empty1 = _make_output([])
        empty2 = _make_output([])

        result = rrf_fusion(empty1, empty2, k=60)

        assert result.total == 0
        assert result.results == []

    def test_三路融合(self):
        """支持三路检索结果融合"""
        results1 = _make_output([
            _make_result(1, 0, "文档A", 0.9),
            _make_result(1, 1, "文档B", 0.8),
        ])

        results2 = _make_output([
            _make_result(1, 0, "文档A", 5.0),
            _make_result(2, 0, "文档C", 3.0),
        ])

        results3 = _make_output([
            _make_result(1, 1, "文档B", 10.0),
            _make_result(1, 0, "文档A", 8.0),
        ])

        result = rrf_fusion(results1, results2, results3, k=60)

        assert result.total == 3

        # 文档A: 1/(60+1) + 1/(60+1) + 1/(60+2) = 1/61 + 1/61 + 1/62
        expected_a = 1/61 + 1/61 + 1/62
        assert abs(result.results[0].score - expected_a) < 1e-6

    def test_排名相同时的处理(self):
        """多个 chunk 在同一路中排名相同时，RRF 分数应正确累加"""
        # 注意：RRF 基于排名，不是分数
        results = _make_output([
            _make_result(1, 0, "文档A", 0.9),  # 排名第1
            _make_result(1, 1, "文档B", 0.9),  # 排名第2（分数相同但排名不同）
            _make_result(2, 0, "文档C", 0.8),  # 排名第3
        ])

        result = rrf_fusion(results, results, k=60)  # 同一路融合两次

        assert result.total == 3

        # 文档A: 1/(60+1) + 1/(60+1) = 2/61
        assert abs(result.results[0].score - (2/61)) < 1e-6

        # 文档B: 1/(60+2) + 1/(60+2) = 2/62
        assert abs(result.results[1].score - (2/62)) < 1e-6

        # 文档C: 1/(60+3) + 1/(60+3) = 2/63
        assert abs(result.results[2].score - (2/63)) < 1e-6

    def test_相同chunk出现在不同路中(self):
        """相同 chunk 在不同路中出现时，RRF 分数应累加"""
        # 向量检索：文档A 排名第1
        vector_results = _make_output([
            _make_result(1, 0, "文档A", 0.9),
            _make_result(1, 1, "文档B", 0.8),
        ])

        # BM25 检索：文档A 排名第2
        bm25_results = _make_output([
            _make_result(1, 1, "文档B", 5.0),  # 排名第1
            _make_result(1, 0, "文档A", 3.0),  # 排名第2
        ])

        result = rrf_fusion(vector_results, bm25_results, k=60)

        assert result.total == 2

        # 文档A: 1/(60+1) + 1/(60+2) = 1/61 + 1/62
        expected_a = 1/61 + 1/62
        assert abs(result.results[0].score - expected_a) < 1e-6

        # 文档B: 1/(60+2) + 1/(60+1) = 1/62 + 1/61
        expected_b = 1/62 + 1/61
        assert abs(result.results[1].score - expected_b) < 1e-6

    def test_参数化k值(self):
        """k 值可配置化"""
        results1 = _make_output([
            _make_result(1, 0, "文档A", 0.9),
        ])

        results2 = _make_output([
            _make_result(1, 0, "文档A", 5.0),
        ])

        # k=10
        result_k10 = rrf_fusion(results1, results2, k=10)
        expected_k10 = 1/(10+1) + 1/(10+1)
        assert abs(result_k10.results[0].score - expected_k10) < 1e-6

        # k=100
        result_k100 = rrf_fusion(results1, results2, k=100)
        expected_k100 = 1/(100+1) + 1/(100+1)
        assert abs(result_k100.results[0].score - expected_k100) < 1e-6

    def test_无参数调用(self):
        """无参数调用时返回空结果"""
        result = rrf_fusion()
        assert result.total == 0
        assert result.results == []

    def test_结果保留原始metadata(self):
        """融合结果应保留原始 chunk 的 metadata（page, doc_name）"""
        results = _make_output([
            _make_result(1, 0, "文档A", 0.9),
        ])

        # 手动设置 page 和 doc_name
        results.results[0].page = 5
        results.results[0].doc_name = "测试文档.pdf"

        result = rrf_fusion(results, results, k=60)

        assert result.results[0].page == 5
        assert result.results[0].doc_name == "测试文档.pdf"

    def test_空结果不影响其他路(self):
        """部分路为空时，不影响其他路的融合"""
        results1 = _make_output([
            _make_result(1, 0, "文档A", 0.9),
        ])

        empty = _make_output([])

        results2 = _make_output([
            _make_result(1, 0, "文档A", 5.0),
        ])

        result = rrf_fusion(results1, empty, results2, k=60)

        assert result.total == 1
        # 文档A: 1/(60+1) + 1/(60+1) = 2/61（空路不贡献分数）
        assert abs(result.results[0].score - (2/61)) < 1e-6


# ==================== 边界情况测试 ====================


class TestEdgeCases:
    """边界情况测试"""

    def test_单chunk单路(self):
        """单 chunk 单路融合"""
        results = _make_output([
            _make_result(1, 0, "文档A", 0.9),
        ])

        result = rrf_fusion(results, results, k=60)

        assert result.total == 1
        assert result.results[0].doc_id == 1
        assert result.results[0].chunk_index == 0

    def test_大量chunks(self):
        """大量 chunks 融合性能测试"""
        # 生成 100 个 chunk
        results = _make_output([
            _make_result(i // 10, i % 10, f"文档{i}", 0.9 - i * 0.001)
            for i in range(100)
        ])

        result = rrf_fusion(results, results, k=60)

        assert result.total == 100

        # 验证分数递减
        for i in range(len(result.results) - 1):
            assert result.results[i].score >= result.results[i + 1].score
