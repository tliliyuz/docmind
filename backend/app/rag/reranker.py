"""Rerank 重排序模块 — DashScope Rerank API 语义精排

DashScope Rerank API 说明：
- 端点：POST {RERANK_BASE_URL}/services/rerank/text-rerank/text-rerank
- 模型：qwen3-rerank
- 输入：query（字符串）+ documents（字符串列表）
- 输出：results 列表（按 relevance_score 降序），含 index / relevance_score
- 重试：指数退避，默认 3 次
- API 异常时降级回退到原始 RRF 排序（不阻断检索管线）

设计要点：
- 调用 DashScope API，按语义相关性重新排序
- 输入不足 top_k 时返回全部
- 不改变 chunk 内容，仅调整顺序和数量
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.rag.retriever import RetrievalOutput, RetrievalResult

from app.config import settings

logger = logging.getLogger(__name__)


class BaseReranker(ABC):
    """Reranker 基类，定义重排序接口"""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        retrieval_output: RetrievalOutput,
        top_k: int = settings.RERANK_TOP_K,
    ) -> RetrievalOutput:
        """对检索结果进行重排序。

        Args:
            query: 用户问题
            retrieval_output: 检索结果
            top_k: 返回结果数量上限

        Returns:
            RetrievalOutput: 重排序后的结果
        """
        ...


class DashScopeReranker(BaseReranker):
    """DashScope Rerank API 精排实现

    调用 DashScope text-rerank API（qwen3-rerank），对 RRF 融合结果做语义精排。
    按 relevance_score 降序排列，截取 top_k。

    - 输入不足 top_k 时返回全部
    - 不改变 chunk 内容，仅调整顺序和数量
    - 空输入直接返回空结果
    - API 异常时降级回退到原始 RRF 排序（不阻断检索管线）
    """

    name: str = "dashscope"

    def __init__(self) -> None:
        self._base_url = settings.RERANK_BASE_URL.rstrip("/")
        self._model = settings.RERANK_MODEL
        self._api_key = settings.RERANK_API_KEY
        self._max_retries = settings.RERANK_MAX_RETRIES
        self._timeout = settings.RERANK_TIMEOUT

    @property
    def api_url(self) -> str:
        """DashScope Rerank API 完整端点"""
        return f"{self._base_url}/services/rerank/text-rerank/text-rerank"

    async def rerank(
        self,
        query: str,
        retrieval_output: RetrievalOutput,
        top_k: int = settings.RERANK_TOP_K,
    ) -> RetrievalOutput:
        """对检索结果进行语义重排序。

        Args:
            query: 用户问题
            retrieval_output: RRF 融合后的检索结果
            top_k: 返回结果数量上限，默认 5

        Returns:
            RetrievalOutput: 按 relevance_score 降序排列的精排结果
        """
        if not retrieval_output.results:
            logger.info("DashScopeReranker: 输入结果为空，直接返回")
            return RetrievalOutput()

        documents = [r.content for r in retrieval_output.results]
        input_count = len(documents)

        # 输入不足 top_k 时，调整 top_n 为实际数量
        effective_top_n = min(top_k, input_count)

        logger.info(
            "DashScopeReranker: 发起重排序请求 model=%s query_len=%d documents=%d top_n=%d",
            self._model, len(query), input_count, effective_top_n,
        )

        try:
            ranked_indices = await self._call_rerank_api(
                query=query,
                documents=documents,
                top_n=effective_top_n,
            )
        except Exception:
            logger.exception(
                "DashScope Rerank API 调用失败，降级回退到原始 RRF 排序"
            )
            # 降级：保持原始 RRF 排序，仅截取 top_k
            fallback_results = retrieval_output.results[:top_k]
            return RetrievalOutput(
                results=fallback_results,
                total=len(fallback_results),
            )

        # 按 API 返回的 relevance_score 降序重新排列
        reranked = [retrieval_output.results[i] for i in ranked_indices]

        logger.info(
            "DashScopeReranker: %d 条输入 → API 精排 → top_%d → %d 条输出",
            input_count, top_k, len(reranked),
        )

        return RetrievalOutput(
            results=reranked,
            total=len(reranked),
        )

    async def _call_rerank_api(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[int]:
        """调用 DashScope Rerank API，带指数退避重试。

        Args:
            query: 查询文本
            documents: 待重排文档文本列表
            top_n: 返回结果数量

        Returns:
            list[int]: 按 relevance_score 降序排列的原始索引列表

        Raises:
            RuntimeError: 重试耗尽后仍失败
        """
        url = self.api_url
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "top_n": top_n,
                "return_documents": False,
            },
        }

        last_error = None
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout)
                ) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        return self.parse_rerank_response(data, len(documents))

                    last_error = f"HTTP {response.status_code}: {_safe_truncate(response.text)}"
                    logger.warning(
                        "Rerank API 调用失败 (尝试 %d/%d): %s",
                        attempt + 1, self._max_retries, last_error,
                    )

            except (httpx.RequestError, httpx.TimeoutException, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(
                    "Rerank API 网络异常 (尝试 %d/%d): %s",
                    attempt + 1, self._max_retries, e,
                )

            if attempt < self._max_retries - 1:
                delay = 1 * (2 ** attempt)  # 1, 2, 4
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"DashScope Rerank API 调用失败，已重试 {self._max_retries} 次: {last_error}"
        )

    @staticmethod
    def parse_rerank_response(data: dict, doc_count: int) -> list[int]:
        """解析 DashScope Rerank API 响应，提取排序后的索引列表。

        Args:
            data: API 响应 JSON
            doc_count: 输入的文档数量（用于校验）

        Returns:
            list[int]: 按 relevance_score 降序排列的原始索引列表

        Raises:
            ValueError: 响应格式异常
        """
        output = data.get("output", {})
        results = output.get("results", [])

        if not results:
            logger.warning("Rerank API 返回空结果列表，降级返回全部原始索引")
            return list(range(doc_count))

        indices = []
        for item in results:
            idx = item.get("index")
            if idx is None:
                raise ValueError(
                    f"Rerank API 响应格式异常: 结果项缺少 index 字段: {item}"
                )
            if not isinstance(idx, int) or idx < 0 or idx >= doc_count:
                raise ValueError(
                    f"Rerank API 返回的索引越界: {idx} (文档数: {doc_count})"
                )
            indices.append(idx)

        usage = data.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        logger.info(
            "Rerank API 完成: %d 条输入 → %d 条输出, total_tokens=%d",
            doc_count, len(indices), total_tokens,
        )

        return indices


def _safe_truncate(text: str, max_len: int = 200) -> str:
    """截断文本用于日志，防止 API 响应过长撑爆日志"""
    return text[:max_len] if len(text) > max_len else text
