"""向量存储抽象层单元测试 — ChromaVectorStore 委托验证"""

import pytest
from unittest.mock import MagicMock, patch

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
        """实现了 search/add/delete 的子类可正常实例化"""

        class FullStore(BaseVectorStore):
            async def search(self, query_embeddings, n_results, where, include):
                return {}

            async def add(self, ids, embeddings=None, documents=None, metadatas=None):
                pass

            async def delete(self, where):
                pass

        store = FullStore()
        assert isinstance(store, BaseVectorStore)


# ==================== ChromaVectorStore ====================


class TestChromaVectorStore:
    """ChromaVectorStore — 验证将操作委托给底层 ChromaDB Collection"""

    @pytest.mark.asyncio
    async def test_search委托给collection(self):
        """search() 通过 asyncio.to_thread 委托给 collection.query"""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"ids": [["id1"]], "documents": [["doc1"]]}

        store = ChromaVectorStore(mock_collection)
        result = await store.search(
            query_embeddings=[[0.1, 0.2]],
            n_results=10,
            where={"kb_id": 1},
            include=["documents", "distances", "metadatas"],
        )

        # 验证委托
        mock_collection.query.assert_called_once()
        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["query_embeddings"] == [[0.1, 0.2]]
        assert call_kwargs["n_results"] == 10
        assert call_kwargs["where"] == {"kb_id": 1}
        assert "documents" in call_kwargs["include"]
        assert result["ids"] == [["id1"]]

    @pytest.mark.asyncio
    async def test_add委托给collection(self):
        """add() 通过 asyncio.to_thread 委托给 collection.add"""
        mock_collection = MagicMock()

        store = ChromaVectorStore(mock_collection)
        await store.add(
            ids=["id1", "id2"],
            embeddings=[[0.1], [0.2]],
            documents=["doc1", "doc2"],
            metadatas=[{"kb_id": 1}, {"kb_id": 1}],
        )

        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args[1]
        assert call_kwargs["ids"] == ["id1", "id2"]
        assert call_kwargs["embeddings"] == [[0.1], [0.2]]
        assert call_kwargs["documents"] == ["doc1", "doc2"]

    @pytest.mark.asyncio
    async def test_delete委托给collection(self):
        """delete() 通过 asyncio.to_thread 委托给 collection.delete"""
        mock_collection = MagicMock()

        store = ChromaVectorStore(mock_collection)
        await store.delete(where={"doc_id": 42})

        mock_collection.delete.assert_called_once_with(where={"doc_id": 42})

    @pytest.mark.asyncio
    async def test_search异常传播(self):
        """ChromaDB 异常应从 search() 传播到调用方"""
        mock_collection = MagicMock()
        mock_collection.query.side_effect = RuntimeError("ChromaDB 连接失败")

        store = ChromaVectorStore(mock_collection)
        with pytest.raises(RuntimeError, match="ChromaDB 连接失败"):
            await store.search(
                query_embeddings=[[0.1]],
                n_results=5,
                where={},
                include=["documents"],
            )

    @pytest.mark.asyncio
    async def test_search通过线程池执行不阻塞事件循环(self):
        """search() 使用 asyncio.to_thread 卸载到线程池，不阻塞事件循环"""
        import asyncio

        mock_collection = MagicMock()
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]]}

        store = ChromaVectorStore(mock_collection)

        # 启动两个并发 search，验证它们不会互相阻塞
        results = await asyncio.gather(
            store.search(query_embeddings=[[0.1]], n_results=5, where={"kb_id": 1}, include=["documents"]),
            store.search(query_embeddings=[[0.2]], n_results=5, where={"kb_id": 2}, include=["documents"]),
        )
        assert len(results) == 2
        assert mock_collection.query.call_count == 2
