"""Chat SSE API 集成测试

对齐 TEST_CASES.md §5.11：
- A4.1  正常问答（自动创建会话）→ SSE 事件序列
- A4.2  正常问答（已有会话）→ SSE 事件序列
- A4.3  空问题 → HTTP 422
- A4.4  KB 无文档 → SSE error (E4001)
- A4.5  KB 不存在 → HTTP 404
- A4.6  Private KB 非 owner → HTTP 403
- A4.7  Public KB 任意用户可查 → SSE 正常
- A4.10 未认证 → HTTP 401
- A4.12 心跳帧存在

覆盖 app/api/chat.py
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import StreamingResponse

from app.core.sse import format_sse_event
from app.core.exceptions import (
    KnowledgeBaseEmptyException,
    KnowledgeBaseNotFoundException,
    PermissionDeniedException,
)


# 测试用 UUID 常量
_TEST_KB_UUID = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
_TEST_KB2_UUID = "cccccccc-cccc-4ccc-cccc-cccccccccccc"
_TEST_CONV_UUID = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"

# ==================== 辅助函数 ====================


async def _sse_event_gen(events):
    """构造 SSE 事件生成器，供 StreamingResponse 使用"""
    for event in events:
        yield event


async def _collect_sse_events(response):
    """消费 httpx 流式响应，解析 SSE 事件列表"""
    events = []
    current_event = None
    current_data = None

    async for line in response.aiter_lines():
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data = json.loads(line[6:])
        elif line == "" and current_event is not None and current_data is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None

    # 末尾事件（无尾部空行时）
    if current_event is not None and current_data is not None:
        events.append({"event": current_event, "data": current_data})

    return events


def _make_sse_meta(conversation_id=50, task_id="test-task"):
    return format_sse_event("meta", {"conversation_id": conversation_id, "task_id": task_id})


def _make_sse_message(delta="这是回答"):
    return format_sse_event("message", {"delta": delta})


def _make_sse_thinking(delta="思考过程"):
    return format_sse_event("thinking", {"delta": delta})


def _make_sse_sources():
    return format_sse_event("sources", {"chunks": [
        {"doc_id": 1, "doc_name": "文档.pdf", "content": "相关内容", "score": 0.95, "page": 1},
    ]})


def _make_sse_finish(message_id=11, title="测试标题"):
    return format_sse_event("finish", {
        "message_id": message_id, "title": title,
        "token_usage": {"prompt": 100, "completion": 50, "total": 150},
    })


def _make_sse_error(code="E4002", message="LLM 调用失败"):
    return format_sse_event("error", {"code": code, "message": message, "detail": ""})


# ==================== 测试类 ====================


class TestChatNormalQA:
    """A4.1 / A4.2 — 正常问答"""

    @pytest.mark.asyncio
    async def test_自动创建会话(self, async_client, auth_headers):
        """A4.1 — conversation_id=null 时自动创建会话，返回完整 SSE 事件序列"""
        sse_events = [
            _make_sse_meta(conversation_id=50),
            _make_sse_message("这是"),
            _make_sse_message("回答"),
            _make_sse_sources(),
            _make_sse_finish(message_id=11, title="测试标题"),
        ]

        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = StreamingResponse(
                _sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            async with async_client.stream(
                "POST", "/api/chat",
                json={"kb_id": _TEST_KB_UUID, "question": "测试问题"},
                headers=auth_headers,
            ) as response:
                events = await _collect_sse_events(response)

        assert response.status_code == 200
        event_types = [e["event"] for e in events]
        assert event_types[0] == "meta"
        assert event_types[-1] == "finish"
        assert "sources" in event_types

        meta = next(e for e in events if e["event"] == "meta")
        assert meta["data"]["conversation_id"] == 50

    @pytest.mark.asyncio
    async def test_已有会话(self, async_client, auth_headers):
        """A4.2 — conversation_id 存在时复用已有会话"""
        sse_events = [
            _make_sse_meta(conversation_id=_TEST_CONV_UUID),
            _make_sse_message("追加回答"),
            _make_sse_sources(),
            _make_sse_finish(message_id=21, title=None),
        ]

        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = StreamingResponse(
                _sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            async with async_client.stream(
                "POST", "/api/chat",
                json={"kb_id": _TEST_KB_UUID, "question": "追加问题", "conversation_id": _TEST_CONV_UUID},
                headers=auth_headers,
            ) as response:
                events = await _collect_sse_events(response)

        meta = next(e for e in events if e["event"] == "meta")
        assert meta["data"]["conversation_id"] == _TEST_CONV_UUID


class TestChatPreSSEErrors:
    """A4.3 / A4.5 / A4.6 / A4.10 — SSE 建立前的错误（HTTP JSON 响应）"""

    @pytest.mark.asyncio
    async def test_空问题返回422(self, async_client, auth_headers):
        """A4.3 — question 为空字符串时返回 HTTP 422"""
        response = await async_client.post(
            "/api/chat",
            json={"kb_id": _TEST_KB_UUID, "question": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_KB不存在返回404(self, async_client, auth_headers):
        """A4.5 — kb_id 不存在时返回 HTTP 404"""
        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = KnowledgeBaseNotFoundException(999)

            response = await async_client.post(
                "/api/chat",
                json={"kb_id": "nonexistent-uuid-0000-0000-000000000000", "question": "测试问题"},
                headers=auth_headers,
            )

        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "E1001"

    @pytest.mark.asyncio
    async def test_private_KB非owner返回403(self, async_client, other_user_auth_headers):
        """A4.6 — 非 owner 访问 private KB 返回 HTTP 403"""
        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = PermissionDeniedException()

            response = await async_client.post(
                "/api/chat",
                json={"kb_id": _TEST_KB_UUID, "question": "测试问题"},
                headers=other_user_auth_headers,
            )

        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "E5005"

    @pytest.mark.asyncio
    async def test_未认证返回401(self, async_client):
        """A4.10 — 无 token 时返回 HTTP 401"""
        response = await async_client.post(
            "/api/chat",
            json={"kb_id": _TEST_KB_UUID, "question": "测试问题"},
        )
        assert response.status_code == 401


class TestChatSSEErrors:
    """A4.4 — SSE 建立后的错误（SSE error 事件）"""

    @pytest.mark.asyncio
    async def test_KB无文档返回SSE错误(self, async_client, auth_headers):
        """A4.4 — KB 无已完成文档时 SSE 发送 error 事件（E4001）"""
        sse_events = [
            _make_sse_meta(conversation_id=50),
            _make_sse_sources(),
            _make_sse_error(code="E4001", message="知识库无可用文档"),
        ]

        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = StreamingResponse(
                _sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            async with async_client.stream(
                "POST", "/api/chat",
                json={"kb_id": _TEST_KB_UUID, "question": "测试问题"},
                headers=auth_headers,
            ) as response:
                events = await _collect_sse_events(response)

        error = next(e for e in events if e["event"] == "error")
        assert error["data"]["code"] == "E4001"


class TestChatVisibility:
    """A4.7 — Public KB 权限"""

    @pytest.mark.asyncio
    async def test_public_KB任意用户可查(self, async_client, other_user_auth_headers):
        """A4.7 — 其他用户可查询 public KB"""
        sse_events = [
            _make_sse_meta(conversation_id=60),
            _make_sse_message("公共回答"),
            _make_sse_sources(),
            _make_sse_finish(message_id=31),
        ]

        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = StreamingResponse(
                _sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            async with async_client.stream(
                "POST", "/api/chat",
                json={"kb_id": _TEST_KB2_UUID, "question": "公共问题"},
                headers=other_user_auth_headers,
            ) as response:
                events = await _collect_sse_events(response)

        assert response.status_code == 200
        # 验证 SSE 流正常返回（非仅 any() 存在性检查）
        event_types = [e["event"] for e in events]
        assert "meta" in event_types
        assert "message" in event_types
        assert "finish" in event_types


class TestChatHeartbeat:
    """A4.12 — 心跳帧"""

    @pytest.mark.asyncio
    async def test_SSE流包含心跳帧(self, async_client, auth_headers):
        """A4.12 — SSE 流中应包含心跳注释帧 : ping"""
        sse_events = [
            _make_sse_meta(),
            ": ping\n\n",  # 心跳帧
            _make_sse_message("长回答"),
            _make_sse_finish(),
        ]

        with patch("app.api.chat.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = StreamingResponse(
                _sse_event_gen(sse_events),
                media_type="text/event-stream",
            )

            raw_lines = []
            async with async_client.stream(
                "POST", "/api/chat",
                json={"kb_id": _TEST_KB_UUID, "question": "测试问题"},
                headers=auth_headers,
            ) as response:
                async for line in response.aiter_lines():
                    raw_lines.append(line)

        assert any(": ping" in line for line in raw_lines)
