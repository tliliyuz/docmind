"""FastAPI 应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import router as auth_router
from .config import settings
from .middleware.auth_middleware import AuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化 ChromaDB"""
    from .core.chroma_client import init_chroma

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
