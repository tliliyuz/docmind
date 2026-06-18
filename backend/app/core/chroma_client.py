"""ChromaDB 连接管理 — PersistentClient + Per-KB Collection 策略

Decision #29：每个知识库独立 collection（`kb_{kb_id}`），查询无需 where filter，
消除 metadata filter 的性能瓶颈（16s → 35ms）。
"""

import chromadb
from chromadb.api import ClientAPI

from app.config import settings
from app.rag.vector_store import BaseVectorStore, ChromaVectorStore

_client: ClientAPI | None = None
_vector_store: ChromaVectorStore | None = None


def init_chroma() -> ClientAPI:
    """初始化 ChromaDB PersistentClient。

    仅创建客户端连接，不预创建 collection（Per-KB collection 在首次访问时懒加载）。
    应用启动时调用一次。
    """
    global _client

    _client = chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )
    return _client


def get_client() -> ClientAPI:
    """获取 ChromaDB PersistentClient。未初始化时自动初始化。"""
    global _client
    if _client is None:
        init_chroma()
    return _client


def get_vector_store() -> BaseVectorStore:
    """获取向量存储抽象单例（推荐给新代码使用）。

    返回 ChromaVectorStore 实例，内部管理多个 KB collection，
    所有方法均为 async，通过 asyncio.to_thread() 卸载同步调用。
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = ChromaVectorStore(get_client())
    return _vector_store
