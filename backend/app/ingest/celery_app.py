"""Celery 应用配置 — broker/backend 从 settings 读取"""

from celery import Celery

from app.config import settings

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

# 注册任务模块（导入即注册 @celery_app.task 装饰的任务）
import app.ingest.tasks  # noqa: E402, F401
