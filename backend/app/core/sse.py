"""SSE 工具 — Server-Sent Events 格式化与心跳机制

对齐 ARCHITECTURE.md §5.1.3 / API.md §6：
- 手动 StreamingResponse（不用 sse-starlette）
- 6 种事件类型：meta / thinking / message / sources / finish / error
- 15s 心跳注释帧 : ping\\n\\n，防止 Nginx/Cloudflare 代理超时
"""

import asyncio
import json
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# 心跳间隔（秒），对齐 ARCHITECTURE.md §5.1.3
HEARTBEAT_INTERVAL = 15


def format_sse_event(event_type: str, data: dict | str) -> str:
    """格式化单个 SSE 事件为标准文本。

    SSE 格式：
        event: <type>\\n
        data: <json>\\n
        \\n

    Args:
        event_type: 事件类型（meta / thinking / message / sources / finish / error）
        data: 事件数据，dict 会被 json.dumps 序列化

    Returns:
        格式化的 SSE 事件字符串
    """
    if isinstance(data, dict):
        data_str = json.dumps(data, ensure_ascii=False)
    else:
        data_str = data
    return f"event: {event_type}\ndata: {data_str}\n\n"


def format_sse_heartbeat() -> str:
    """格式化 SSE 心跳注释帧。

    浏览器忽略注释帧（以 : 开头），但代理服务器（Nginx/Cloudflare）
    会重置超时计时器，保持连接活跃。
    """
    return ": ping\n\n"


async def _heartbeat_generator(interval: int = HEARTBEAT_INTERVAL) -> AsyncIterator[str]:
    """心跳生成器，定期产出 SSE 注释帧。"""
    while True:
        await asyncio.sleep(interval)
        yield format_sse_heartbeat()


async def stream_with_heartbeat(
    event_generator: AsyncIterator[str],
    interval: int = HEARTBEAT_INTERVAL,
) -> AsyncIterator[str]:
    """将事件流与心跳流合并输出。

    事件流优先输出；心跳仅在事件间隙定时发送。
    事件流结束后自动停止心跳。

    Args:
        event_generator: SSE 事件生成器
        interval: 心跳间隔秒数

    Yields:
        SSE 格式字符串（事件或心跳）
    """
    heartbeat_task = asyncio.create_task(_collect_heartbeat(interval))

    try:
        async for event in event_generator:
            yield event
    finally:
        heartbeat_task.cancel()
        try:
            # 收集已产生但未输出的心跳帧
            for hb in heartbeat_task.result():
                yield hb
        except (asyncio.CancelledError, Exception):
            pass


async def _collect_heartbeat(interval: int) -> list[str]:
    """心跳收集器（后台任务），收集所有心跳帧。

    返回值仅用于任务取消后的残余帧收集，正常流程中此协程不自行结束。
    """
    frames: list[str] = []
    while True:
        await asyncio.sleep(interval)
        frames.append(format_sse_heartbeat())
