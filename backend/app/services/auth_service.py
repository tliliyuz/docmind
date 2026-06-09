"""认证业务逻辑 — 注册 / 登录 / Token 刷新 / 退出 / 改密

对齐 ARCHITECTURE.md §9.2：
- login()：签发 access_token + refresh_token，refresh_token 哈希存 MySQL
- refresh()：Rotation — 验证旧 token → 吊销 → 签发新 token 对
- logout()：吊销指定 refresh_token
- change_password()：改密 + 吊销该用户全部 refresh_token（强制下线）
"""

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    InvalidCredentialsException,
    InvalidRefreshTokenException,
    RefreshTokenExpiredException,
    RefreshTokenRevokedException,
    TokenLeakDetectedException,
    UsernameExistsException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse, UserResponse

logger = logging.getLogger(__name__)


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
    """验证用户名密码，返回 access_token + refresh_token。

    对齐 API.md §2 POST /api/auth/login：
    - access_token 15min 短有效期
    - refresh_token 7 天长有效期，SHA-256 哈希存 MySQL
    """
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsException()

    # 签发 token 对
    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token_str = create_refresh_token(user.id)

    # refresh_token 哈希存 MySQL
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token_str),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    await db.flush()

    logger.info("用户登录成功: user_id=%d", user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def refresh(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
    """Rotation：用旧 refresh_token 换取新 token 对。

    对齐 ARCHITECTURE.md §9.2.4：
    1. 解码 refresh_token JWT
    2. SHA-256 哈希 → 查 refresh_tokens 表
    3. 检查 revoked_at / expires_at
    4. 泄露检测：已吊销 token 被重用 → 吊销该用户全部 token（E5009）
    5. 旧 token 标记失效 + 签发新 token 对
    """
    # 1. 解码 JWT
    try:
        payload = decode_refresh_token(refresh_token_str)
    except JWTError:
        raise InvalidRefreshTokenException("refresh_token 解码失败或已过期")

    user_id = int(payload["sub"])

    # 2. SHA-256 哈希 → 查表
    token_hash = hash_token(refresh_token_str)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()

    if rt is None:
        # token 不在数据库中（可能从未存储或已被清理）
        raise InvalidRefreshTokenException("refresh_token 不存在")

    # 3. 泄露检测：已吊销 token 被重用
    if rt.revoked_at is not None:
        # 该 token 已被吊销但仍被使用 → 可能泄露，吊销该用户全部 token
        logger.warning(
            "检测到已吊销的 refresh_token 被重用: user_id=%d, 可能泄露",
            user_id,
        )
        await _revoke_all_user_tokens(db, user_id)
        raise TokenLeakDetectedException()

    # 检查过期（DB 已存储 UTC，ORM DateTime(timezone=True) 返回 aware datetime）
    if rt.expires_at < datetime.now(timezone.utc):
        raise RefreshTokenExpiredException()

    # 4. 旧 token 标记失效（Rotation）
    rt.revoked_at = datetime.now(timezone.utc)
    await db.flush()

    # 5. 签发新 token 对
    user = await db.get(User, user_id)
    if user is None:
        raise InvalidRefreshTokenException("用户不存在")

    new_access_token = create_access_token(user.id, user.username, user.role)
    new_refresh_token_str = create_refresh_token(user.id)

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh_token_str),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_rt)
    await db.flush()

    logger.info("Token 刷新成功: user_id=%d", user_id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token_str,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def logout(db: AsyncSession, refresh_token_str: str) -> None:
    """吊销指定 refresh_token。

    对齐 API.md §2 POST /api/auth/logout。
    """
    try:
        payload = decode_refresh_token(refresh_token_str)
    except JWTError:
        raise InvalidRefreshTokenException("refresh_token 解码失败")

    token_hash = hash_token(refresh_token_str)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()

    if rt is not None and rt.revoked_at is None:
        rt.revoked_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info("refresh_token 已吊销: user_id=%d", rt.user_id)


async def change_password(
    db: AsyncSession, user_id: int, old_password: str, new_password: str
) -> None:
    """修改密码 + 吊销该用户全部 refresh_token（强制下线）。

    对齐 API.md §2 PUT /api/auth/password。
    """
    user = await db.get(User, user_id)
    if user is None:
        raise InvalidCredentialsException()

    if not verify_password(old_password, user.password_hash):
        raise InvalidCredentialsException()

    # 更新密码
    user.password_hash = hash_password(new_password)
    await db.flush()

    # 吊销该用户全部 refresh_token
    await _revoke_all_user_tokens(db, user_id)

    logger.info("密码修改成功，全部 refresh_token 已吊销: user_id=%d", user_id)


async def _revoke_all_user_tokens(db: AsyncSession, user_id: int) -> None:
    """吊销指定用户的全部有效 refresh_token。"""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.flush()
