"""ChromaDB 连接管理 — PersistentClient + docmind collection

单 collection 策略：所有知识库共用 `docmind` collection，通过 metadata 中的 kb_id 隔离。
"""

import chromadb
from chromadb.api import ClientAPI, Collection

from app.config import settings
from app.rag.vector_store import BaseVectorStore, ChromaVectorStore

_client: ClientAPI | None = None
_collection: Collection | None = None
_vector_store: ChromaVectorStore | None = None


def init_chroma() -> Collection:
    """初始化 ChromaDB PersistentClient，获取或创建 docmind collection。
    应用启动时调用一次。
    """
    global _client, _collection

    _client = chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name="docmind",
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def get_collection() -> Collection:
    """获取 docmind collection。未初始化时自动初始化。

    新代码推荐使用 get_vector_store() 获取抽象接口。
    """
    global _collection, _client
    if _collection is None:
        init_chroma()
    return _collection


def get_client() -> ClientAPI:
    """获取 ChromaDB PersistentClient。未初始化时自动初始化。"""
    global _client, _collection
    if _client is None:
        init_chroma()
    return _client


def get_vector_store() -> BaseVectorStore:
    """获取向量存储抽象单例（推荐给新代码使用）。

    返回 ChromaVectorStore 实例，封装 ChromaDB Collection 操作，
    所有方法均为 async，通过 asyncio.to_thread() 卸载同步调用。
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = ChromaVectorStore(get_collection())
    return _vector_store
