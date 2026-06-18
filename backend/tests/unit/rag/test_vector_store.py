"""向量存储抽象层单元测试 — ChromaVectorStore 委托验证（Per-KB Collection）"""

import pytest
from unittest.mock import MagicMock

from app.rag.vector_store import BaseVectorStore, ChromaVectorStore


# ==================== BaseVectorStore ABC ====================


class TestBaseVectorStore:
    """BaseVectorStore 抽象基类 — 验证接口定义"""

    def test_无法直接实例化(self):
        """BaseVectorStore 是 ABC，不能直接实例化"""
        with pytest.raises(TypeError):
            BaseVectorStore()  # type: ignore[abstract]

    def test_子类必须实现抽象方法(self):
        """子类缺少抽象方法时无法实例化"""

        class IncompleteStore(BaseVectorStore):
            pass

        with pytest.raises(TypeError):
            IncompleteStore()  # type: ignore[abstract]

    def test_实现全部方法的子类可实例化(self):
        """实现了 search/add/delete（含 kb_id）的子类可正常实例化"""

        class FullStore(BaseVectorStore):
            async def search(self, query_embeddings, n_results, kb_id, include, where=None):
                return {}

            async def add(self, ids, kb_id, embeddings=None, documents=None, metadatas=None):
                pass

            async def delete(self, kb_id, where=None):
                pass

        store = FullStore()
        assert isinstance(store, BaseVectorStore)


# ==================== ChromaVectorStore ====================


def _make_mock_client(mock_collection=None):
    """构造 mock ClientAPI，get_or_create_collection 返回指定 mock collection"""
    if mock_collection is None:
        mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    return mock_client, mock_collection


class TestChromaVectorStoreSearch:
    """ChromaVectorStore.search — 验证多 collection 路由 + 线程池卸载"""

    @pytest.mark.asyncio
    async def test_search路由到正确的kb_collection(self):
        """search() 通过 kb_id 路由到对应 KB collection 并委托 query"""
        mock_client, mock_collection = _make_mock_client()
        mock_collection.query.return_value = {"ids": [["id1"]], "documents": [["doc1"]]}

        store = ChromaVectorStore(mock_client)
        result = await store.search(
            query_embeddings=[[0.1, 0.2]],
            n_results=10,
            kb_id=1,
            include=["documents", "distances", "metadatas"],
        )

        # 验证通过 client.get_or_create_collection 获取 kb_1 collection
        mock_client.get_or_create_collection.assert_called_once_with(
            name="kb_1", metadata={"hnsw:space": "cosine"},
        )
        # 验证委托给 collection.query
        mock_collection.query.assert_called_once()
        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["query_embeddings"] == [[0.1, 0.2]]
        assert call_kwargs["n_results"] == 10
        assert call_kwargs["where"] is None  # Per-KB：不再需要 where={"kb_id": ...}
        assert "documents" in call_kwargs["include"]
        assert result["ids"] == [["id1"]]

    @pytest.mark.asyncio
    async def test_search传doc级where过滤(self):
        """search() 可传可选的 doc 级 where 过滤（如 {"doc_id": 42}）"""
        mock_client, mock_collection = _make_mock_client()
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]]}

        store = ChromaVectorStore(mock_client)
        await store.search(
            query_embeddings=[[0.1]],
            n_results=5,
            kb_id=1,
            where={"doc_id": 42},
            include=["documents"],
        )

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["where"] == {"doc_id": 42}

    @pytest.mark.asyncio
    async def test_search同一kb复用collection缓存(self):
        """同一 kb_id 多次 search 复用已缓存的 collection，不重复 get_or_create"""
        mock_client, mock_collection = _make_mock_client()
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]]}

        store = ChromaVectorStore(mock_client)
        await store.search(query_embeddings=[[0.1]], n_results=5, kb_id=1, include=["documents"])
        await store.search(query_embeddings=[[0.2]], n_results=5, kb_id=1, include=["documents"])

        # get_or_create_collection 仅调用一次
        assert mock_client.get_or_create_collection.call_count == 1

    @pytest.mark.asyncio
    async def test_search不同kb路由到不同collection(self):
        """不同 kb_id 路由到不同 collection"""
        mock_client = MagicMock()
        mock_col_1 = MagicMock()
        mock_col_1.query.return_value = {"ids": [[]], "documents": [[]]}
        mock_col_2 = MagicMock()
        mock_col_2.query.return_value = {"ids": [[]], "documents": [[]]}
        mock_client.get_or_create_collection.side_effect = [mock_col_1, mock_col_2]

        store = ChromaVectorStore(mock_client)
        await store.search(query_embeddings=[[0.1]], n_results=5, kb_id=1, include=["documents"])
        await store.search(query_embeddings=[[0.2]], n_results=5, kb_id=2, include=["documents"])

        assert mock_client.get_or_create_collection.call_count == 2
        mock_col_1.query.assert_called_once()
        mock_col_2.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_search异常传播(self):
        """ChromaDB 异常应从 search() 传播到调用方"""
        mock_client, mock_collection = _make_mock_client()
        mock_collection.query.side_effect = RuntimeError("ChromaDB 连接失败")

        store = ChromaVectorStore(mock_client)
        with pytest.raises(RuntimeError, match="ChromaDB 连接失败"):
            await store.search(
                query_embeddings=[[0.1]],
                n_results=5,
                kb_id=1,
                include=["documents"],
            )

    @pytest.mark.asyncio
    async def test_search通过线程池执行不阻塞事件循环(self):
        """search() 使用 asyncio.to_thread 卸载到线程池，不阻塞事件循环"""
        import asyncio

        mock_client, mock_collection = _make_mock_client()
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]]}

        store = ChromaVectorStore(mock_client)

        # 启动两个并发 search（不同 kb），验证它们不会互相阻塞
        results = await asyncio.gather(
            store.search(query_embeddings=[[0.1]], n_results=5, kb_id=1, include=["documents"]),
            store.search(query_embeddings=[[0.2]], n_results=5, kb_id=2, include=["documents"]),
        )
        assert len(results) == 2
        assert mock_collection.query.call_count == 2


class TestChromaVectorStoreAdd:
    """ChromaVectorStore.add — 验证委托给对应 KB collection"""

    @pytest.mark.asyncio
    async def test_add委托给正确的kb_collection(self):
        """add() 通过 kb_id 路由到对应 KB collection 并委托 add"""
        mock_client, mock_collection = _make_mock_client()

        store = ChromaVectorStore(mock_client)
        await store.add(
            ids=["id1", "id2"],
            kb_id=1,
            embeddings=[[0.1], [0.2]],
            documents=["doc1", "doc2"],
            metadatas=[{"doc_id": 1}, {"doc_id": 1}],
        )

        mock_client.get_or_create_collection.assert_called_once_with(
            name="kb_1", metadata={"hnsw:space": "cosine"},
        )
        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args[1]
        assert call_kwargs["ids"] == ["id1", "id2"]
        assert call_kwargs["embeddings"] == [[0.1], [0.2]]
        assert call_kwargs["documents"] == ["doc1", "doc2"]

    @pytest.mark.asyncio
    async def test_add异常传播(self):
        """ChromaDB 异常应从 add() 传播到调用方"""
        mock_client, mock_collection = _make_mock_client()
        mock_collection.add.side_effect = RuntimeError("ChromaDB 写入失败")

        store = ChromaVectorStore(mock_client)
        with pytest.raises(RuntimeError, match="ChromaDB 写入失败"):
            await store.add(ids=["id1"], kb_id=1, embeddings=[[0.1]])


class TestChromaVectorStoreDelete:
    """ChromaVectorStore.delete — 验证 doc 级删除 vs KB 级 drop collection"""

    @pytest.mark.asyncio
    async def test_delete带where_委托给collection删除(self):
        """delete(kb_id, where={...}) 在指定 KB collection 中按条件删除"""
        mock_client, mock_collection = _make_mock_client()

        store = ChromaVectorStore(mock_client)
        await store.delete(kb_id=1, where={"doc_id": 42})

        # 验证通过 kb_id 获取 collection 后委托 delete
        mock_client.get_or_create_collection.assert_called_once_with(
            name="kb_1", metadata={"hnsw:space": "cosine"},
        )
        mock_collection.delete.assert_called_once_with(where={"doc_id": 42})

    @pytest.mark.asyncio
    async def test_delete不带where_删除整个kb_collection(self):
        """delete(kb_id, where=None) 直接删除整个 KB collection（O(1)）"""
        mock_client = MagicMock()
        store = ChromaVectorStore(mock_client)
        # 预填充缓存
        store._collections[1] = MagicMock()

        await store.delete(kb_id=1)  # where=None

        mock_client.delete_collection.assert_called_once_with(name="kb_1")
        # 验证缓存已清理
        assert 1 not in store._collections

    @pytest.mark.asyncio
    async def test_delete_collection不存在时静默忽略(self):
        """delete_collection 失败时不抛异常（collection 可能已被删除）"""
        mock_client = MagicMock()
        mock_client.delete_collection.side_effect = RuntimeError("not found")
        store = ChromaVectorStore(mock_client)

        # 不应抛出异常
        await store.delete(kb_id=1)  # where=None

        mock_client.delete_collection.assert_called_once_with(name="kb_1")

    @pytest.mark.asyncio
    async def test_delete异常传播(self):
        """delete(kb_id, where={...}) 时 ChromaDB 异常应传播"""
        mock_client, mock_collection = _make_mock_client()
        mock_collection.delete.side_effect = RuntimeError("ChromaDB 删除失败")

        store = ChromaVectorStore(mock_client)
        with pytest.raises(RuntimeError, match="ChromaDB 删除失败"):
            await store.delete(kb_id=1, where={"doc_id": 42})
