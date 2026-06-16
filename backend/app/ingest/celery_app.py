"""Celery 应用配置 — broker/backend 从 settings 读取"""

import asyncio
import sys

from celery import Celery
from app.core.chroma_client import init_chroma
from app.config import settings
# Worker 启动时初始化 ChromaDB（独立进程，不走 FastAPI lifespan）
from celery.signals import worker_process_init

# Windows 下 aiomysql 需要 SelectorEventLoop，Proactor 会卡死
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

celery_app = Celery(
    "docmind",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    # 入库任务耗时较长，放宽超时
    task_soft_time_limit=600,
    task_time_limit=900,
)

# Windows: solo 池（默认），避免 eventlet/gevent 与 asyncio 冲突
if sys.platform == "win32":
    celery_app.conf.update(
        worker_pool="solo",
    )


@worker_process_init.connect
def _init_worker_resources(**kwargs):
    init_chroma()


# 注册任务模块（导入即注册 @celery_app.task 装饰的任务）
import app.ingest.tasks  # noqa: E402, F401
import app.ingest.delete_tasks  # noqa: E402, F401
