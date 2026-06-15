"""KB 访问权限检查 — 共享纯函数

对齐 PRD.md §5.4 三层权限模型：
- visibility 控制 READ：public→所有登录用户，private→owner+admin
- ownership 控制 WRITE：owner+admin 可删/改元数据
- owner-only：上传/reprocess 仅 owner（admin 不可代传）

所有函数操作已加载的 KnowledgeBase 对象，不触发 DB 查询。
"""

from app.core.exceptions import PermissionDeniedException
from app.models.knowledge_base import KnowledgeBase


def require_kb_readable(kb: KnowledgeBase, user_id: int, role: str) -> None:
    """READ 权限检查（visibility 优先）。

    public KB：所有登录用户可读
    private KB：仅 owner 或 admin 可读

    Raises:
        PermissionDeniedException: 当前用户无读权限
    """
    if kb.visibility == "private" and kb.user_id != user_id and role != "admin":
        raise PermissionDeniedException()


def require_kb_writable(kb: KnowledgeBase, user_id: int, role: str) -> None:
    """WRITE 权限检查（ownership 基础）。

    owner 或 admin 可执行写操作（删除 KB/文档、修正元数据）。
    上传文档除外——请使用 require_kb_owner()。

    Raises:
        PermissionDeniedException: 当前用户无写权限
    """
    if kb.user_id != user_id and role != "admin":
        raise PermissionDeniedException()


def require_kb_owner(kb: KnowledgeBase, user_id: int) -> None:
    """Owner-only 权限检查。

    仅 KB 所有者可操作（admin 也不允许）。
    用于上传文档、reprocess 等写操作。

    Raises:
        PermissionDeniedException: 当前用户非 owner
    """
    if kb.user_id != user_id:
        raise PermissionDeniedException()
