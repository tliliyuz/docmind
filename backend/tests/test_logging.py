"""结构化日志测试 — JSONFormatter / RequestIDFilter / setup_logging

对齐 ARCHITECTURE.md §9.3 / ROADMAP.md §6.6 错误处理测试。
"""

import json
import logging
from unittest.mock import patch

import pytest

from app.core.logging_config import (
    JSONFormatter,
    RequestIDFilter,
    get_request_id,
    get_user_id,
    request_id_var,
    setup_logging,
    user_id_var,
)


class TestJSONFormatter:
    """JSONFormatter 输出格式测试"""

    def test输出有效JSON(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="测试消息", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "测试消息"
        assert data["logger"] == "test"

    def test包含时间戳(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "timestamp" in data
        # ISO 格式检查
        assert "T" in data["timestamp"]

    def test包含request_id和user_id(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        # 模拟 RequestIDFilter 注入
        record.request_id = "abc123"
        record.user_id = 42
        output = formatter.format(record)
        data = json.loads(output)
        assert data["request_id"] == "abc123"
        assert data["user_id"] == 42

    def test异常信息序列化(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("测试异常")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="",
            lineno=1, msg="出错了", args=(), exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "测试异常"

    def test_extra字段序列化(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        record.custom_field = "自定义值"
        output = formatter.format(record)
        data = json.loads(output)
        assert "extra" in data
        assert data["extra"]["custom_field"] == "自定义值"

    def test中文消息正确序列化(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="中文日志消息", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "中文日志消息"


class TestRequestIDFilter:
    """RequestIDFilter contextvars 注入测试"""

    def test注入request_id(self):
        f = RequestIDFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        token = request_id_var.set("req-123")
        try:
            f.filter(record)
            assert record.request_id == "req-123"
        finally:
            request_id_var.reset(token)

    def test注入user_id(self):
        f = RequestIDFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        token = user_id_var.set(99)
        try:
            f.filter(record)
            assert record.user_id == 99
        finally:
            user_id_var.reset(token)

    def test无上下文时默认值(self):
        f = RequestIDFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        f.filter(record)
        assert record.request_id == ""
        assert record.user_id == 0


class TestSetupLogging:
    """setup_logging 配置测试"""

    def test_debug模式设置console_handler(self):
        setup_logging(debug=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert root.level == logging.DEBUG

    def test生产模式设置json_handler(self):
        setup_logging(debug=False)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert root.level == logging.INFO
        handler = root.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test不重复添加handler(self):
        setup_logging(debug=True)
        setup_logging(debug=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1
