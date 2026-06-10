"""FastAPI 应用入口"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversation import router as conversation_router
from app.api.knowledge_base import router as kb_router
from app.api.document import router as doc_router
from app.config import settings
from app.core.chroma_client import init_chroma
from app.core.exceptions import AppException
from app.core.logging_config import get_request_id, setup_logging
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.request_id_middleware import RequestIDMiddleware

logger = logging.getLogger(__name__)


# ==================== 生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化日志 + ChromaDB + 配置安全检查"""
    setup_logging(settings.DEBUG)
    init_chroma()

    # JWT 密钥默认值校验：生产环境使用默认值将拒绝启动
    if settings.JWT_SECRET_KEY == "change-me":
        if settings.DEBUG:
            logger.warning(
                "⚠ JWT_SECRET_KEY 仍为默认值 'change-me'，开发环境继续运行，"
                "生产环境请务必通过 .env 覆盖"
            )
        else:
            raise RuntimeError(
                "JWT_SECRET_KEY 不能为默认值 'change-me'，"
                "请通过 .env 文件设置 JWT_SECRET_KEY"
            )

    logger.info("DocMind 应用启动完成 (DEBUG=%s)", settings.DEBUG)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS — 开发阶段允许前端跨域（最先添加 = 最外层）
# 多个来源用逗号分隔，通过 .env 的 CORS_ORIGINS 覆盖
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID 中间件（最内层，最先处理请求）
app.add_middleware(RequestIDMiddleware)

# JWT 认证中间件
app.add_middleware(AuthMiddleware)

# 路由注册
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(kb_router)
app.include_router(doc_router)
app.include_router(admin_router)


# ==================== 全局异常处理器 ====================

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """业务异常 → 扁平错误响应，与 AuthMiddleware 格式统一"""
    rid = get_request_id()
    logger.info(
        "业务异常: %s %s → %s %s",
        request.method, request.url.path,
        exc.error_code, exc.error_message,
        extra={"error_code": exc.error_code, "status_code": exc.status_code},
    )
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
    rid = get_request_id()
    logger.info(
        "参数校验失败: %s %s",
        request.method, request.url.path,
        extra={"errors": str(exc.errors())},
    )
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
    rid = get_request_id()
    # 结构化日志：记录完整异常信息（含 traceback）
    logger.error(
        "未捕获异常: %s %s → %s",
        request.method, request.url.path, type(exc).__name__,
        exc_info=True,
        extra={"exc_type": type(exc).__name__},
    )
    # 生产环境屏蔽堆栈，开发环境返回完整错误信息
    if settings.DEBUG:
        detail = f"{type(exc).__name__}: {str(exc)}"
    else:
        detail = "请联系管理员"
    return JSONResponse(
        status_code=500,
        content={
            "code": "E9001",
            "message": "服务器内部错误",
            "detail": detail,
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}
