"""Ragas 自动化评估脚本 — 端到端生成质量评估（Faithfulness / Answer Relevancy / Context Precision / Context Recall）

对齐 TESTING.md §5a 评估层次设计（阈值经首轮 Ragas 全量评估校准，2026-06-23）：
- Faithfulness ≥ 0.80（对标人工评分"准确性" 4/5）
- Answer Relevancy ≥ 0.80（对标人工评分"完整性" 4/5）
- Context Precision ≥ 0.80（ragas 原生 LLM-based，检索精度语义升级）
- Context Recall ≥ 0.80（检索召回率语义降级修正）

用法:
  cd backend
  python tests/eval/eval_ragas.py --kb-id 1                          # 使用内部整数 ID
  python tests/eval/eval_ragas.py --kb-id da63f069-...              # 使用 UUID（自动解析为内部 ID）
  python tests/eval/eval_ragas.py --kb-id 1 --top-k 10              # 自定义 top_k
  python tests/eval/eval_ragas.py --kb-id 1 --model pro             # 使用 pro 模型生成答案
  python tests/eval/eval_ragas.py --kb-id 1 --output json           # JSON 输出
  python tests/eval/eval_ragas.py --kb-id 1 --output md             # Markdown 报告
  python tests/eval/eval_ragas.py --kb-id 1 --metrics faithfulness,answer_relevancy  # 选择性指标
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

# 确保 backend 目录在 sys.path 中（支持从项目根目录或 tests/ 目录运行）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import select

from app.config import settings
from app.core.chroma_client import get_vector_store
from app.core.database import async_session
from app.core.llm import chat_completion, LLMResult
from app.core.redis_client import get_async_redis
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.rag.bm25 import BM25Retriever
from app.rag.knowledge_pipeline import KnowledgePipeline, KnowledgePipelineResult
from app.rag.retriever import RetrievalOutput, VectorRetriever
from app.rag.reranker import DashScopeReranker
from tests.eval.eval_test_set import EVAL_TEST_SET

logger = logging.getLogger(__name__)


# ============================================================================
# DashScope 同步 Embeddings 适配器（供 ragas 使用）
# ============================================================================
# DashScope 的 OpenAI「兼容」接口对 embeddings 并不完全兼容：
# OpenAI SDK 发送 {"input": "text"}，DashScope 期望 {"input": {"texts": [...]}}。
# 因此绕过 OpenAI SDK，用 httpx 同步调用 DashScope 原生 API。
# 实现 LangChain Embeddings 协议（embed_documents / embed_query），
# 再通过 LangchainEmbeddingsWrapper 桥接到 ragas。


class _DashScopeSyncEmbeddings:
    """DashScope text-embedding-v3 的同步 LangChain Embeddings 适配器。

    仅在 eval_ragas 中使用，不放入 app/ 以避免过度设计。
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, text_type="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], text_type="query")[0]

    def _embed(self, texts: list[str], text_type: str) -> list[list[float]]:
        import httpx

        url = f"{self._base_url}/services/embeddings/text-embedding/text-embedding"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": {"texts": texts},
            "parameters": {"text_type": text_type},
        }
        with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["output"]["embeddings"]]


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class RagasQuestionResult:
    """单题 ragas 评估结果"""
    question_id: int
    question: str
    difficulty: str
    question_type: str
    answer: str
    contexts: list[str]               # 检索到的 chunk 原文（rerank 后）
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None          # ragas 原生 ContextPrecision（LLM-based，需 reference）
    context_precision_doc: float | None = None      # 文档级 CP（自定义算法，诊断列）
    context_recall: float | None = None
    error: str | None = None           # 非 None 表示该题评估失败
    ar_flagged: bool = False           # AR=0.0 复核标记（疑似 judge 误判 noncommittal）


@dataclass
class RagasEvalSummary:
    """汇总评估结果"""
    total: int = 0
    evaluated: int = 0             # 成功评估的题目数
    failed: int = 0                # 评估失败的题目数
    faithfulness_mean: float | None = None
    answer_relevancy_mean: float | None = None
    answer_relevancy_adjusted_mean: float | None = None  # 排除 AR=0.0 复核题后的均值
    ar_zero_count: int = 0                                # AR=0.0 题数（含误判与真低分）
    context_precision_mean: float | None = None           # ragas 原生 ContextPrecision（LLM-based）
    context_precision_doc_mean: float | None = None       # 文档级 CP（自定义算法，诊断列）
    context_recall_mean: float | None = None
    per_question: list[RagasQuestionResult] = field(default_factory=list)


# ============================================================================
# 目标阈值
# ============================================================================

# 阈值经 2026-06-23 Ragas 全量评估（28 题）校准
TARGETS: dict[str, tuple[float, str]] = {
    "faithfulness": (0.80, "≥ 0.80"),
    "answer_relevancy": (0.80, "≥ 0.80"),
    "context_precision": (0.80, "≥ 0.80"),          # ragas 原生（LLM-based）
    "context_precision_doc": (0.60, "≥ 0.60"),      # 文档级 CP（自定义，诊断参考值；首轮均值 0.60）
    "context_recall": (0.80, "≥ 0.80"),
}

# 默认启用的指标
DEFAULT_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


# ============================================================================
# 上下文精度/召回率自定义计算（基于 expected_docs）
# ============================================================================

def compute_context_precision_doc(
    retrieved_results: list,
    expected_doc_ids: set[int],
    k: int = 10,
) -> float:
    """计算文档级上下文精度：top-K 检索结果中来自期望文档的 chunk 占比。

    基于 expected_docs 作为文档级 ground truth（辅助诊断指标）。
    若 top-K 中至少有一个 chunk 来自期望文档则认为该位置相关。

    Args:
        retrieved_results: 检索结果列表（RetrievalResult）
        expected_doc_ids: 期望文档的 doc_id 集合
        k: 评估的 top-K

    Returns:
        float: 0-1 之间的精度值
    """
    if not retrieved_results or not expected_doc_ids:
        return 0.0

    top_k = retrieved_results[:k]
    relevant_at_k = sum(1 for r in top_k if r.doc_id in expected_doc_ids)
    return relevant_at_k / min(k, len(top_k))


def compute_context_recall(
    retrieved_results: list,
    expected_doc_ids: set[int],
) -> float:
    """计算上下文召回率：期望文档中有多少被检索到。

    使用 expected_docs 作为文档级 ground truth。

    Args:
        retrieved_results: 检索结果列表（RetrievalResult）
        expected_doc_ids: 期望文档的 doc_id 集合

    Returns:
        float: 0-1 之间的召回率值
    """
    if not expected_doc_ids:
        return 0.0

    retrieved_doc_ids = {r.doc_id for r in retrieved_results}
    recalled = len(retrieved_doc_ids & expected_doc_ids)
    return recalled / len(expected_doc_ids)


# ============================================================================
# Answer Relevancy 中文反推问题 Prompt
# ============================================================================
# ragas 0.2.x 的 AnswerRelevancy 算法：
#   1. 让 LLM 从「答案」反推出能被该答案回答的「问题」（strictness 个，默认 3）
#   2. 反推问题与原问题做 embedding 余弦相似度，取均值
#   3. score = cosine_sim.mean() * int(not committal)
#      —— 只要 3 次反推中任意一次把答案判为 noncommittal（含糊回避），
#         整题分数直接归零（int(not committal)=0）
#
# 默认英文 prompt 在中文答案上存在两个问题：
#   - flash 判定模型在中文 hard 题上容易把合理答案误判为 noncommittal → 整题 0 分
#   - 英文 prompt 对中文答案的反推问题质量差，相似度均值偏低
# 故覆盖为中文 prompt，并配合 pro 判定模型（见 _init_ragas）。

def _build_answer_relevancy_cn_prompt():
    """构造 Answer Relevancy 的中文反推问题 prompt（懒加载 ragas）。

    正确语义：根据「答案」生成一个该答案能直接回答的「问题」，
    而非根据原问题生成子问题（旧死代码常量的错误所在）。
    """
    from ragas.metrics._answer_relevance import (
        ResponseRelevanceInput,
        ResponseRelevanceOutput,
        ResponseRelevancePrompt,
    )

    class _ResponseRelevancePromptCN(ResponseRelevancePrompt):
        instruction = (
            "请根据给定的答案，生成一个该答案能够直接回答的问题，"
            "并判断该答案是否属于含糊回避（noncommittal）。\n"
            "含糊回避指答案含糊、模糊、回避或未正面作答，"
            '例如「我不确定」「文档未提及」「无法回答」属于含糊回避，给出 noncommittal=1；\n'
            "答案明确回答了某个问题（即使简短或部分信息缺失）则给出 noncommittal=0。\n"
            "注意：不要因为答案不够详细或不够完整就判为含糊回避；"
            "只要答案对某个问题给出了明确内容，就不是含糊回避。\n"
            "输出 JSON，包含 question（反推的问题）与 noncommittal（0 或 1）两个字段。"
        )
        examples = [
            (
                ResponseRelevanceInput(response="爱因斯坦出生于德国。"),
                ResponseRelevanceOutput(
                    question="爱因斯坦出生在哪里？", noncommittal=0,
                ),
            ),
            (
                ResponseRelevanceInput(
                    response="我不了解 2023 年发明的智能手机的突破性功能，"
                    "因为我没有 2022 年之后的信息。"
                ),
                ResponseRelevanceOutput(
                    question="2023 年发明的智能手机有什么突破性功能？",
                    noncommittal=1,
                ),
            ),
        ]

    return _ResponseRelevancePromptCN()


# ============================================================================
# Context Precision 中文验证 Prompt（ragas 原生 LLM-based）
# ============================================================================
# ragas 0.2.x 的 ContextPrecision 算法：
#   1. 对每个检索到的 context，用 LLM 判断该 context 是否对生成
#      reference（参考答案）有用
#   2. verdict=1 表示有用，verdict=0 表示无用
#   3. 对 verdict 列表计算 Average Precision 得分
#   4. score = Σ(precision@k * relevance@k) / total_relevant
#
# 默认英文 prompt 对中文 context+reference 可能误判，
# 故覆盖为中文 prompt（与 AnswerRelevancy 中文 prompt 同理）。

def _build_context_precision_cn_prompt():
    """构造 Context Precision 的中文验证 prompt（懒加载 ragas）。"""
    from ragas.metrics._context_precision import (
        ContextPrecisionPrompt,
        QAC,
        Verification,
    )

    class _ContextPrecisionPromptCN(ContextPrecisionPrompt):
        instruction = (
            "请根据给定的问题、上下文和参考答案，判断该上下文是否对得出参考答案有用。\n"
            "有用：上下文中包含与参考答案相关的关键事实、数据或信息。\n"
            "无用：上下文与参考答案无关，或不能为得出答案提供帮助。\n"
            "输出 JSON，包含 reason（判断理由，一句话）与 verdict（1 表示有用，0 表示无用）两个字段。"
        )
        examples = [
            (
                QAC(
                    question="新员工入职第一天需要完成哪些手续？",
                    context="上午9:00前往人力资源部报到，提交入职材料，签署劳动合同及相关协议。"
                            "领取工牌、办公电脑和基础办公用品。信息技术部开通企业邮箱、OA账号。"
                            "参加新员工入职培训。",
                    answer="上午9:00前往人力资源部报到，提交入职材料（身份证复印件、学历学位证书、"
                          "离职证明、照片、银行卡、体检报告等），签署劳动合同及相关协议；"
                          "领取工牌、办公电脑和基础办公用品；信息技术部开通企业邮箱、"
                          "OA账号、即时通讯账号及业务系统权限；参加新员工入职培训。",
                ),
                Verification(
                    reason="上下文包含了入职报到的关键步骤，与参考答案高度相关",
                    verdict=1,
                ),
            ),
            (
                QAC(
                    question="新员工入职第一天需要完成哪些手续？",
                    context="公司为各部门配置了多功能复合打印机，支持黑白/彩色打印、复印、扫描功能。"
                            "设备分布于各楼层文印区及部门办公区。",
                    answer="上午9:00前往人力资源部报到，提交入职材料（身份证复印件、学历学位证书、"
                          "离职证明、照片、银行卡、体检报告等），签署劳动合同及相关协议；"
                          "领取工牌、办公电脑和基础办公用品；信息技术部开通企业邮箱、"
                          "OA账号、即时通讯账号及业务系统权限；参加新员工入职培训。",
                ),
                Verification(
                    reason="上下文是关于打印机的使用说明，与入职手续完全无关",
                    verdict=0,
                ),
            ),
        ]

    return _ContextPrecisionPromptCN()


# ============================================================================
# Ragas 评估器
# ============================================================================

class RagasEvaluator:
    """Ragas 端到端评估器

    1. 对每题运行知识管线获取检索上下文
    2. 调用 LLM 生成答案
    3. 使用 ragas 计算 Faithfulness / Answer Relevancy（LLM-based）
    4. 使用自定义算法计算 Context Precision / Context Recall（文档级 ground truth）
    5. 输出结构化报告
    """

    def __init__(
        self,
        kb_id: int,
        llm_model: str = "flash",
        top_k: int = 10,
        metrics: list[str] | None = None,
    ):
        self.kb_id = kb_id
        self.top_k = top_k
        self.metrics = metrics or DEFAULT_METRICS

        # 答案生成模型
        self._answer_model = (
            settings.LLM_MODEL if llm_model == "pro" else settings.LLM_FLASH_MODEL
        )

        # 管线组件（懒加载）
        self._vector_retriever: VectorRetriever | None = None
        self._bm25_factory_used: bool = False
        self._bm25_retriever: BM25Retriever | None = None
        self._pipeline: KnowledgePipeline | None = None

        # 文档映射
        self._filename_to_doc_id: dict[str, int] = {}
        self._doc_id_to_filename: dict[int, str] = {}

        # ragas 评估 LLM（懒加载）
        self._ragas_llm: Any = None
        self._ragas_metrics: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 懒加载辅助
    # ------------------------------------------------------------------

    @property
    def vector_retriever(self) -> VectorRetriever:
        if self._vector_retriever is None:
            self._vector_retriever = VectorRetriever(get_vector_store())
        return self._vector_retriever

    async def _ensure_bm25(self) -> BM25Retriever:
        if self._bm25_retriever is None:
            async_redis = await get_async_redis()
            self._bm25_retriever = BM25Retriever(
                async_redis=async_redis,
                session_factory=async_session,
            )
        return self._bm25_retriever

    async def _ensure_pipeline(self) -> KnowledgePipeline:
        if self._pipeline is None:
            bm25 = await self._ensure_bm25()

            async def _bm25_factory():
                return bm25

            self._pipeline = KnowledgePipeline(
                vector_retriever=self.vector_retriever,
                bm25_retriever_factory=_bm25_factory,
                reranker=DashScopeReranker(),
            )
        return self._pipeline

    # ------------------------------------------------------------------
    # 文档映射
    # ------------------------------------------------------------------

    async def load_doc_map(self) -> None:
        """从 MySQL 加载 kb_id 下所有文档的 filename ↔ doc_id 双向映射"""
        async with async_session() as db:
            result = await db.execute(
                select(Document.id, Document.filename)
                .where(Document.kb_id == self.kb_id)
            )
            rows = result.all()

        self._filename_to_doc_id = {row.filename: row.id for row in rows}
        self._doc_id_to_filename = {row.id: row.filename for row in rows}
        logger.info(
            "文档映射已加载: kb_id=%d, %d 个文档",
            self.kb_id, len(self._filename_to_doc_id),
        )

    def _resolve_expected_doc_ids(self, expected_docs: list[str]) -> set[int]:
        """将期望文档文件名列表解析为 doc_id 集合"""
        doc_ids: set[int] = set()
        for filename in expected_docs:
            doc_id = self._filename_to_doc_id.get(filename)
            if doc_id is not None:
                doc_ids.add(doc_id)
            else:
                logger.warning("期望文档未在知识库中找到: %s", filename)
        return doc_ids

    # ------------------------------------------------------------------
    # 核心评估流程
    # ------------------------------------------------------------------

    async def capture_answer_and_contexts(
        self, question: str
    ) -> tuple[str, list[str], RetrievalOutput]:
        """运行知识管线 + LLM，获取答案和检索上下文。

        Args:
            question: 用户问题

        Returns:
            (answer, contexts, reranked_output) 元组
        """
        pipeline = await self._ensure_pipeline()

        async with async_session() as db:
            result: KnowledgePipelineResult = await pipeline.execute_knowledge(
                db=db,
                question=question,
                kb_id=self.kb_id,
                history_messages=[],  # 单轮评估，无历史
                recorder=None,
            )

        # 提取检索上下文（rerank 后的 chunk 原文）
        reranked = result.reranked_output
        contexts = [r.content for r in reranked.results]

        # 构建 LLM 消息
        prompt = result.prompt_result
        if not prompt.system_prompt and not prompt.user_prompt:
            # REJECT 路径：无陈述性证据，跳过 LLM 调用
            return ("", contexts, reranked)

        messages: list[dict[str, str]] = []
        if prompt.system_prompt:
            messages.append({"role": "system", "content": prompt.system_prompt})
        messages.append({"role": "user", "content": prompt.user_prompt})

        # 调用 LLM 生成答案（非流式）
        try:
            llm_result: LLMResult = await chat_completion(
                messages=messages,
                deep_thinking=False,
                model=self._answer_model,
            )
            answer = llm_result.content
        except Exception:
            logger.exception("LLM 答案生成失败: question=%s", question[:50])
            answer = ""

        return answer, contexts, reranked

    async def _init_ragas(self) -> None:
        """懒加载 ragas 指标和评估 LLM + Embeddings。

        将 ragas 导入延迟到此处，避免未安装 ragas 时 import 即崩溃。
        """
        if self._ragas_metrics:
            return

        try:
            from ragas.llms import LangchainLLMWrapper
            from ragas.embeddings import LangchainEmbeddingsWrapper
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError(
                "ragas 未安装，请运行: pip install ragas==0.2.* datasets>=3.0"
            ) from e

        # 评估用 LLM（judge）——统一使用 pro 模型。
        # Answer Relevancy 对 judge 最苛刻：需严格输出结构化反推问题，
        # flash 在中文 hard 题上易把合理答案误判为 noncommittal 导致整题归零。
        # Faithfulness 同样受益于更强的判定模型。
        base_llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            temperature=0,
            request_timeout=120,  # 单次 HTTP 请求超时（秒），避免底层 httpx 无限等待
        )
        self._ragas_llm = LangchainLLMWrapper(base_llm)

        # 评估用 Embeddings（DashScope text-embedding-v3，通过 httpx 同步调用原生 API）
        # 不能使用 OpenAIEmbeddings：DashScope 兼容接口的 embeddings 入参格式不兼容
        base_embeddings = _DashScopeSyncEmbeddings(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
        self._ragas_embeddings = LangchainEmbeddingsWrapper(base_embeddings)

        # 按需初始化指标
        if "faithfulness" in self.metrics:
            from ragas.metrics import Faithfulness
            self._ragas_metrics["faithfulness"] = Faithfulness(llm=self._ragas_llm)

        if "answer_relevancy" in self.metrics:
            from ragas.metrics import AnswerRelevancy
            self._ragas_metrics["answer_relevancy"] = AnswerRelevancy(
                llm=self._ragas_llm,
                embeddings=self._ragas_embeddings,
                # 注入中文反推问题 prompt（覆盖默认英文 prompt）
                question_generation=_build_answer_relevancy_cn_prompt(),
            )

        if "context_precision" in self.metrics:
            from ragas.metrics import ContextPrecision
            self._ragas_metrics["context_precision"] = ContextPrecision(
                llm=self._ragas_llm,
                # 注入中文验证 prompt（覆盖默认英文 prompt）
                context_precision_prompt=_build_context_precision_cn_prompt(),
            )

    async def _score_ragas_metrics(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        reference: str = "",
    ) -> dict[str, float | None]:
        """使用 ragas 对单题进行 LLM-based 指标评分。

        Args:
            question: 用户问题
            answer: 生成的答案
            contexts: 检索到的上下文
            reference: 参考答案（用于 ContextPrecision，可选）

        Returns:
            dict: {"faithfulness": 0.85, "answer_relevancy": 0.72,
                   "context_precision": 0.80, ...}
        """
        await self._init_ragas()

        scores: dict[str, float | None] = {}

        # 无答案或无语境时跳过 LLM 评估
        if not answer or not contexts:
            for metric_name in self.metrics:
                if metric_name in ("faithfulness", "answer_relevancy", "context_precision"):
                    scores[metric_name] = None
            return scores

        from ragas.dataset_schema import SingleTurnSample

        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
        )

        for metric_name in ("faithfulness", "answer_relevancy"):
            if metric_name not in self.metrics:
                continue
            metric = self._ragas_metrics.get(metric_name)
            if metric is None:
                scores[metric_name] = None
                continue
            try:
                score_val = await metric.single_turn_ascore(sample, timeout=300)
                scores[metric_name] = float(score_val)
            except Exception:
                logger.exception(
                    "ragas %s 评分失败: question_id（见上下文）", metric_name
                )
                scores[metric_name] = None

        # ContextPrecision（ragas 原生 LLM-based）— 需要 reference
        if "context_precision" in self.metrics:
            cp_metric = self._ragas_metrics.get("context_precision")
            if cp_metric is not None and reference:
                try:
                    cp_sample = SingleTurnSample(
                        user_input=question,
                        retrieved_contexts=contexts,
                        reference=reference,
                    )
                    cp_val = await cp_metric.single_turn_ascore(cp_sample, timeout=300)
                    scores["context_precision"] = float(cp_val)
                except Exception:
                    logger.exception(
                        "ragas context_precision 评分失败"
                    )
                    scores["context_precision"] = None
            else:
                scores["context_precision"] = None

        return scores

    async def evaluate_all(self) -> RagasEvalSummary:
        """对全部题目（排除 out-of-scope）运行 ragas 评估。

        Returns:
            RagasEvalSummary: 汇总评估结果
        """
        await self.load_doc_map()

        # 筛选题目：排除 out-of-scope
        scoped_items = [
            item for item in EVAL_TEST_SET
            if item.get("difficulty") != "out-of-scope"
        ]

        summary = RagasEvalSummary(total=len(scoped_items))
        results: list[RagasQuestionResult] = []

        print(f"\n{'='*70}")
        print(f"  Ragas 端到端评估 — kb_id={self.kb_id}, top_k={self.top_k}")
        print(f"  评估集: {len(scoped_items)} 题（已排除 {len(EVAL_TEST_SET) - len(scoped_items)} 题 out-of-scope）")
        print(f"  答案生成模型: {self._answer_model}")
        print(f"  启用指标: {', '.join(self.metrics)}")
        print(f"{'='*70}\n")

        for idx, item in enumerate(scoped_items):
            qid = item["id"]
            question = item["question"]
            difficulty = item.get("difficulty", "")
            qtype = item.get("type", "")
            expected_docs: list[str] = item.get("expected_docs", [])
            reference: str = item.get("reference", "")

            print(f"[{idx + 1}/{len(scoped_items)}] 评估 Q{qid} ({difficulty}): {question[:60]}...")

            try:
                # 1. 运行管线获取答案和上下文
                answer, contexts, reranked_output = await self.capture_answer_and_contexts(
                    question
                )

                # 2. ragas LLM-based 指标（含原生 ContextPrecision，需 reference）
                ragas_scores = await self._score_ragas_metrics(
                    question, answer, contexts, reference=reference,
                )

                # 3. 文档级上下文指标（自定义，基于 expected_docs，诊断列）
                expected_doc_ids = self._resolve_expected_doc_ids(expected_docs)
                cp_doc = None
                cr = None
                if "context_precision" in self.metrics:
                    cp_doc = compute_context_precision_doc(
                        reranked_output.results, expected_doc_ids, k=self.top_k
                    )
                if "context_recall" in self.metrics:
                    cr = compute_context_recall(
                        reranked_output.results, expected_doc_ids
                    )

                result = RagasQuestionResult(
                    question_id=qid,
                    question=question,
                    difficulty=difficulty,
                    question_type=qtype,
                    answer=answer,
                    contexts=contexts,
                    faithfulness=ragas_scores.get("faithfulness"),
                    answer_relevancy=ragas_scores.get("answer_relevancy"),
                    context_precision=ragas_scores.get("context_precision"),
                    context_precision_doc=cp_doc,
                    context_recall=cr,
                    ar_flagged=(
                        ragas_scores.get("answer_relevancy") is not None
                        and ragas_scores.get("answer_relevancy") == 0.0
                    ),
                )
                results.append(result)

                # 简要反馈
                parts: list[str] = []
                if ragas_scores.get("faithfulness") is not None:
                    parts.append(f"F={ragas_scores['faithfulness']:.2f}")
                if ragas_scores.get("answer_relevancy") is not None:
                    parts.append(f"AR={ragas_scores['answer_relevancy']:.2f}")
                cp_native = ragas_scores.get("context_precision")
                if cp_native is not None:
                    parts.append(f"CP={cp_native:.2f}")
                if cp_doc is not None:
                    parts.append(f"CPdoc={cp_doc:.2f}")
                if cr is not None:
                    parts.append(f"CR={cr:.2f}")
                status = "  ".join(parts) if parts else "⚠ 无评分"
                print(f"       {status}")

            except Exception:
                logger.exception("Q%d 评估异常", qid)
                results.append(RagasQuestionResult(
                    question_id=qid,
                    question=question,
                    difficulty=difficulty,
                    question_type=qtype,
                    answer="",
                    contexts=[],
                    error="评估异常",
                ))
                print(f"       ❌ 评估异常")

        # 汇总统计
        faithful_vals = [r.faithfulness for r in results if r.faithfulness is not None]
        relevancy_vals = [r.answer_relevancy for r in results if r.answer_relevancy is not None]
        # AR=0.0 在 ragas 中往往来自 judge 误判 noncommittal（整题归零），
        # 与真实低分无法在数值上区分。标记后单独计算「排除 0 分复核题」的调整均值，
        # 便于诊断 judge 是否仍存在系统性误判；原始均值仍如实保留。
        relevancy_adjusted_vals = [
            r.answer_relevancy for r in results
            if r.answer_relevancy is not None and r.answer_relevancy > 0.0
        ]
        ar_zero_count = sum(
            1 for r in results if r.answer_relevancy is not None and r.answer_relevancy == 0.0
        )
        cp_vals = [r.context_precision for r in results if r.context_precision is not None]
        cp_doc_vals = [r.context_precision_doc for r in results if r.context_precision_doc is not None]
        cr_vals = [r.context_recall for r in results if r.context_recall is not None]
        failed_count = sum(1 for r in results if r.error is not None)

        summary.evaluated = len(results) - failed_count
        summary.failed = failed_count
        summary.faithfulness_mean = mean(faithful_vals) if faithful_vals else None
        summary.answer_relevancy_mean = mean(relevancy_vals) if relevancy_vals else None
        summary.answer_relevancy_adjusted_mean = (
            mean(relevancy_adjusted_vals) if relevancy_adjusted_vals else None
        )
        summary.ar_zero_count = ar_zero_count
        summary.context_precision_mean = mean(cp_vals) if cp_vals else None
        summary.context_precision_doc_mean = mean(cp_doc_vals) if cp_doc_vals else None
        summary.context_recall_mean = mean(cr_vals) if cr_vals else None
        summary.per_question = results

        return summary


# ============================================================================
# 报告输出
# ============================================================================

def _pass_fail(value: float | None, target: float) -> str:
    if value is None:
        return "—"
    return "✅" if value >= target else "❌"


def print_summary_table(summary: RagasEvalSummary) -> None:
    """打印 ragas 评估汇总表"""
    print(f"\n{'='*70}")
    print("  Ragas 评估结果汇总")
    print(f"{'='*70}\n")

    header = f"{'指标':<22} {'目标':<10} {'平均值':<10} {'结果'}"
    print(header)
    print("-" * 50)

    metric_rows = [
        ("faithfulness_mean", "Faithfulness（忠实度）"),
        ("answer_relevancy_mean", "Answer Relevancy（相关性）"),
        ("context_precision_mean", "Context Precision（上下文精度，ragas 原生）"),
        ("context_precision_doc_mean", "Context Precision Doc（文档级，诊断列）"),
        ("context_recall_mean", "Context Recall（上下文召回率）"),
    ]

    for attr, label in metric_rows:
        key = attr.replace("_mean", "")
        if key not in TARGETS:
            continue
        target_val, target_str = TARGETS[key]
        value = getattr(summary, attr)
        row = (
            f"{label:<22} {target_str:<10} "
            f"{f'{value:.4f}' if value is not None else '—':<10} "
            f"{_pass_fail(value, target_val)}"
        )
        print(row)

    # Answer Relevancy 诊断行：排除 0 分复核题后的调整均值 + 0 分题数
    # 说明 judge 在 noncommittal 上是否存在系统性误判
    if summary.answer_relevancy_adjusted_mean is not None:
        print(
            f"  ├ Answer Relevancy 排除 0 分复核题: "
            f"{summary.answer_relevancy_adjusted_mean:.4f} "
            f"（0 分题: {summary.ar_zero_count}/{summary.evaluated}）"
        )

    print("-" * 50)
    print(f"  评估题目: {summary.total} 题 | 成功: {summary.evaluated} | 失败: {summary.failed}")
    print(f"  ✅ = 达标    ❌ = 未达标    — = 无数据    ⚑ = AR 0 分待复核")
    print()


def print_per_question_table(summary: RagasEvalSummary) -> None:
    """打印逐题明细表"""
    print(f"\n{'='*70}")
    print("  逐题 Ragas 评分明细")
    print(f"{'='*70}\n")

    header = (
        f"{'ID':<4} {'难度':<10} {'Faithfulness':<14} "
        f"{'AnswerRel':<12} {'CP(ragas)':<10} {'CPdoc':<8} {'CR':<8}"
    )
    print(header)
    print("-" * 78)

    for r in summary.per_question:
        f_str = f"{r.faithfulness:.4f}" if r.faithfulness is not None else "—"
        ar_str = f"{r.answer_relevancy:.4f}" if r.answer_relevancy is not None else "—"
        cp_str = f"{r.context_precision:.4f}" if r.context_precision is not None else "—"
        cp_doc_str = f"{r.context_precision_doc:.4f}" if r.context_precision_doc is not None else "—"
        cr_str = f"{r.context_recall:.4f}" if r.context_recall is not None else "—"

        row = (
            f"Q{r.question_id:<3} {r.difficulty:<10} "
            f"{f_str:<14} {ar_str:<12} {cp_str:<10} {cp_doc_str:<8} {cr_str:<8}"
        )
        if r.ar_flagged:
            row += "  ⚑ AR 0 分待复核"
        if r.error:
            row += f"  ⚠ {r.error}"
        print(row)

    print()


def export_json(summary: RagasEvalSummary, output_path: str) -> None:
    """导出 JSON 格式评估报告"""
    report: dict[str, Any] = {
        "kb_id": None,  # 由调用方填充
        "eval_model": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": summary.total,
            "evaluated": summary.evaluated,
            "failed": summary.failed,
            "faithfulness_mean": summary.faithfulness_mean,
            "answer_relevancy_mean": summary.answer_relevancy_mean,
            "answer_relevancy_adjusted_mean": summary.answer_relevancy_adjusted_mean,
            "ar_zero_count": summary.ar_zero_count,
            "context_precision_mean": summary.context_precision_mean,
            "context_precision_doc_mean": summary.context_precision_doc_mean,
            "context_recall_mean": summary.context_recall_mean,
        },
        "per_question": [
            {
                "question_id": r.question_id,
                "question": r.question,
                "difficulty": r.difficulty,
                "type": r.question_type,
                "answer": r.answer,
                "contexts_count": len(r.contexts),
                "faithfulness": r.faithfulness,
                "answer_relevancy": r.answer_relevancy,
                "ar_flagged": r.ar_flagged,
                "context_precision": r.context_precision,
                "context_precision_doc": r.context_precision_doc,
                "context_recall": r.context_recall,
                "error": r.error,
            }
            for r in summary.per_question
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"📄 JSON 报告已导出: {output_path}")


def export_markdown(summary: RagasEvalSummary, output_path: str) -> None:
    """导出 Markdown 格式评估报告"""
    lines: list[str] = []
    lines.append("# Ragas 端到端评估报告\n")
    lines.append(f"**生成时间**：{datetime.now(timezone.utc).isoformat()}\n")
    lines.append(f"**评估题目数**：{summary.total} | **成功**：{summary.evaluated} | **失败**：{summary.failed}\n")

    # 汇总表
    lines.append("## 指标汇总\n")
    lines.append("| 指标 | 目标 | 平均值 | 结果 |")
    lines.append("|:---|---:|---:|:---:|")

    metric_rows = [
        ("faithfulness_mean", "Faithfulness（忠实度）", "faithfulness"),
        ("answer_relevancy_mean", "Answer Relevancy（相关性）", "answer_relevancy"),
        ("context_precision_mean", "Context Precision（ragas 原生）", "context_precision"),
        ("context_precision_doc_mean", "Context Precision Doc（文档级）", "context_precision_doc"),
        ("context_recall_mean", "Context Recall（上下文召回率）", "context_recall"),
    ]
    for attr, label, key in metric_rows:
        if key not in TARGETS:
            continue
        target_val, target_str = TARGETS[key]
        value = getattr(summary, attr)
        val_str = f"{value:.4f}" if value is not None else "—"
        result_str = _pass_fail(value, target_val)
        lines.append(f"| {label} | {target_str} | {val_str} | {result_str} |")

    # Answer Relevancy 诊断行
    if summary.answer_relevancy_adjusted_mean is not None:
        lines.append(
            f"| Answer Relevancy（排除 0 分复核题） | — | "
            f"{summary.answer_relevancy_adjusted_mean:.4f} | "
            f"0 分题 {summary.ar_zero_count}/{summary.evaluated} |"
        )

    lines.append("")

    # 逐题明细
    lines.append("## 逐题明细\n")
    lines.append("| ID | 难度 | Faithfulness | AnswerRelevancy | CP(ragas) | CPdoc | CtxRecall |")
    lines.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|")

    for r in summary.per_question:
        f_str = f"{r.faithfulness:.4f}" if r.faithfulness is not None else "—"
        ar_str = f"{r.answer_relevancy:.4f}" if r.answer_relevancy is not None else "—"
        cp_str = f"{r.context_precision:.4f}" if r.context_precision is not None else "—"
        cp_doc_str = f"{r.context_precision_doc:.4f}" if r.context_precision_doc is not None else "—"
        cr_str = f"{r.context_recall:.4f}" if r.context_recall is not None else "—"
        flag_note = " ⚑AR 0 分待复核" if r.ar_flagged else ""
        error_note = f" ⚠{r.error}" if r.error else ""
        lines.append(
            f"| Q{r.question_id} | {r.difficulty} "
            f"| {f_str} | {ar_str} | {cp_str} | {cp_doc_str} | {cr_str} |{flag_note}{error_note}"
        )

    lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"📄 Markdown 报告已导出: {output_path}")


# ============================================================================
# CLI 入口
# ============================================================================

async def resolve_kb_id(raw: str) -> int:
    """将用户输入的 kb_id（整数或 UUID）解析为内部整数 ID。

    Args:
        raw: 用户输入的 kb_id，可以是整数（如 "1"）或 UUID（如 "da63f069-..."）

    Returns:
        int: 内部知识库整数 ID

    Raises:
        SystemExit: 知识库不存在时退出
    """
    # 尝试解析为整数
    try:
        return int(raw)
    except ValueError:
        pass

    # 按 UUID 查询
    async with async_session() as db:
        result = await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.uuid == raw)
        )
        row = result.one_or_none()

    if row is None:
        print(f"❌ 未找到知识库: uuid={raw}", file=sys.stderr)
        sys.exit(1)

    resolved_id = row[0]
    logger.info("UUID → 内部 ID: %s → %d", raw, resolved_id)
    return resolved_id


async def main_async(
    kb_id: int,
    top_k: int,
    model: str,
    metrics: list[str],
    output_formats: list[str],
    output_dir: str,
) -> None:
    """异步主流程"""
    evaluator = RagasEvaluator(
        kb_id=kb_id,
        llm_model=model,
        top_k=top_k,
        metrics=metrics,
    )
    summary = await evaluator.evaluate_all()

    # 控制台输出
    print_summary_table(summary)
    print_per_question_table(summary)

    # 文件输出
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    for fmt in output_formats:
        if fmt == "json":
            path = str(Path(output_dir) / f"ragas_eval_{timestamp}.json")
            export_json(summary, path)
        elif fmt == "md":
            path = str(Path(output_dir) / f"ragas_eval_{timestamp}.md")
            export_markdown(summary, path)

    # 达标判断
    checks: list[bool] = []
    if summary.faithfulness_mean is not None:
        checks.append(summary.faithfulness_mean >= TARGETS["faithfulness"][0])
    if summary.answer_relevancy_mean is not None:
        checks.append(summary.answer_relevancy_mean >= TARGETS["answer_relevancy"][0])
    if summary.context_precision_mean is not None:
        checks.append(summary.context_precision_mean >= TARGETS["context_precision"][0])
    if summary.context_precision_doc_mean is not None:
        checks.append(summary.context_precision_doc_mean >= TARGETS["context_precision_doc"][0])
    if summary.context_recall_mean is not None:
        checks.append(summary.context_recall_mean >= TARGETS["context_recall"][0])

    if checks and all(checks):
        print("🎉 全部指标达标！\n")
    elif checks:
        print("⚠️  部分指标未达标，详见上方标记 ❌ 的项目。\n")
    else:
        print("⚠️  无可用指标数据。\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DocMind Ragas 端到端评估 — 生成质量自动化评分",
    )
    parser.add_argument(
        "--kb-id", type=str, required=True,
        help="目标知识库 ID（支持内部整数 ID 或 UUID）",
    )
    parser.add_argument(
        "--top-k", type=int, default=10,
        help="检索返回数量（默认 10）",
    )
    parser.add_argument(
        "--model", type=str, default="flash", choices=["flash", "pro"],
        help="答案生成模型：flash（默认，deepseek-v4-flash）或 pro（deepseek-v4-pro）",
    )
    parser.add_argument(
        "--metrics", type=str, default=None,
        help="启用的评估指标，逗号分隔（默认全部启用）。可选: faithfulness,answer_relevancy,context_precision,context_recall",
    )
    parser.add_argument(
        "--output", type=str, nargs="*", default=[],
        choices=["json", "md"],
        help="输出格式：json 和/或 md",
    )
    parser.add_argument(
        "--output-dir", type=str, default=".",
        help="报告输出目录（默认当前目录）",
    )
    args = parser.parse_args()

    # 解析指标
    if args.metrics:
        metrics = [m.strip() for m in args.metrics.split(",")]
        # 验证指标名称
        valid = set(DEFAULT_METRICS)
        for m in metrics:
            if m not in valid:
                print(f"⚠ 未知指标: {m}，可选: {', '.join(valid)}")
                sys.exit(1)
    else:
        metrics = DEFAULT_METRICS

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 解析 kb_id：支持整数或 UUID
    kb_id = asyncio.run(resolve_kb_id(args.kb_id))

    asyncio.run(main_async(
        kb_id=kb_id,
        top_k=args.top_k,
        model=args.model,
        metrics=metrics,
        output_formats=args.output or [],
        output_dir=args.output_dir,
    ))


if __name__ == "__main__":
    main()
