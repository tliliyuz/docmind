"""Embedding 向量化 — DashScope text-embedding-v3 调用

提供单批次 Embedding 接口，重试逻辑内置于 _call_embed_api。
调用方（tasks.py）自行分批并写入 checkpoint，保持对 checkpoint 时机的控制。
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.core.exceptions import EmbeddingTimeoutException, VectorStoreErrorException

logger = logging.getLogger(__name__)


@dataclass
class EmbedResult:
    """单批次 Embedding 结果"""
    embeddings: list[list[float]] = field(default_factory=list)
    token_counts: list[int] = field(default_factory=list)
    total_tokens: int = 0


def _build_embed_url() -> str:
    """构建 DashScope Embedding API 完整 URL"""
    base = settings.EMBEDDING_BASE_URL.rstrip("/")
    return f"{base}/services/embeddings/text-embedding/text-embedding"


def _build_payload(texts: list[str], text_type: str = "document") -> dict:
    """构建 DashScope Embedding API 请求体

    Args:
        texts: 待向量化的文本列表
        text_type: "document"（入库文档）或 "query"（检索查询），
                   DashScope 对两种类型使用不同的向量化策略
    """
    return {
        "model": settings.EMBEDDING_MODEL,
        "input": {"texts": texts},
        "parameters": {"text_type": text_type},
    }


async def _call_embed_api(texts: list[str], text_type: str = "document") -> EmbedResult:
    """单次调用 DashScope Embedding API，带指数退避重试"""
    url = _build_embed_url()
    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(texts, text_type)

    last_error = None
    for attempt in range(settings.EMBED_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(settings.EMBED_TIMEOUT)) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return _parse_embed_response(data, len(texts))

                last_error = f"HTTP {response.status_code}: {_safe_truncate(response.text)}"
                logger.warning(
                    "Embedding API 调用失败 (尝试 %d/%d): %s",
                    attempt + 1, settings.EMBED_MAX_RETRIES, last_error,
                )

        except (httpx.RequestError, httpx.TimeoutException, json.JSONDecodeError) as e:
            last_error = str(e)
            logger.warning(
                "Embedding API 网络异常 (尝试 %d/%d): %s",
                attempt + 1, settings.EMBED_MAX_RETRIES, e,
            )

        if attempt < settings.EMBED_MAX_RETRIES - 1:
            delay = settings.EMBED_BASE_DELAY * (2 ** attempt)  # 1, 2, 4, 8, 16
            await asyncio.sleep(delay)

    raise EmbeddingTimeoutException(
        f"Embedding API 调用失败，已重试 {settings.EMBED_MAX_RETRIES} 次: {last_error}"
    )


def _parse_embed_response(data: dict, text_count: int) -> EmbedResult:
    """解析 DashScope Embedding API 响应，按比例分配 token 计数"""
    output = data.get("output", {})
    embeddings_raw = output.get("embeddings", [])
    usage = data.get("usage", {})

    embeddings = []
    for item in embeddings_raw:
        if "embedding" not in item:
            raise VectorStoreErrorException(
                f"DashScope API 返回格式异常: 第 {item.get('text_index', '?')} 条缺少 embedding 字段"
            )
        embeddings.append(item["embedding"])

    if len(embeddings) != text_count:
        raise VectorStoreErrorException(
            f"Embedding 数量不匹配: 期望 {text_count}, 实际 {len(embeddings)}"
        )

    # 验证所有 embedding 维度一致
    if embeddings:
        dim = len(embeddings[0])
        for idx, emb in enumerate(embeddings):
            if len(emb) != dim:
                raise ValueError(
                    f"Embedding 维度不一致: 第 0 条 {dim} 维, 第 {idx} 条 {len(emb)} 维"
                )

    total_tokens = usage.get("total_tokens", 0)

    # API 仅返回总量不返回每条，按等比例分配（余数分配到前几条，避免整除丢弃）
    if text_count:
        if total_tokens >= text_count:
            per_text = total_tokens // text_count
            remainder = total_tokens - per_text * text_count
            token_counts = [per_text + 1] * remainder + [per_text] * (text_count - remainder)
        else:
            token_counts = [1] * text_count
    else:
        token_counts = []

    return EmbedResult(
        embeddings=embeddings,
        token_counts=token_counts,
        total_tokens=total_tokens,
    )


def _safe_truncate(text: str, max_len: int = 200) -> str:
    """截断文本用于日志，防止 API 响应过长撑爆日志"""
    return text[:max_len] if len(text) > max_len else text


async def embed_chunks(texts: list[str], text_type: str = "document") -> EmbedResult:
    """对文本列表执行 Embedding 向量化。

    Args:
        texts: 待向量化的文本列表
        text_type: "document"（入库文档）或 "query"（检索查询）

    Returns:
        EmbedResult: 包含 embeddings、token_counts、total_tokens

    Raises:
        RuntimeError: API 调用失败（已重试 5 次后仍失败）
    """
    if not texts:
        return EmbedResult()

    if len(texts) > settings.EMBED_BATCH_SIZE:
        raise ValueError(
            f"单次 Embedding 文本数超过上限: {len(texts)} > {settings.EMBED_BATCH_SIZE}"
        )

    logger.info("开始 Embedding 向量化: %d 条文本 (type=%s)", len(texts), text_type)
    result = await _call_embed_api(texts, text_type)
    logger.info(
        "Embedding 完成: %d 条, total_tokens=%d",
        len(texts), result.total_tokens,
    )
    return result


