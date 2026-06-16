"""通用工具函数 — 供 services 层等模块复用"""


def escape_like(value: str) -> str:
    r"""转义 SQL LIKE 通配符 ``%`` 和 ``_``，防止用户输入被解释为 LIKE 模式。

    MySQL / SQLite 默认使用 ``\`` 作为 ESCAPE 字符。

    供 admin_service / trace_service / document_service 等模糊搜索复用。
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
