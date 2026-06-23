"""Ragas 评估脚本单元测试

覆盖 RagasEvaluator 初始化、管线调用、指标计算、报告输出、CLI 参数解析。
Mock ragas 外部依赖，验证评估数据流正确性。
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保 backend 目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.rag.knowledge_pipeline import KnowledgePipelineResult
from app.rag.prompt_builder import PromptBuildResult
from app.rag.retriever import RetrievalOutput, RetrievalResult
from tests.eval.eval_ragas import (
    RagasEvaluator,
    RagasEvalSummary,
    RagasQuestionResult,
    TARGETS,
    DEFAULT_METRICS,
    compute_context_precision_doc,
    compute_context_recall,
    print_summary_table,
    print_per_question_table,
    export_json,
    export_markdown,
)


# ============================================================================
# 辅助函数
# ============================================================================

def _make_retrieval_output(doc_ids=None, count=5):
    """构造标准检索结果"""
    if doc_ids is None:
        doc_ids = [1, 1, 2, 3, 4]
    results = []
    for i in range(min(count, len(doc_ids))):
        results.append(RetrievalResult(
            doc_id=doc_ids[i],
            chunk_index=i,
            content=f"chunk {i} 的测试内容",
            score=0.9 - i * 0.05,
            page=1,
        ))
    return RetrievalOutput(results=results, total=len(results))


def _make_pipeline_result(answer_contexts=True):
    """构造 KnowledgePipelineResult，含可控的 prompt 和检索结果"""
    if answer_contexts:
        prompt = PromptBuildResult(
            system_prompt="你是一个知识库助手",
            user_prompt="测试问题？",
            used_chunks=[{"content": "chunk 0 的测试内容", "doc_id": 1, "chunk_index": 0}],
            total_context_tokens=100,
            chunks_count=1,
            history_messages=[],
        )
    else:
        # 模拟 REJECT 路径
        prompt = PromptBuildResult(
            system_prompt="",
            user_prompt="",
            used_chunks=[],
            total_context_tokens=0,
            chunks_count=0,
            history_messages=[],
        )

    return KnowledgePipelineResult(
        reranked_output=_make_retrieval_output(),
        prompt_result=prompt,
        doc_map={1: "测试文档.md", 2: "其他文档.md"},
        evidence_review=None,
    )


# ============================================================================
# 自定义上下文指标计算
# ============================================================================

class TestComputeContextPrecisionDoc:
    """compute_context_precision_doc — 文档级上下文精度计算（诊断列）"""

    def test_所有结果来自期望文档(self):
        """全部 top-K 结果来自期望文档 → 精度 1.0"""
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="c1", score=0.9),
            RetrievalResult(doc_id=1, chunk_index=1, content="c2", score=0.8),
        ]
        precision = compute_context_precision_doc(results, {1}, k=5)
        assert precision == 1.0

    def test_部分结果来自期望文档(self):
        """混合来源 → 精度按比例计算"""
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="c1", score=0.9),
            RetrievalResult(doc_id=2, chunk_index=0, content="c2", score=0.8),
            RetrievalResult(doc_id=1, chunk_index=1, content="c3", score=0.7),
        ]
        precision = compute_context_precision_doc(results, {1}, k=3)
        assert precision == 2.0 / 3.0

    def test_期望文档为空(self):
        """无期望文档 → 精度 0.0"""
        results = [RetrievalResult(doc_id=1, chunk_index=0, content="c1", score=0.9)]
        precision = compute_context_precision_doc(results, set(), k=5)
        assert precision == 0.0

    def test_检索结果为空(self):
        """无检索结果 → 精度 0.0"""
        precision = compute_context_precision_doc([], {1}, k=5)
        assert precision == 0.0

    def test_top_k截断(self):
        """仅评估 top-K 范围内的结果"""
        results = [RetrievalResult(doc_id=2, chunk_index=i, content="c", score=0.9) for i in range(10)]
        # 期望 doc 1 不在 top-5 中
        precision = compute_context_precision_doc(results, {1}, k=5)
        assert precision == 0.0


class TestComputeContextRecall:
    """compute_context_recall — 上下文召回率计算"""

    def test_全部期望文档被检索到(self):
        """所有期望文档都有 chunk 被检索 → 召回率 1.0"""
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="c1", score=0.9),
            RetrievalResult(doc_id=2, chunk_index=0, content="c2", score=0.8),
        ]
        recall = compute_context_recall(results, {1, 2})
        assert recall == 1.0

    def test_部分期望文档未检索到(self):
        """部分期望文档缺失 → 召回率按比例"""
        results = [RetrievalResult(doc_id=1, chunk_index=0, content="c1", score=0.9)]
        recall = compute_context_recall(results, {1, 2, 3})
        assert recall == 1.0 / 3.0

    def test_期望文档为空(self):
        """无期望文档 → 召回率 0.0"""
        results = [RetrievalResult(doc_id=1, chunk_index=0, content="c1", score=0.9)]
        recall = compute_context_recall(results, set())
        assert recall == 0.0


# ============================================================================
# RagasEvaluator 初始化
# ============================================================================

class TestRagasEvaluatorInit:
    """RagasEvaluator — 初始化配置"""

    def test_默认模型为flash(self):
        """未指定 model 时使用 flash 模型"""
        evaluator = RagasEvaluator(kb_id=1)
        from app.config import settings
        assert evaluator._answer_model == settings.LLM_FLASH_MODEL

    def test_pro模型选择(self):
        """指定 pro 模型"""
        evaluator = RagasEvaluator(kb_id=1, llm_model="pro")
        from app.config import settings
        assert evaluator._answer_model == settings.LLM_MODEL

    def test_自定义指标列表(self):
        """指定部分指标"""
        evaluator = RagasEvaluator(kb_id=1, metrics=["faithfulness"])
        assert evaluator.metrics == ["faithfulness"]

    def test_默认启用全部指标(self):
        """不指定 metrics 时默认启用全部"""
        evaluator = RagasEvaluator(kb_id=1)
        assert evaluator.metrics == DEFAULT_METRICS


# ============================================================================
# RagasEvaluator 核心流程（Mock ragas）
# ============================================================================

class TestRagasEvaluatorCore:
    """RagasEvaluator — 核心评估流程（Mock 外部依赖）"""

    @pytest.mark.asyncio
    async def test_capture_answer正常流程(self):
        """管线 + LLM 正常返回答案和上下文"""
        evaluator = RagasEvaluator(kb_id=1, llm_model="flash")

        # Mock KnowledgePipeline
        mock_pipeline = MagicMock()
        mock_pipeline.execute_knowledge = AsyncMock(
            return_value=_make_pipeline_result()
        )
        evaluator._pipeline = mock_pipeline

        # Mock chat_completion
        with patch(
            "tests.eval.eval_ragas.chat_completion",
            new_callable=AsyncMock,
        ) as mock_llm:
            from app.core.llm import LLMResult
            mock_llm.return_value = LLMResult(
                content="这是测试答案", reasoning_content="",
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
            )

            answer, contexts, reranked = await evaluator.capture_answer_and_contexts(
                "测试问题？"
            )

        assert answer == "这是测试答案"
        assert len(contexts) == 5
        assert contexts[0] == "chunk 0 的测试内容"
        assert reranked.total == 5

    @pytest.mark.asyncio
    async def test_capture_answer_REJECT路径(self):
        """REJECT 路径：空 prompt 时跳过 LLM 调用"""
        evaluator = RagasEvaluator(kb_id=1, llm_model="flash")

        mock_pipeline = MagicMock()
        mock_pipeline.execute_knowledge = AsyncMock(
            return_value=_make_pipeline_result(answer_contexts=False)
        )
        evaluator._pipeline = mock_pipeline

        answer, contexts, reranked = await evaluator.capture_answer_and_contexts(
            "无相关文档的问题？"
        )

        assert answer == ""
        assert len(contexts) == 5
        assert reranked.total == 5

    @pytest.mark.asyncio
    async def test_evaluate_all基本流程(self):
        """evaluate_all 遍历全部非 out-of-scope 题目"""
        evaluator = RagasEvaluator(kb_id=1, llm_model="flash")

        # Mock doc_map 加载
        evaluator._filename_to_doc_id = {
            "入职指南.md": 1,
            "请假与考勤制度.md": 2,
            "报销制度.md": 3,
            "VPN配置指南.md": 4,
            "打印机使用说明.md": 5,
            "访客登记流程.md": 6,
            "代码评审标准.md": 7,
        }

        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.execute_knowledge = AsyncMock(
            return_value=_make_pipeline_result()
        )
        evaluator._pipeline = mock_pipeline

        # Mock chat_completion 和 ragas
        with patch(
            "tests.eval.eval_ragas.chat_completion",
            new_callable=AsyncMock,
        ) as mock_llm:
            from app.core.llm import LLMResult
            mock_llm.return_value = LLMResult(
                content="测试答案", reasoning_content="",
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
            )

            # Mock ragas 指标（避免实际加载 ragas 库）
            with patch.object(
                evaluator, "_init_ragas", new_callable=AsyncMock,
            ):
                with patch.object(
                    evaluator, "_score_ragas_metrics",
                    new_callable=AsyncMock,
                ) as mock_score:
                    mock_score.return_value = {
                        "faithfulness": 0.85,
                        "answer_relevancy": 0.72,
                        "context_precision": 0.80,
                    }

                    summary = await evaluator.evaluate_all()

        # 验证汇总（28 题，排除 2 题 out-of-scope）
        assert summary.total == 28
        assert summary.evaluated == 28
        assert summary.failed == 0
        assert len(summary.per_question) == 28

        # 验证指标平均值
        assert summary.faithfulness_mean == 0.85
        assert summary.answer_relevancy_mean == 0.72
        assert summary.context_precision_mean is not None
        assert summary.context_precision_doc_mean is not None
        assert summary.context_recall_mean is not None

    @pytest.mark.asyncio
    async def test_evaluate_all_单题LLM异常不崩溃(self):
        """单题 LLM 调用异常应记录 error 并继续"""
        evaluator = RagasEvaluator(kb_id=1, llm_model="flash")

        evaluator._filename_to_doc_id = {"入职指南.md": 1}

        mock_pipeline = MagicMock()
        mock_pipeline.execute_knowledge = AsyncMock(
            side_effect=Exception("LLM 调用超时")
        )
        evaluator._pipeline = mock_pipeline

        with patch.object(evaluator, "load_doc_map", new_callable=AsyncMock):
            with patch.object(evaluator, "_init_ragas", new_callable=AsyncMock):
                with patch.object(evaluator, "_score_ragas_metrics", new_callable=AsyncMock):
                    summary = await evaluator.evaluate_all()

        # 全部 28 题都应该记录 error
        assert summary.failed == 28
        assert summary.evaluated == 0
        for r in summary.per_question:
            assert r.error is not None

    @pytest.mark.asyncio
    async def test_ragas_metrics空答案返回None(self):
        """空答案时 ragas 指标返回 None 而非崩溃"""
        evaluator = RagasEvaluator(kb_id=1)

        with patch.object(evaluator, "_init_ragas", new_callable=AsyncMock):
            scores = await evaluator._score_ragas_metrics(
                question="测试问题",
                answer="",  # 空答案
                contexts=["上下文内容"],
                reference="",
            )

        # 空答案应跳过 ragas 评估
        assert scores.get("faithfulness") is None
        assert scores.get("answer_relevancy") is None
        assert scores.get("context_precision") is None

    @pytest.mark.asyncio
    async def test_evaluate_all_AR零分标记与调整均值(self):
        """AR=0.0 题应标记 ar_flagged，调整均值排除 0 分题，ar_zero_count 计数正确"""
        evaluator = RagasEvaluator(kb_id=1, llm_model="flash")

        evaluator._filename_to_doc_id = {"入职指南.md": 1}

        # Mock capture_answer_and_contexts 绕开真实 DB/管线，
        # 本用例只验证 AR=0.0 的标记与汇总统计逻辑
        reranked = _make_retrieval_output()
        with patch.object(
            evaluator, "capture_answer_and_contexts",
            new_callable=AsyncMock,
            return_value=("测试答案", [], reranked),
        ):
            with patch.object(evaluator, "load_doc_map", new_callable=AsyncMock):
                with patch.object(evaluator, "_init_ragas", new_callable=AsyncMock):
                    call_count = {"n": 0}

                    async def _fake_score(question, answer, contexts, reference=""):
                        # 第 2、5 题模拟 judge 误判 noncommittal 导致 AR=0.0
                        call_count["n"] += 1
                        ar = 0.0 if call_count["n"] in (2, 5) else 0.72
                        return {"faithfulness": 0.85, "answer_relevancy": ar, "context_precision": 0.80}

                    with patch.object(
                        evaluator, "_score_ragas_metrics",
                        new_callable=AsyncMock, side_effect=_fake_score,
                    ):
                        summary = await evaluator.evaluate_all()

        # 28 题中 2 题 AR=0.0
        assert summary.ar_zero_count == 2
        flagged = [r for r in summary.per_question if r.ar_flagged]
        assert len(flagged) == 2
        # 原始均值被 2 个 0 拉低
        assert summary.answer_relevancy_mean is not None
        assert summary.answer_relevancy_mean < 0.72
        # 调整均值仅含非零题，应等于 0.72
        assert summary.answer_relevancy_adjusted_mean == 0.72
        # 失败计数仍为 0（0.0 是判定分而非异常）
        assert summary.failed == 0


# ============================================================================
# 报告输出
# ============================================================================

class TestReportOutput:
    """报告输出 — 控制台 / JSON / Markdown"""

    def _make_summary(self):
        """构造测试用汇总"""
        return RagasEvalSummary(
            total=2,
            evaluated=2,
            failed=0,
            faithfulness_mean=0.85,
            answer_relevancy_mean=0.72,
            context_precision_mean=0.90,
            context_precision_doc_mean=0.80,
            context_recall_mean=0.80,
            per_question=[
                RagasQuestionResult(
                    question_id=1, question="Q1", difficulty="easy",
                    question_type="精确查询", answer="答案1",
                    contexts=["c1", "c2"],
                    faithfulness=0.90, answer_relevancy=0.75,
                    context_precision=1.0, context_precision_doc=0.80,
                    context_recall=1.0,
                ),
                RagasQuestionResult(
                    question_id=2, question="Q2", difficulty="medium",
                    question_type="语义匹配", answer="答案2",
                    contexts=["c3"],
                    faithfulness=0.80, answer_relevancy=0.69,
                    context_precision=0.80, context_precision_doc=0.60,
                    context_recall=0.60,
                ),
            ],
        )

    def test_print_summary_table不抛异常(self, capsys):
        """print_summary_table 正常输出不崩溃"""
        summary = self._make_summary()
        print_summary_table(summary)
        captured = capsys.readouterr()
        assert "Faithfulness" in captured.out
        assert "0.8500" in captured.out

    def test_print_per_question_table不抛异常(self, capsys):
        """print_per_question_table 正常输出不崩溃"""
        summary = self._make_summary()
        print_per_question_table(summary)
        captured = capsys.readouterr()
        assert "Q1" in captured.out
        assert "0.9000" in captured.out

    def test_export_json文件内容正确(self, tmp_path):
        """JSON 导出包含完整字段"""
        summary = self._make_summary()
        output_path = str(tmp_path / "test_output.json")
        export_json(summary, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["summary"]["total"] == 2
        assert data["summary"]["faithfulness_mean"] == 0.85
        assert len(data["per_question"]) == 2
        assert data["per_question"][0]["question_id"] == 1
        assert data["per_question"][0]["faithfulness"] == 0.90
        assert "timestamp" in data

    def test_export_markdown文件内容正确(self, tmp_path):
        """Markdown 导出包含指标表格"""
        summary = self._make_summary()
        output_path = str(tmp_path / "test_output.md")
        export_markdown(summary, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Ragas 端到端评估报告" in content
        assert "Faithfulness" in content
        assert "0.8500" in content
        assert "Q1" in content


# ============================================================================
# TARGETS 阈值
# ============================================================================

class TestTargets:
    """评估目标阈值定义"""

    def test_全部指标有阈值定义(self):
        """DEFAULT_METRICS 中每个指标在 TARGETS 中都有定义"""
        for metric in DEFAULT_METRICS:
            assert metric in TARGETS, f"{metric} 缺少阈值定义"

    def test_阈值范围合理(self):
        """所有阈值在 0-1 之间"""
        for key, (value, _) in TARGETS.items():
            assert 0.0 <= value <= 1.0, f"{key} 阈值 {value} 不在 [0,1] 范围内"
