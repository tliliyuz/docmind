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
    JWT_EXPIRE_MINUTES: int = 1440  #当前access_token过期时间

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

    # ── Token Budget（四池子分拆，对齐 ARCHITECTURE.md §8.1）──
    MAX_CONTEXT_TOKENS: int = 20000
    SYSTEM_BUDGET: int = 2000
    HISTORY_BUDGET: int = 6000
    RETRIEVAL_BUDGET: int = 10000
    QUESTION_BUDGET: int = 2000
    HISTORY_MAX_MESSAGES: int = 20

    # ── Chunking ──
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150

    # ── Retrieval ──
    VECTOR_TOP_K: int = 10
    BM25_TOP_K: int = 10
    BM25_MIN_SCORE: float = -5.0
    BM25_CACHE_TTL: int = 300

    # ── RRF ──
    RRF_K: int = 60

    # ── Reranker ──
    RERANK_TOP_K: int = 5

    # ── Prompt ──
    PROMPT_MAX_CHUNKS: int = 5
    PROMPT_MAX_CONTEXT_TOKENS: int = 3000

    # ── Embedding ──
    EMBED_MAX_RETRIES: int = 5
    EMBED_BASE_DELAY: int = 1

    # ── Idempotency ──
    IDEMPOTENCY_LOCK_TTL: int = 600

    # ── Parsing ──
    PARSE_FAILURE_PARTIAL: float = 0.2
    PARSE_FAILURE_FAILED: float = 0.5

    # ── SSE ──
    SSE_HEARTBEAT_INTERVAL: int = 15

    # ── Document ──
    CHUNK_PREVIEW_LENGTH: int = 200

    @property
    def mysql_url(self) -> str:
        """构造异步 MySQL 连接串"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )


settings = Settings()
