"""结构化日志 — JSON 格式输出 + request_id 链路追踪

对齐 ARCHITECTURE.md §9.3：
- JSONFormatter：生产环境 JSON 格式日志，便于 ELK/Loki 索引
- RequestIDFilter：从 contextvars 注入 request_id / user_id 到每条日志
- setup_logging()：配置 root logger（DEBUG→console，非 DEBUG→JSON）
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# 跨 async 函数传递的上下文变量（对齐 ARCHITECTURE.md §9.3.4）
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[int] = ContextVar("user_id", default=0)


def get_request_id() -> str:
    """获取当前请求的 request_id（无请求上下文时返回空字符串）"""
    return request_id_var.get()


def get_user_id() -> int:
    """获取当前请求的 user_id（无请求上下文时返回 0）"""
    return user_id_var.get()


class JSONFormatter(logging.Formatter):
    """JSON 格式日志 formatter

    输出字段对齐 ARCHITECTURE.md §9.3.2：
    {
        "timestamp": "2026-06-05T10:30:00.123Z",
        "level": "INFO",
        "request_id": "a1b2c3d4",
        "user_id": 1,
        "logger": "app.services.chat_service",
        "message": "检索完成",
        "extra": {...}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", ""),
            "user_id": getattr(record, "user_id", 0),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 附加 extra 字段（排除标准字段和内部字段）
        _standard = {
            "name", "msg", "args", "created", "relativeCreated",
            "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "pathname", "filename", "module", "levelno", "levelname",
            "msecs", "thread", "threadName", "processName", "process",
            "request_id", "user_id", "message",
        }
        extra = {
            k: v for k, v in record.__dict__.items()
            if k not in _standard and not k.startswith("_")
        }
        if extra:
            log_entry["extra"] = extra

        # 异常信息
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }
            if record.exc_text:
                log_entry["traceback"] = record.exc_text

        return json.dumps(log_entry, ensure_ascii=False)


class RequestIDFilter(logging.Filter):
    """从 contextvars 注入 request_id / user_id 到 LogRecord"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True


def setup_logging(debug: bool = False) -> None:
    """配置 root logger

    Args:
        debug: True → 人类可读 console 输出；False → JSON 格式 stdout
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # 清除已有 handler（避免重复添加）
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug else logging.INFO)

    if debug:
        # 开发环境：人类可读格式
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # 生产环境：JSON 格式
        formatter = JSONFormatter()

    handler.setFormatter(formatter)
    handler.addFilter(RequestIDFilter())
    root.addHandler(handler)

    # 降低第三方库日志级别
    for noisy in ["httpx", "httpcore", "aiomysql", "sqlalchemy.engine"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
