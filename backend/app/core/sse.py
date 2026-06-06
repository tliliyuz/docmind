"""SSE 工具 — Server-Sent Events 格式化与心跳机制

对齐 ARCHITECTURE.md §5.1.3 / API.md §6：
- 手动 StreamingResponse（不用 sse-starlette）
- 6 种事件类型：meta / thinking / message / sources / finish / error
- 15s 心跳注释帧 : ping\\n\\n，防止 Nginx/Cloudflare 代理超时
- 使用 asyncio.wait + timeout 方案实时发送心跳，事件流间隙不阻塞
"""

import asyncio
import json
import logging
from typing import AsyncIterator

from app.config import settings

logger = logging.getLogger(__name__)


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


async def stream_with_heartbeat(
    event_generator: AsyncIterator[str],
    interval: int = settings.SSE_HEARTBEAT_INTERVAL,
) -> AsyncIterator[str]:
    """将事件流与心跳流合并输出。

    事件流优先输出；当事件流在 interval 秒内无新事件时，自动发送心跳帧。
    事件流结束后自动停止。

    实现方案：使用 asyncio.wait + timeout 同时等待下一事件和心跳定时器。
    - 事件先到达 → 立即输出事件，继续等待下一事件
    - timeout 先触发 → 输出心跳帧，继续等待同一事件（不取消事件任务）

    Args:
        event_generator: SSE 事件生成器
        interval: 心跳间隔秒数

    Yields:
        SSE 格式字符串（事件或心跳）
    """
    event_iter = event_generator.__aiter__()
    _done = object()  # 哨兵值，标识事件流结束

    async def _fetch_next() -> str:
        """获取下一个事件，事件流结束时返回哨兵值。"""
        try:
            return await event_iter.__anext__()
        except StopAsyncIteration:
            return _done  # type: ignore[return-value]

    # 发起第一个事件获取任务
    pending = asyncio.ensure_future(_fetch_next())

    try:
        while True:
            done, _ = await asyncio.wait([pending], timeout=interval)

            if pending in done:
                result = pending.result()
                if result is _done:
                    return  # 事件流正常结束
                yield result
                # 发起下一个事件获取任务
                pending = asyncio.ensure_future(_fetch_next())
            else:
                # timeout → 事件流静默期间发送心跳
                yield format_sse_heartbeat()
                # 不取消 pending，继续等待同一事件
    finally:
        # 清理：取消未完成的事件获取任务
        if not pending.done():
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
