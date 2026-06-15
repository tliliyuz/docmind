"""离线检索评估脚本 — BM25 vs 向量 vs RRF 的 Recall@K / MRR / Precision@K 对比

对齐 TESTING.md §5：
- Recall@5 ≥ 0.85, Recall@10 ≥ 0.90
- MRR ≥ 0.70, Precision@5 ≥ 0.60
- 每次检索代码变更后运行

用法:
  cd backend
  python tests/eval/eval_retrieval.py --kb-id 1                # 指定知识库 ID
  python tests/eval/eval_retrieval.py --kb-id 1 --top-k 10     # 自定义 top_k
  python tests/eval/eval_retrieval.py --kb-id 1 --output md    # 输出 Markdown 报告
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

# 确保 backend 目录在 sys.path 中（支持从项目根目录或 tests/ 目录运行）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import select

from app.core.chroma_client import get_vector_store
from app.core.database import async_session
from app.core.redis_client import get_async_redis
from app.models.document import Document
from app.rag.bm25 import BM25Retriever
from app.rag.fusion import rrf_fusion
from app.rag.retriever import RetrievalOutput, RetrievalResult, VectorRetriever
from tests.eval.eval_test_set import EVAL_TEST_SET

logger = logging.getLogger(__name__)


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class EvalResult:
    """单题评估结果"""
    question_id: int
    question: str
    expected_docs: list[str]
    retrieved_docs: list[str]          # 检索到的文档名（去重）
    recalled_docs: list[str]            # 命中的期望文档名
    recall_5: float                     # Recall@5
    recall_10: float                    # Recall@10
    mrr: float                          # 第一个相关 chunk 的倒数排名
    precision_5: float                  # Precision@5
    rank_of_first_relevant: int | None  # 第一个相关结果的排名（1-based）


@dataclass
class RetrieverEvalSummary:
    """单个检索器的评估汇总"""
    name: str
    results: list[EvalResult] = field(default_factory=list)
    recall_5_avg: float = 0.0
    recall_10_avg: float = 0.0
    mrr_avg: float = 0.0
    precision_5_avg: float = 0.0
    recall_5_pass: bool = False   # ≥ 0.85
    recall_10_pass: bool = False  # ≥ 0.90
    mrr_pass: bool = False        # ≥ 0.70
    precision_5_pass: bool = False  # ≥ 0.60


# ============================================================================
# 评估引擎
# ============================================================================

class RetrievalEvaluator:
    """离线检索评估器

    对单个知识库运行完整的三路检索评估（向量 / BM25 / RRF 融合），
    计算 Recall@K、MRR、Precision@K 并输出对比报告。
    """

    def __init__(self, kb_id: int, top_k: int = 10):
        self.kb_id = kb_id
        self.top_k = top_k
        # 懒加载
        self._vector_retriever: VectorRetriever | None = None
        self._bm25_retriever: BM25Retriever | None = None
        # 文件名 → doc_id 映射（由 load_doc_map 填充）
        self._filename_to_doc_id: dict[str, int] = {}

    @property
    def vector_retriever(self) -> VectorRetriever:
        if self._vector_retriever is None:
            self._vector_retriever = VectorRetriever(get_vector_store())
        return self._vector_retriever

    async def _ensure_bm25_retriever(self) -> BM25Retriever:
        """懒加载 BM25Retriever（需要异步获取 Redis 客户端）"""
        if self._bm25_retriever is None:
            async_redis = await get_async_redis()
            self._bm25_retriever = BM25Retriever(
                async_redis=async_redis,
                session_factory=async_session,
            )
        return self._bm25_retriever

    async def load_doc_map(self) -> None:
        """从 MySQL 加载 kb_id 下所有文档的 filename → doc_id 映射"""
        async with async_session() as db:
            result = await db.execute(
                select(Document.id, Document.filename)
                .where(Document.kb_id == self.kb_id)
            )
            rows = result.all()

        self._filename_to_doc_id = {row.filename: row.id for row in rows}
        logger.info(
            "文档映射已加载: kb_id=%d, %d 个文档",
            self.kb_id, len(self._filename_to_doc_id),
        )
        if self._filename_to_doc_id:
            logger.debug("文档列表:\n  %s",
                         "\n  ".join(self._filename_to_doc_id.keys()))

    def _resolve_expected_doc_ids(self, expected_docs: list[str]) -> list[int]:
        """将期望文档文件名列表解析为 doc_id 列表。

        未在知识库中找到的文档名会被警告并跳过。
        """
        doc_ids: list[int] = []
        for filename in expected_docs:
            doc_id = self._filename_to_doc_id.get(filename)
            if doc_id is not None:
                doc_ids.append(doc_id)
            else:
                logger.warning("期望文档未在知识库中找到: %s", filename)
        return doc_ids

    @staticmethod
    def _compute_metrics(
        question_id: int,
        question: str,
        expected_docs: list[str],
        expected_doc_ids: list[int],
        retrieved: RetrievalOutput,
    ) -> EvalResult:
        """对单次检索结果计算全部指标。

        Args:
            question_id: 问题 ID
            question: 问题文本
            expected_docs: 期望文档文件名列表
            expected_doc_ids: 期望文档的 doc_id 列表
            retrieved: 检索器返回的结果

        Returns:
            EvalResult: 包含所有指标的计算结果
        """
        results = retrieved.results

        # 提取检索到的文档名（去重，保持出现顺序）
        seen_doc_ids: set[int] = set()
        retrieved_doc_names: list[str] = []
        for r in results:
            if r.doc_id not in seen_doc_ids:
                seen_doc_ids.add(r.doc_id)
                retrieved_doc_names.append(r.doc_name or f"doc_{r.doc_id}")

        # 命中检查
        expected_set = set(expected_doc_ids) if expected_doc_ids else set()

        # Recall@5 / Recall@10
        if expected_set:
            top5_ids = set(r.doc_id for r in results[:5])
            top10_ids = set(r.doc_id for r in results[:10])
            recall_5 = len(top5_ids & expected_set) / len(expected_set)
            recall_10 = len(top10_ids & expected_set) / len(expected_set)
        else:
            # 超出知识库范围的题目：无期望文档 → Recall 恒为 1.0（正确行为是返回空/不相关）
            recall_5 = 1.0
            recall_10 = 1.0

        # MRR: 第一个相关结果的倒数排名
        rank_of_first: int | None = None
        mrr = 0.0
        for i, r in enumerate(results):
            if r.doc_id in expected_set:
                rank_of_first = i + 1
                mrr = 1.0 / rank_of_first
                break
        # 如果 expected_set 非空但没有命中，MRR = 0（rank_of_first 保持 None）

        # Precision@5
        if results[:5]:
            if expected_set:
                precision_5 = len(set(r.doc_id for r in results[:5]) & expected_set) / 5
            else:
                # 无期望文档时 Precision 应为 0（检索到的都是不相关的）
                precision_5 = 0.0
        else:
            precision_5 = 0.0

        # 命中的期望文档名
        recalled_docs: list[str] = []
        for r in results:
            if r.doc_id in expected_set:
                name = r.doc_name or f"doc_{r.doc_id}"
                if name not in recalled_docs:
                    recalled_docs.append(name)

        return EvalResult(
            question_id=question_id,
            question=question,
            expected_docs=list(expected_docs),
            retrieved_docs=retrieved_doc_names,
            recalled_docs=recalled_docs,
            recall_5=recall_5,
            recall_10=recall_10,
            mrr=mrr,
            precision_5=precision_5,
            rank_of_first_relevant=rank_of_first,
        )

    async def evaluate_retriever(
        self,
        name: str,
        search_fn,
    ) -> RetrieverEvalSummary:
        """对单个检索器运行全部 30 题的评估。

        Args:
            name: 检索器名称（用于报告）
            search_fn: async callable (question, kb_id, top_k) → RetrievalOutput

        Returns:
            RetrieverEvalSummary: 汇总指标
        """
        summary = RetrieverEvalSummary(name=name)
        results: list[EvalResult] = []

        for item in EVAL_TEST_SET:
            qid = item["id"]
            question = item["question"]
            expected_docs = item["expected_docs"]
            expected_doc_ids = self._resolve_expected_doc_ids(expected_docs)

            try:
                retrieved = await search_fn(question, self.kb_id, self.top_k)
            except Exception:
                logger.exception("检索异常: question_id=%d, retriever=%s", qid, name)
                # 异常时使用空结果
                retrieved = RetrievalOutput()

            eval_result = self._compute_metrics(
                question_id=qid,
                question=question,
                expected_docs=expected_docs,
                expected_doc_ids=expected_doc_ids,
                retrieved=retrieved,
            )
            results.append(eval_result)

        # 汇总统计（out-of-scope 题目排除在指标计算之外）
        scoped: list[EvalResult] = []
        for r, item in zip(results, EVAL_TEST_SET):
            if item["difficulty"] != "out-of-scope":
                scoped.append(r)

        if scoped:
            summary.recall_5_avg = mean(r.recall_5 for r in scoped)
            summary.recall_10_avg = mean(r.recall_10 for r in scoped)
            summary.mrr_avg = mean(r.mrr for r in scoped)
            summary.precision_5_avg = mean(r.precision_5 for r in scoped)
        else:
            # 全部 out-of-scope（不太可能但防御）
            summary.recall_5_avg = 0.0
            summary.recall_10_avg = 0.0
            summary.mrr_avg = 0.0
            summary.precision_5_avg = 0.0

        summary.results = results
        summary.recall_5_pass = summary.recall_5_avg >= 0.85
        summary.recall_10_pass = summary.recall_10_avg >= 0.90
        summary.mrr_pass = summary.mrr_avg >= 0.70
        summary.precision_5_pass = summary.precision_5_avg >= 0.60

        return summary

    async def run_full_evaluation(self) -> dict[str, RetrieverEvalSummary]:
        """运行完整的三路检索评估。

        Returns:
            dict: {"vector": ..., "bm25": ..., "rrf": ...}
        """
        # 先加载文档映射
        await self.load_doc_map()

        if not self._filename_to_doc_id:
            logger.warning(
                "知识库 %d 中无文档，无法运行评估。请先上传 knowledge_samples/ 中的文档。",
                self.kb_id,
            )

        print(f"\n{'='*70}")
        print(f"  离线检索评估 — kb_id={self.kb_id}, top_k={self.top_k}")
        print(f"  测试集: {len(EVAL_TEST_SET)} 题")
        print(f"  知识库文档数: {len(self._filename_to_doc_id)}")
        print(f"{'='*70}\n")

        # 向量检索
        print("🔍 运行向量检索评估...")
        vector_summary = await self.evaluate_retriever(
            "向量检索 (ChromaDB cosine)",
            lambda q, kb, k: self.vector_retriever.search(q, kb, top_k=k),
        )

        # BM25 检索
        print("🔍 运行 BM25 检索评估...")
        bm25 = await self._ensure_bm25_retriever()
        bm25_summary = await self.evaluate_retriever(
            "BM25 关键词 (jieba + rank-bm25)",
            lambda q, kb, k: bm25.search(q, kb, top_k=k),
        )

        # RRF 融合（向量 + BM25）
        print("🔍 运行 RRF 融合评估...")
        rrf_summary = await self._evaluate_rrf()

        return {
            "vector": vector_summary,
            "bm25": bm25_summary,
            "rrf": rrf_summary,
        }

    async def _evaluate_rrf(self) -> RetrieverEvalSummary:
        """评估 RRF 融合（向量 + BM25 → RRF 融合）"""
        summary = RetrieverEvalSummary(name="RRF 融合 (k=60)")
        results: list[EvalResult] = []
        bm25 = await self._ensure_bm25_retriever()

        for item in EVAL_TEST_SET:
            qid = item["id"]
            expected_docs = item["expected_docs"]
            expected_doc_ids = self._resolve_expected_doc_ids(expected_docs)

            try:
                vector_out = await self.vector_retriever.search(
                    item["question"], self.kb_id, top_k=self.top_k,
                )
                bm25_out = await bm25.search(
                    item["question"], self.kb_id, top_k=self.top_k,
                )
                fused = rrf_fusion(vector_out, bm25_out)
            except Exception:
                logger.exception("RRF 检索异常: question_id=%d", qid)
                fused = RetrievalOutput()

            eval_result = self._compute_metrics(
                question_id=qid,
                question=item["question"],
                expected_docs=expected_docs,
                expected_doc_ids=expected_doc_ids,
                retrieved=fused,
            )
            results.append(eval_result)

        # 汇总（排除 out-of-scope）
        scoped = []
        for r, item in zip(results, EVAL_TEST_SET):
            if item["difficulty"] != "out-of-scope":
                scoped.append(r)

        if scoped:
            summary.recall_5_avg = mean(r.recall_5 for r in scoped)
            summary.recall_10_avg = mean(r.recall_10 for r in scoped)
            summary.mrr_avg = mean(r.mrr for r in scoped)
            summary.precision_5_avg = mean(r.precision_5 for r in scoped)

        summary.results = results
        summary.recall_5_pass = summary.recall_5_avg >= 0.85
        summary.recall_10_pass = summary.recall_10_avg >= 0.90
        summary.mrr_pass = summary.mrr_avg >= 0.70
        summary.precision_5_pass = summary.precision_5_avg >= 0.60

        return summary


# ============================================================================
# 报告输出
# ============================================================================

TARGETS = {
    "recall_5": (0.85, "≥ 0.85"),
    "recall_10": (0.90, "≥ 0.90"),
    "mrr": (0.70, "≥ 0.70"),
    "precision_5": (0.60, "≥ 0.60"),
}


def _pass_fail(value: float, target: float) -> str:
    return "✅" if value >= target else "❌"


def print_summary_table(summaries: dict[str, RetrieverEvalSummary]) -> None:
    """打印汇总对比表"""
    print(f"\n{'='*70}")
    print("  评估结果汇总")
    print(f"{'='*70}\n")

    header = f"{'指标':<18} {'目标':<10} {'向量检索':<14} {'BM25':<14} {'RRF融合':<14}"
    print(header)
    print("-" * 70)

    metrics = [
        ("recall_5_avg", "Recall@5"),
        ("recall_10_avg", "Recall@10"),
        ("mrr_avg", "MRR"),
        ("precision_5_avg", "Precision@5"),
    ]

    for attr, label in metrics:
        target_val, target_str = TARGETS[attr.replace("_avg", "")]
        vec_val = getattr(summaries["vector"], attr)
        bm25_val = getattr(summaries["bm25"], attr)
        rrf_val = getattr(summaries["rrf"], attr)

        row = (
            f"{label:<18} {target_str:<10} "
            f"{vec_val:.4f} {_pass_fail(vec_val, target_val):<6}  "
            f"{bm25_val:.4f} {_pass_fail(bm25_val, target_val):<6}  "
            f"{rrf_val:.4f} {_pass_fail(rrf_val, target_val):<6}"
        )
        print(row)

    print("-" * 70)
    print("  ✅ = 达标    ❌ = 未达标")
    print(f"\n评估范围: 排除 2 题 out-of-scope，共 28 题参与指标计算\n")


def print_per_question_table(summaries: dict[str, RetrieverEvalSummary]) -> None:
    """打印逐题明细表"""
    print(f"\n{'='*70}")
    print("  逐题 Recall@5 明细")
    print(f"{'='*70}\n")

    header = f"{'ID':<4} {'难度':<12} {'类型':<16} {'向量':<8} {'BM25':<8} {'RRF':<8} {'期望文档'}"
    print(header)
    print("-" * 100)

    for i, item in enumerate(EVAL_TEST_SET):
        vec_r = summaries["vector"].results[i]
        bm25_r = summaries["bm25"].results[i]
        rrf_r = summaries["rrf"].results[i]

        expected_str = ", ".join(item["expected_docs"]) if item["expected_docs"] else "(无—超出范围)"
        row = (
            f"{item['id']:<4} {item['difficulty']:<12} {item['type']:<16} "
            f"{vec_r.recall_5:.4f}  {bm25_r.recall_5:.4f}  {rrf_r.recall_5:.4f}  "
            f"{expected_str}"
        )
        print(row)

    print()


def print_failure_detail(summaries: dict[str, RetrieverEvalSummary]) -> None:
    """打印未召回期望文档的题目详情"""
    print(f"\n{'='*70}")
    print("  未完全召回分析（Recall@5 < 1.0 的题目）")
    print(f"{'='*70}\n")

    for retriever_key, label in [("vector", "向量检索"), ("bm25", "BM25"), ("rrf", "RRF 融合")]:
        summary = summaries[retriever_key]
        partials = [r for r in summary.results if r.recall_5 < 1.0 and r.expected_docs]
        if not partials:
            print(f"  {label}: 全部完全召回 ✅")
            continue

        print(f"  {label} ({len(partials)} 题未完全召回):")
        for r in partials:
            missing = [d for d in r.expected_docs if d not in r.recalled_docs]
            print(f"    Q{r.question_id}: 缺失 {missing}")
            print(f"       问题: {r.question[:50]}...")
            print(f"       检索到: {r.retrieved_docs[:5] or '(无)'}")
        print()


# ============================================================================
# CLI 入口
# ============================================================================

async def main_async(kb_id: int, top_k: int) -> None:
    """异步主流程"""
    evaluator = RetrievalEvaluator(kb_id=kb_id, top_k=top_k)
    summaries = await evaluator.run_full_evaluation()

    print_summary_table(summaries)
    print_per_question_table(summaries)
    print_failure_detail(summaries)

    # 判断是否全部达标
    all_pass = all(
        s.recall_5_pass and s.recall_10_pass and s.mrr_pass and s.precision_5_pass
        for s in summaries.values()
    )
    if all_pass:
        print("🎉 全部指标达标！\n")
    else:
        print("⚠️  部分指标未达标，详见上方标记 ❌ 的项目。\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DocMind 离线检索评估 — BM25 vs 向量 vs RRF 融合对比",
    )
    parser.add_argument(
        "--kb-id", type=int, required=True,
        help="目标知识库 ID",
    )
    parser.add_argument(
        "--top-k", type=int, default=10,
        help="检索返回数量（默认 10）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(main_async(kb_id=args.kb_id, top_k=args.top_k))


if __name__ == "__main__":
    main()
