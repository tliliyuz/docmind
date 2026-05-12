"""JWT 验证中间件 — 从 Authorization header 提取并验证 Bearer Token，将当前用户写入 request.state

使用纯 ASGI 中间件（非 BaseHTTPMiddleware），以便正确返回 JSON 错误响应。
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import decode_access_token

# 不需要认证的公开路由
_PUBLIC_PATHS = {
    "/api/auth/register",
    "/api/auth/login",
    "/api/health",
    "/docs",
    "/openapi.json",
}


class AuthMiddleware:
    """纯 ASGI 中间件 — JWT 认证"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        # OPTIONS 预检 + 公开路由跳过认证
        if (
            request.method == "OPTIONS"
            or request.url.path in _PUBLIC_PATHS
            or request.url.path.startswith("/docs")
            or request.url.path.startswith("/openapi.json")
        ):
            await self.app(scope, receive, send)
            return

        # 提取 Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            response = JSONResponse(
                status_code=401,
                content={
                    "code": "E5004",
                    "message": "Token 无效或格式错误",
                    "detail": "缺少 Authorization header 或格式不是 Bearer",
                },
            )
            await response(scope, receive, send)
            return

        token = auth_header[7:]
        payload = decode_access_token(token)

        if not payload:
            response = JSONResponse(
                status_code=401,
                content={
                    "code": "E5004",
                    "message": "Token 无效或格式错误",
                    "detail": "Token 解析失败或已过期",
                },
            )
            await response(scope, receive, send)
            return

        # 将用户信息写入 request.state
        request.state.user_id = int(payload.get("sub"))
        request.state.username = payload.get("username")
        request.state.role = payload.get("role")

        await self.app(scope, receive, send)
