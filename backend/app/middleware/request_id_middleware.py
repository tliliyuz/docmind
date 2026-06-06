"""Request ID 中间件 — 为每个请求生成唯一 request_id，写入 contextvars + response header

对齐 ARCHITECTURE.md §9.3.4：跨请求传递 request_id，便于日志链路追踪。
"""

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import get_request_id, request_id_var, user_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求生成唯一 request_id，写入 contextvars + response header。

    优先从客户端 X-Request-ID header 获取（支持链路透传），否则生成新 ID。
    """

    async def dispatch(self, request: Request, call_next):
        # 优先从客户端 header 获取（支持链路透传），否则生成新 ID
        rid = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        token_rid = request_id_var.set(rid)

        # 尝试从 request.state 获取 user_id（AuthMiddleware 已注入）
        token_uid = None
        try:
            uid = request.state.user_id
            token_uid = user_id_var.set(uid)
        except AttributeError:
            pass

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token_rid)
            if token_uid is not None:
                user_id_var.reset(token_uid)
