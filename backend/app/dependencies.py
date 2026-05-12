"""依赖注入 — DB session、当前用户等"""

from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """每次请求获取一个异步 DB session，结束时自动提交/关闭"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_current_user(request: Request) -> dict:
    """从 request.state 中获取已认证用户信息（由 AuthMiddleware 注入）。
    路由中通过 Depends(get_current_user) 使用。
    """
    return {
        "user_id": request.state.user_id,
        "username": request.state.username,
        "role": request.state.role,
    }
