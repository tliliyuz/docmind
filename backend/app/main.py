"""FastAPI 应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.config import settings
from app.core.exceptions import AppException
from app.middleware.auth_middleware import AuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化 ChromaDB"""
    from app.core.chroma_client import init_chroma

    init_chroma()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS — 开发阶段允许前端跨域（最先添加 = 最外层）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT 认证中间件
app.add_middleware(AuthMiddleware)

# 路由注册
app.include_router(auth_router)


# ==================== 全局异常处理器 ====================
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """业务异常 → 扁平错误响应，与 AuthMiddleware 格式统一"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.error_code,
            "message": exc.error_message,
            "detail": exc.error_detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": "E9003",
            "message": "请求参数校验失败",
            "detail": str(exc.errors()),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "code": "E9001",
            "message": "服务器内部错误",
            "detail": str(exc),
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}
