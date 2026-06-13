"""限流中间件 — 固定窗口计数器 + Redis 原子操作（INCR + EXPIRE）

对齐 ARCHITECTURE.md §13.2：
- 算法：固定窗口计数器（Fixed Window Counter）
- Redis Key: rate_limit:{ip}:{endpoint_group}:{window_ts}
- 响应头：X-RateLimit-Limit / X-RateLimit-Remaining / X-RateLimit-Reset
- 错误码：E9004（429 Too Many Requests）

纯 ASGI 中间件（与 AuthMiddleware 同级），不使用 BaseHTTPMiddleware。
"""

import logging
import time

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.core.redis_client import get_async_redis

logger = logging.getLogger(__name__)

# ── Lua 脚本：原子 INCR + 首次设置 TTL ──
# KEYS[1]: 限流 key
# ARGV[1]: 窗口秒数
# 返回: 当前计数值
_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, ttl)
end
return current
"""

# ── 接口组路由规则 ──
# 匹配顺序：先精确路径，再前缀匹配；未命中归入 default
_ENDPOINT_GROUPS = [
    # (路径前缀, 方法限制, 组名)
    ("/api/chat", {"POST"}, "chat"),
    ("/api/auth/login", {"POST"}, "login"),
    ("/api/auth/register", {"POST"}, "login"),
    ("/api/knowledge-bases", {"POST"}, "upload"),  # 文档上传在 KB 子路径
    # 文档上传/批量上传（POST /api/knowledge-bases/{kb_id}/documents）
]

# 不需要限流的路径前缀
_SKIP_PREFIXES = frozenset({
    "/docs",
    "/openapi.json",
    "/api/health",
})


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP（优先反向代理 header，兜底 socket）"""
    # X-Forwarded-For 可能含多个 IP，取第一个（最外层客户端）
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # X-Real-IP（Nginx 常用）
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # 兜底：直连 IP
    if request.client:
        return request.client.host
    return "unknown"


def _get_endpoint_group(path: str, method: str) -> str:
    """根据路径和方法判断接口组（chat / upload / login / default）"""
    for prefix, methods, group in _ENDPOINT_GROUPS:
        if path.startswith(prefix) and method in methods:
            return group
    return "default"


def _get_limit_for_group(group: str) -> int:
    """获取接口组对应的限流阈值（次/分钟）"""
    limits = {
        "chat": settings.RATE_LIMIT_CHAT_PER_MINUTE,
        "upload": settings.RATE_LIMIT_UPLOAD_PER_MINUTE,
        "login": settings.RATE_LIMIT_LOGIN_PER_MINUTE,
        "default": settings.RATE_LIMIT_DEFAULT_PER_MINUTE,
    }
    return limits.get(group, settings.RATE_LIMIT_DEFAULT_PER_MINUTE)


class RateLimitMiddleware:
    """纯 ASGI 中间件 — 固定窗口限流（Redis 原子计数）"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # 仅处理 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = request.url.path
        method = request.method

        # 跳过：OPTIONS 预检 + 非 API 路径 + 限流关闭
        if method == "OPTIONS" or not path.startswith("/api") or path in _SKIP_PREFIXES:
            await self.app(scope, receive, send)
            return

        # 限流开关关闭时直接放行
        if not settings.RATE_LIMIT_ENABLED:
            await self.app(scope, receive, send)
            return

        # 判断接口组
        group = _get_endpoint_group(path, method)
        limit = _get_limit_for_group(group)
        window = settings.RATE_LIMIT_WINDOW_SECONDS

        # 构造 Redis key
        client_ip = _get_client_ip(request)
        window_ts = int(time.time()) // window * window
        key = f"rate_limit:{client_ip}:{group}:{window_ts}"

        try:
            redis_client = await get_async_redis()
            # 原子 INCR + 首次设置 TTL
            current = await redis_client.eval(
                _RATE_LIMIT_SCRIPT, 1, key, str(window),
            )
            current = int(current)
        except Exception as e:
            # Redis 不可用时降级放行（不阻塞用户）
            logger.warning("限流 Redis 操作失败，降级放行: %s", e)
            await self.app(scope, receive, send)
            return

        # 计算剩余配额和重置时间
        remaining = max(0, limit - current)
        reset_at = window_ts + window

        # 未超限 → 放行（注入 rate limit header）
        if current <= limit:
            rate_headers = [
                (b"x-ratelimit-limit", str(limit).encode()),
                (b"x-ratelimit-remaining", str(remaining).encode()),
                (b"x-ratelimit-reset", str(reset_at).encode()),
            ]

            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    # ASGI headers 是 [(b"key", b"value"), ...] 列表
                    raw_headers = list(message.get("headers", []))
                    raw_headers.extend(rate_headers)
                    message["headers"] = raw_headers
                await send(message)

            await self.app(scope, receive, send_with_headers)
            return

        # 超限 → 429 E9004
        logger.warning(
            "限流触发: ip=%s group=%s count=%d limit=%d",
            client_ip, group, current, limit,
        )
        response = JSONResponse(
            status_code=429,
            content={
                "code": "E9004",
                "message": "请求频率超限",
                "detail": f"{group} 接口限制 {limit} 次/{window}秒，请稍后重试",
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
            },
        )
        await response(scope, receive, send)
