"""认证接口 — POST /api/auth/register  +  POST /api/auth/login"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import login, register

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=dict)
async def register_user(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register(db, req.username, req.password)
    return {"code": "0", "message": "注册成功", "data": user.model_dump()}


@router.post("/login", response_model=dict)
async def login_user(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    token = await login(db, req.username, req.password)
    return {"code": "0", "message": "登录成功", "data": token.model_dump()}
