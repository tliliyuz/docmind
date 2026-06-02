"""ChatRequest Schema 校验测试

对齐 TEST_CASES.md §5.10：
- U7.90 question 空 → ValidationError
- U7.91 question 超长 → ValidationError
- U7.92 kb_id 缺失 → ValidationError
- U7.93 conversation_id 可选 → 默认 None
- U7.94 deep_thinking 默认值 → 默认 False
- U7.97 正常请求 → 通过
"""

import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest


class TestChatRequestSchema:
    """ChatRequest Pydantic 模型校验"""

    def test_question空应报错(self):
        """U7.90 — question 为空字符串时应抛 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(kb_id=1, question="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("question",) for e in errors)

    def test_question超长应报错(self):
        """U7.91 — question 超过 2000 字符时应抛 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(kb_id=1, question="x" * 2001)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("question",) for e in errors)

    def test_kb_id缺失应报错(self):
        """U7.92 — kb_id 缺失时应抛 ValidationError（必填字段）"""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(question="测试问题")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("kb_id",) for e in errors)

    def test_conversation_id可选默认None(self):
        """U7.93 — conversation_id 不传时应默认为 None"""
        req = ChatRequest(kb_id=1, question="测试问题")
        assert req.conversation_id is None

    def test_deep_thinking默认关闭(self):
        """U7.94 — deep_thinking 不传时应默认为 False"""
        req = ChatRequest(kb_id=1, question="测试问题")
        assert req.deep_thinking is False

    def test_正常请求全部字段(self):
        """U7.97 — 所有字段合法时应正常创建"""
        req = ChatRequest(
            conversation_id=42,
            kb_id=1,
            question="这是一个测试问题",
            deep_thinking=True,
        )
        assert req.conversation_id == 42
        assert req.kb_id == 1
        assert req.question == "这是一个测试问题"
        assert req.deep_thinking is True
