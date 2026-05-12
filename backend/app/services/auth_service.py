"""认证业务逻辑 — 注册 / 登录"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.exceptions import InvalidCredentialsException, UsernameExistsException
from app.models.user import User
from app.schemas.auth import TokenResponse, UserResponse
from app.config import settings


async def register(db: AsyncSession, username: str, password: str) -> UserResponse:
    """注册新用户，用户名重复时抛出 UsernameExistsException"""
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none() is not None:
        raise UsernameExistsException(username)

    user = User(
        username=username,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


async def login(db: AsyncSession, username: str, password: str) -> TokenResponse:
    """验证用户名密码，返回 JWT access_token"""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsException()

    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )
