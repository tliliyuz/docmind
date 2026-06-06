"""认证接口 — 注册 / 登录 / Token 刷新 / 退出 / 改密

对齐 API.md §2：
- POST /api/auth/register — 注册
- POST /api/auth/login — 登录（返回 access_token + refresh_token）
- POST /api/auth/refresh — Token 刷新（Rotation）
- POST /api/auth/logout — 吊销 refresh_token
- PUT /api/auth/password — 改密 + 吊销全部 refresh_token
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services.auth_service import (
    change_password,
    login,
    logout,
    refresh,
    register,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=dict)
async def register_user(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register(db, req.username, req.password)
    return {"code": "0", "message": "注册成功", "data": user.model_dump()}


@router.post("/login", response_model=dict)
async def login_user(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    token = await login(db, req.username, req.password)
    return {"code": "0", "message": "登录成功", "data": token.model_dump()}


@router.post("/refresh", response_model=dict)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token = await refresh(db, req.refresh_token)
    return {"code": "0", "message": "Token 刷新成功", "data": token.model_dump()}


@router.post("/logout", response_model=dict)
async def logout_user(req: LogoutRequest, db: AsyncSession = Depends(get_db)):
    await logout(db, req.refresh_token)
    return {"code": "0", "message": "已退出登录", "data": None}


@router.put("/password", response_model=dict)
async def change_user_password(
    req: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    await change_password(db, user["user_id"], req.old_password, req.new_password)
    return {"code": "0", "message": "密码修改成功，所有设备已下线", "data": None}
