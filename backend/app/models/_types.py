"""SQLAlchemy 自定义类型 — UTCDateTime 确保 ORM 层读写均带 UTC tzinfo

设计意图（对齐 ARCHITECTURE.md §12）：
- MySQL DATETIME 列不存储时区，PyMySQL/aiomysql 驱动返回 naive datetime
- 本 TypeDecorator 在 ORM 层完成 aware ↔ naive 双向转换：
  - 写入：astimezone(UTC) + replace(tzinfo=None) → DB 存 UTC naive
  - 读取：replace(tzinfo=UTC) → 返回 aware datetime
- Pydantic 拿到 aware datetime → 自动序列化为 "2026-06-09T12:00:02Z"
- 前端 new Date("...Z") → 自动转为本地时区显示
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """UTC datetime 类型 — ORM 层确保始终返回 timezone-aware datetime。

    impl = DateTime 表示底层仍用 MySQL DATETIME 列存储，无需迁移。
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        """写入 DB 前：剥离 tzinfo（DB 存 naive UTC 值）。"""
        if value is None:
            return None
        # 先转为 UTC，再剥离 tzinfo（避免 DST 偏移问题）
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        """从 DB 读取后：附加 UTC tzinfo（返回 aware datetime）。"""
        if value is None:
            return None
        # DB 约定存储 UTC → 直接附加 UTC tzinfo
        return value.replace(tzinfo=timezone.utc)
