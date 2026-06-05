"""应用配置 — 字段声明与 .env 变量自动映射，提供类型校验和 IDE 补全"""

from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    """pydantic-settings 自动从 CWD 读取 .env，将变量名匹配到以下字段。
    这里声明的值仅作「默认值」，.env 中存在同名变量时会被覆盖。"""
    model_config = {
        "env_file": Path(__file__).parent.parent / ".env",  # 相对 config.py 定位
        "env_file_encoding": "utf-8",
    }

    # 应用
    APP_NAME: str = "DocMind"
    DEBUG: bool = True

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "docmind"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CHROMA_BATCH_SIZE: int = 100

    # Embedding
    EMBED_BATCH_SIZE: int = 10  # DashScope text-embedding-v3 单次上限 10 条
    DEBUG_CHUNK_FULL: bool = False

    # LLM (OpenAI 兼容)
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-v4-pro"

    # Embedding
    EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v3"

    # Rerank (可选)
    RERANK_API_KEY: str = ""

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    UPLOAD_MAX_SIZE: int = 52428800  # 50MB，单位字节
    ALLOWED_EXTENSIONS: str = "pdf,docx,md,txt"  # 逗号分隔，可通过 .env 覆盖

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"  # 逗号分隔多个来源

    @property
    def mysql_url(self) -> str:
        """构造异步 MySQL 连接串"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )


settings = Settings()
