"""ChromaDB 连接管理 — PersistentClient + docmind collection

单 collection 策略：所有知识库共用 `docmind` collection，通过 metadata 中的 kb_id 隔离。
"""

import chromadb
from chromadb.api import ClientAPI, Collection

from app.config import settings

_client: ClientAPI | None = None
_collection: Collection | None = None


def init_chroma() -> Collection:
    """初始化 ChromaDB PersistentClient，获取或创建 docmind collection。
    应用启动时调用一次。
    """
    global _client, _collection

    _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    _collection = _client.get_or_create_collection(
        name="docmind",
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def get_collection() -> Collection:
    """获取 docmind collection。未初始化时抛异常。"""
    if _collection is None:
        raise RuntimeError("ChromaDB 未初始化，请先调用 init_chroma()")
    return _collection


def get_client() -> ClientAPI:
    """获取 ChromaDB PersistentClient。未初始化时抛异常。"""
    if _client is None:
        raise RuntimeError("ChromaDB 未初始化，请先调用 init_chroma()")
    return _client
