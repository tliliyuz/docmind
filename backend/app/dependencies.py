"""依赖注入 — DB session、当前用户等"""

from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.exceptions import PermissionDeniedException, UserDisabledException
from app.models.user import User


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """每次请求获取一个异步 DB session，结束时自动提交/关闭"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    """从 request.state 中获取已认证用户信息（由 AuthMiddleware 注入），
    并校验用户 status 是否被禁用。

    复用 get_db() 的 DB session，避免每个认证请求额外开启一个 session。
    路由中通过 Depends(get_current_user) 使用。
    """
    user_id = request.state.user_id
    # 校验用户是否被禁用（主键查询，毫秒级）
    user = await db.get(User, user_id)
    if user is None or user.status == "disabled":
        raise UserDisabledException()
    return {
        "user_id": user_id,
        "username": request.state.username,
        "role": request.state.role,
    }


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """依赖注入：要求当前用户为 admin 角色。

    对齐 API.md §7.1：所有 /api/admin/* 端点要求 role=admin，
    非 admin 返回 403 E5005。
    """
    if current_user.get("role") != "admin":
        raise PermissionDeniedException()
    return current_user
