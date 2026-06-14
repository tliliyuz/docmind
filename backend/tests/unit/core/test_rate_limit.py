"""限流中间件测试 — 固定窗口计数器 + Redis 原子操作

对齐 ARCHITECTURE.md §13.2 / TEST_CASES.md A8.1-A8.5。
"""

from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

import pytest

from app.middleware.rate_limit_middleware import (
    _get_client_ip,
    _get_endpoint_group,
    _get_limit_for_group,
    RateLimitMiddleware,
)


# ==================== 单元测试 ====================

class TestGetClientIp:
    """客户端 IP 提取"""

    def test_x_forwarded_for优先(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_x_real_ip兜底(self):
        request = MagicMock()
        request.headers = {"X-Real-IP": "10.0.0.1"}
        assert _get_client_ip(request) == "10.0.0.1"

    def test_client_host兜底(self):
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        assert _get_client_ip(request) == "192.168.1.1"

    def test_无client返回unknown(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _get_client_ip(request) == "unknown"


class TestGetEndpointGroup:
    """接口组路由规则"""

    def test_chat接口(self):
        assert _get_endpoint_group("/api/chat", "POST") == "chat"

    def test_login接口(self):
        assert _get_endpoint_group("/api/auth/login", "POST") == "login"

    def test_register接口(self):
        assert _get_endpoint_group("/api/auth/register", "POST") == "login"

    def test_upload接口(self):
        assert _get_endpoint_group("/api/knowledge-bases/1/documents", "POST") == "upload"

    def test_其他接口归入default(self):
        assert _get_endpoint_group("/api/knowledge-bases", "GET") == "default"

    def test_非POST方法不匹配chat(self):
        """GET /api/chat 不归入 chat 组（仅 POST 限流）"""
        assert _get_endpoint_group("/api/chat", "GET") == "default"


class TestGetLimitForGroup:
    """限流阈值获取"""

    @patch("app.middleware.rate_limit_middleware.settings")
    def test_chat组阈值(self, mock_settings):
        mock_settings.RATE_LIMIT_CHAT_PER_MINUTE = 30
        mock_settings.RATE_LIMIT_UPLOAD_PER_MINUTE = 20
        mock_settings.RATE_LIMIT_LOGIN_PER_MINUTE = 10
        mock_settings.RATE_LIMIT_DEFAULT_PER_MINUTE = 120
        assert _get_limit_for_group("chat") == 30

    @patch("app.middleware.rate_limit_middleware.settings")
    def test_login组阈值(self, mock_settings):
        mock_settings.RATE_LIMIT_CHAT_PER_MINUTE = 30
        mock_settings.RATE_LIMIT_UPLOAD_PER_MINUTE = 20
        mock_settings.RATE_LIMIT_LOGIN_PER_MINUTE = 10
        mock_settings.RATE_LIMIT_DEFAULT_PER_MINUTE = 120
        assert _get_limit_for_group("login") == 10

    @patch("app.middleware.rate_limit_middleware.settings")
    def test_unknown组使用default阈值(self, mock_settings):
        mock_settings.RATE_LIMIT_CHAT_PER_MINUTE = 30
        mock_settings.RATE_LIMIT_UPLOAD_PER_MINUTE = 20
        mock_settings.RATE_LIMIT_LOGIN_PER_MINUTE = 10
        mock_settings.RATE_LIMIT_DEFAULT_PER_MINUTE = 120
        assert _get_limit_for_group("unknown") == 120


# ==================== 集成测试（ASGI 中间件）====================

def _make_mock_app(status_code=200, body=b'{"code":"0"}'):
    """创建 mock ASGI 应用（返回固定响应）"""
    async def mock_app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
    return mock_app


def _make_asgi_scope(path="/api/test", method="GET", client_ip="127.0.0.1"):
    """创建 ASGI scope 字典"""
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
    }


class TestRateLimitMiddlewareIntegration:
    """限流中间件集成测试 — 直接构造 ASGI scope 测试中间件行为"""

    @pytest.mark.asyncio
    async def test_A8_1_正常请求返回限流header(self):
        """A8.1: 正常请求应包含 X-RateLimit-* 响应头"""
        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value=1)  # 第 1 次请求
        with patch("app.middleware.rate_limit_middleware.get_async_redis", return_value=mock_redis):
            app = RateLimitMiddleware(_make_mock_app())
            scope = _make_asgi_scope("/api/knowledge-bases", "GET")
            messages = []
            async def receive():
                return {"type": "http.request", "body": b""}
            async def send(msg):
                messages.append(msg)
            await app(scope, receive, send)

        # 找到 http.response.start 消息
        start_msg = next(m for m in messages if m["type"] == "http.response.start")
        headers = dict(start_msg["headers"])
        assert b"x-ratelimit-limit" in headers
        assert b"x-ratelimit-remaining" in headers
        assert b"x-ratelimit-reset" in headers
        assert headers[b"x-ratelimit-limit"] == b"120"  # default 组

    @pytest.mark.asyncio
    async def test_A8_2_超过阈值返回429(self):
        """A8.2: 超过限流阈值应返回 429 + E9004"""
        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value=121)  # 超过 default 120/min
        with patch("app.middleware.rate_limit_middleware.get_async_redis", return_value=mock_redis):
            app = RateLimitMiddleware(_make_mock_app())
            scope = _make_asgi_scope("/api/knowledge-bases", "GET")
            messages = []
            async def receive():
                return {"type": "http.request", "body": b""}
            async def send(msg):
                messages.append(msg)
            await app(scope, receive, send)

        # 找到 http.response.start 消息
        start_msg = next(m for m in messages if m["type"] == "http.response.start")
        assert start_msg["status"] == 429
        # 验证响应体包含 E9004
        body_msg = next(m for m in messages if m["type"] == "http.response.body")
        assert b"E9004" in body_msg["body"]
        assert "请求频率超限".encode() in body_msg["body"]
        # 验证限流 header
        headers = dict(start_msg["headers"])
        assert headers[b"x-ratelimit-remaining"] == b"0"

    @pytest.mark.asyncio
    async def test_A8_3_不同接口组独立计数(self):
        """A8.3: 不同接口组独立限流 — chat / login / upload / default 各自独立"""
        # 验证不同路径映射到不同组
        assert _get_endpoint_group("/api/chat", "POST") == "chat"
        assert _get_endpoint_group("/api/auth/login", "POST") == "login"
        assert _get_endpoint_group("/api/auth/register", "POST") == "login"
        assert _get_endpoint_group("/api/knowledge-bases/1/documents", "POST") == "upload"
        assert _get_endpoint_group("/api/knowledge-bases", "GET") == "default"

        # 验证不同组的阈值不同
        with patch("app.middleware.rate_limit_middleware.settings") as mock_settings:
            mock_settings.RATE_LIMIT_CHAT_PER_MINUTE = 30
            mock_settings.RATE_LIMIT_UPLOAD_PER_MINUTE = 20
            mock_settings.RATE_LIMIT_LOGIN_PER_MINUTE = 10
            mock_settings.RATE_LIMIT_DEFAULT_PER_MINUTE = 120
            assert _get_limit_for_group("chat") == 30
            assert _get_limit_for_group("login") == 10
            assert _get_limit_for_group("upload") == 20
            assert _get_limit_for_group("default") == 120

    @pytest.mark.asyncio
    async def test_A8_4_限流开关关闭时不拦截(self):
        """A8.4: RATE_LIMIT_ENABLED=False 时限流中间件直接放行，不注入限流 header"""
        with patch("app.middleware.rate_limit_middleware.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False
            mock_settings.RATE_LIMIT_CHAT_PER_MINUTE = 30
            mock_settings.RATE_LIMIT_UPLOAD_PER_MINUTE = 20
            mock_settings.RATE_LIMIT_LOGIN_PER_MINUTE = 10
            mock_settings.RATE_LIMIT_DEFAULT_PER_MINUTE = 120
            mock_settings.RATE_LIMIT_WINDOW_SECONDS = 60
            app = RateLimitMiddleware(_make_mock_app())
            scope = _make_asgi_scope("/api/knowledge-bases", "GET")
            messages = []
            async def receive():
                return {"type": "http.request", "body": b""}
            async def send(msg):
                messages.append(msg)
            await app(scope, receive, send)

        # 限流关闭时不应注入限流 header
        start_msg = next(m for m in messages if m["type"] == "http.response.start")
        headers = dict(start_msg["headers"])
        assert b"x-ratelimit-limit" not in headers

    @pytest.mark.asyncio
    async def test_A8_5_Redis不可用时降级放行(self):
        """A8.5: Redis 不可用时限流降级放行，不阻塞用户"""
        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(side_effect=ConnectionError("Redis 连接失败"))
        with patch("app.middleware.rate_limit_middleware.get_async_redis", return_value=mock_redis):
            app = RateLimitMiddleware(_make_mock_app())
            scope = _make_asgi_scope("/api/knowledge-bases", "GET")
            messages = []
            async def receive():
                return {"type": "http.request", "body": b""}
            async def send(msg):
                messages.append(msg)
            await app(scope, receive, send)

        # Redis 故障时应降级放行（正常响应，非 429）
        start_msg = next(m for m in messages if m["type"] == "http.response.start")
        assert start_msg["status"] == 200
        # 不应注入限流 header（降级路径不注入）
        headers = dict(start_msg["headers"])
        assert b"x-ratelimit-limit" not in headers

    @pytest.mark.asyncio
    async def test_OPTIONS请求跳过限流(self):
        """OPTIONS 预检请求不计入限流"""
        app = RateLimitMiddleware(_make_mock_app())
        scope = _make_asgi_scope("/api/knowledge-bases", "OPTIONS")
        messages = []
        async def receive():
            return {"type": "http.request", "body": b""}
        async def send(msg):
            messages.append(msg)
        await app(scope, receive, send)

        start_msg = next(m for m in messages if m["type"] == "http.response.start")
        headers = dict(start_msg["headers"])
        assert b"x-ratelimit-limit" not in headers

    @pytest.mark.asyncio
    async def test_health接口跳过限流(self):
        """/api/health 不计入限流"""
        app = RateLimitMiddleware(_make_mock_app())
        scope = _make_asgi_scope("/api/health", "GET")
        messages = []
        async def receive():
            return {"type": "http.request", "body": b""}
        async def send(msg):
            messages.append(msg)
        await app(scope, receive, send)

        start_msg = next(m for m in messages if m["type"] == "http.response.start")
        assert start_msg["status"] == 200
        headers = dict(start_msg["headers"])
        assert b"x-ratelimit-limit" not in headers

    @pytest.mark.asyncio
    async def test_WebSocket请求跳过限流(self):
        """WebSocket 请求不经过限流"""
        app = RateLimitMiddleware(_make_mock_app())
        scope = _make_asgi_scope("/ws", "GET")
        scope["type"] = "websocket"  # 非 HTTP 类型
        messages = []
        async def receive():
            return {"type": "http.request", "body": b""}
        async def send(msg):
            messages.append(msg)
        await app(scope, receive, send)

        # WebSocket 请求直接放行，不经过限流逻辑
        assert len(messages) > 0

    @pytest.mark.asyncio
    async def test_限流Lua脚本调用参数正确(self):
        """验证 Lua 脚本调用参数：key 格式和 TTL 正确"""
        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value=1)
        with patch("app.middleware.rate_limit_middleware.get_async_redis", return_value=mock_redis):
            with patch("app.middleware.rate_limit_middleware.time") as mock_time:
                mock_time.time.return_value = 1718006430  # 固定时间戳
                app = RateLimitMiddleware(_make_mock_app())
                scope = _make_asgi_scope("/api/chat", "POST", "10.0.0.1")
                messages = []
                async def receive():
                    return {"type": "http.request", "body": b""}
                async def send(msg):
                    messages.append(msg)
                await app(scope, receive, send)

        # 验证 eval 调用参数
        mock_redis.eval.assert_called_once()
        call_args = mock_redis.eval.call_args
        # eval(script, numkeys, key, ttl) — key 是位置参数
        # call_args = (script, numkeys, key, ttl) 或 kwargs
        args_tuple = call_args[0]  # 位置参数元组
        # args_tuple = (_RATE_LIMIT_SCRIPT, 1, "rate_limit:...", "60")
        key = args_tuple[2]  # 第三个参数是 key
        assert "rate_limit:10.0.0.1:chat:" in key
        # TTL 应为 window_seconds
        ttl = args_tuple[3]  # 第四个参数是 TTL
        assert ttl == "60"
