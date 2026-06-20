"""Request ID 中间件 — 为每个请求生成唯一 request_id，写入 contextvars + response header

对齐 ARCHITECTURE.md §9.3.4：跨请求传递 request_id，便于日志链路追踪。

纯 ASGI 中间件（与 AuthMiddleware、RateLimitMiddleware 一致），不使用 BaseHTTPMiddleware。
"""

from uuid import uuid4

from starlette.requests import Request

from app.core.logging_config import get_request_id, request_id_var, user_id_var


class RequestIDMiddleware:
    """纯 ASGI 中间件 — 为每个请求生成唯一 request_id，写入 contextvars + response header。

    优先从客户端 X-Request-ID header 获取（支持链路透传），否则生成新 ID。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

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

        # 包装 send 以注入 X-Request-ID response header
        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", rid.encode()))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token_rid)
            if token_uid is not None:
                user_id_var.reset(token_uid)
