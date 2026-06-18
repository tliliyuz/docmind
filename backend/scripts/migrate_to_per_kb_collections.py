"""Per-KB Collection 数据迁移脚本

将旧单 collection（docmind）中的数据按 kb_id 迁移到新 Per-KB collection（kb_{kb_id}）。
迁移完成后删除旧 docmind collection。

用法:
    cd backend
    python scripts/migrate_to_per_kb_collections.py
    python scripts/migrate_to_per_kb_collections.py --dry-run    # 仅检查，不实际迁移
    python scripts/migrate_to_per_kb_collections.py --skip-delete  # 迁移后保留旧 collection

前提条件:
    - 应用已停止（避免并发写入冲突）
    - CHROMA_PERSIST_DIR 环境变量或 .env 中的路径正确
"""

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

# 确保 backend 目录在 sys.path 中（支持从项目根目录运行）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import chromadb
from chromadb.api import ClientAPI

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OLD_COLLECTION_NAME = "docmind"
NEW_COLLECTION_PREFIX = "kb_"
PAGE_SIZE = 1000  # 每批读取的向量数


def get_client() -> ClientAPI:
    """创建 ChromaDB PersistentClient"""
    return chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )


def check_old_collection(client: ClientAPI) -> bool:
    """检查旧 docmind collection 是否存在"""
    try:
        client.get_collection(OLD_COLLECTION_NAME)
        return True
    except Exception:
        return False


def read_all_data(client: ClientAPI) -> list[dict]:
    """分页读取旧 docmind collection 的全部数据

    Returns:
        list[dict]: 所有记录的列表，每条包含 {id, embedding, document, metadata}
    """
    collection = client.get_collection(OLD_COLLECTION_NAME)
    total = collection.count()
    logger.info("旧 collection '%s' 共 %d 条向量记录", OLD_COLLECTION_NAME, total)

    if total == 0:
        logger.info("旧 collection 为空，无需迁移")
        return []

    all_records: list[dict] = []
    offset = 0
    while offset < total:
        batch = collection.get(
            limit=PAGE_SIZE,
            offset=offset,
            include=["embeddings", "documents", "metadatas"],
        )
        ids = batch["ids"]
        embeddings = batch["embeddings"] if batch["embeddings"] is not None else []
        documents = batch["documents"] if batch["documents"] is not None else []
        metadatas = batch["metadatas"] if batch["metadatas"] is not None else []

        for i in range(len(ids)):
            record = {
                "id": ids[i],
                "embedding": embeddings[i] if i < len(embeddings) else None,
                "document": documents[i] if i < len(documents) else None,
                "metadata": metadatas[i] if i < len(metadatas) else {},
            }
            all_records.append(record)

        offset += len(ids)
        logger.info("  已读取 %d/%d 条...", min(offset, total), total)

        if len(ids) == 0:
            break

    logger.info("读取完成：共 %d 条记录", len(all_records))
    return all_records


def group_by_kb(records: list[dict]) -> dict[int, list[dict]]:
    """按 kb_id 分组，跳过无 kb_id metadata 的记录"""
    groups: dict[int, list[dict]] = defaultdict(list)
    skipped = 0
    for r in records:
        meta = r["metadata"]
        kb_id = meta.get("kb_id")
        if kb_id is None:
            skipped += 1
            logger.warning("记录 %s 缺少 kb_id metadata，跳过", r["id"])
            continue
        groups[int(kb_id)].append(r)

    if skipped:
        logger.warning("共跳过 %d 条缺少 kb_id 的记录", skipped)

    return dict(groups)


def write_to_new_collections(
    client: ClientAPI,
    groups: dict[int, list[dict]],
    dry_run: bool = False,
) -> dict[int, int]:
    """将分组后的数据批量写入 kb_{kb_id} collection

    Returns:
        dict[int, int]: kb_id → 写入记录数
    """
    written_counts: dict[int, int] = {}

    for kb_id, records in sorted(groups.items()):
        collection_name = f"{NEW_COLLECTION_PREFIX}{kb_id}"
        logger.info(
            "  kb_%d: %d 条记录 %s",
            kb_id, len(records),
            "(DRY RUN — 跳过)" if dry_run else "",
        )

        if dry_run:
            written_counts[kb_id] = len(records)
            continue

        # 按 batch 写入，避免单次 add 数据量过大
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        batch_size = 500
        for start in range(0, len(records), batch_size):
            batch = records[start:start + batch_size]
            collection.add(
                ids=[r["id"] for r in batch],
                embeddings=[r["embedding"] for r in batch],
                documents=[r["document"] for r in batch],
                metadatas=[r["metadata"] for r in batch],
            )
            logger.debug(
                "    kb_%d: 写入 %d-%d/%d",
                kb_id, start + 1, min(start + batch_size, len(records)), len(records),
            )

        written_counts[kb_id] = len(records)

    return written_counts


def verify_migration(
    client: ClientAPI,
    written_counts: dict[int, int],
) -> bool:
    """验证迁移后各 collection 记录数一致"""
    all_ok = True
    for kb_id, expected_count in written_counts.items():
        collection_name = f"{NEW_COLLECTION_PREFIX}{kb_id}"
        try:
            collection = client.get_collection(collection_name)
            actual_count = collection.count()
        except Exception:
            logger.error("验证失败：collection '%s' 不存在！", collection_name)
            all_ok = False
            continue

        if actual_count != expected_count:
            logger.error(
                "验证失败：kb_%d 期望 %d 条，实际 %d 条",
                kb_id, expected_count, actual_count,
            )
            all_ok = False
        else:
            logger.info("验证通过：kb_%d → %d 条", kb_id, actual_count)

    return all_ok


def delete_old_collection(client: ClientAPI) -> None:
    """删除旧 docmind collection"""
    try:
        client.delete_collection(OLD_COLLECTION_NAME)
        logger.info("旧 collection '%s' 已删除", OLD_COLLECTION_NAME)
    except Exception as e:
        logger.warning("旧 collection 删除失败（可能已删除）: %s", e)


def main() -> None:
    global PAGE_SIZE

    parser = argparse.ArgumentParser(
        description="DocMind ChromaDB 迁移：单 collection → Per-KB collection",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅检查并打印迁移计划，不实际写入",
    )
    parser.add_argument(
        "--batch-size", type=int, default=PAGE_SIZE,
        help=f"分页读取大小（默认 {PAGE_SIZE}）",
    )
    parser.add_argument(
        "--skip-delete", action="store_true",
        help="迁移后不删除旧 collection（用于回滚安全期）",
    )
    args = parser.parse_args()

    PAGE_SIZE = args.batch_size

    logger.info("=" * 60)
    logger.info("  DocMind Per-KB Collection 数据迁移")
    logger.info("  ChromaDB 路径: %s", settings.CHROMA_PERSIST_DIR)
    logger.info("  模式: %s", "DRY RUN" if args.dry_run else "实际迁移")
    logger.info("=" * 60)

    # 1. 连接 ChromaDB
    client = get_client()
    logger.info("ChromaDB PersistentClient 已连接")

    # 2. 检查旧 collection 是否存在
    if not check_old_collection(client):
        logger.info(
            "旧 collection '%s' 不存在，无需迁移（可能已迁移或全新安装）",
            OLD_COLLECTION_NAME,
        )
        return

    # 3. 分页读取全部数据
    records = read_all_data(client)
    if not records:
        return

    # 4. 按 kb_id 分组
    groups = group_by_kb(records)
    logger.info("按 kb_id 分组完成：共 %d 个知识库", len(groups))
    for kb_id_num, recs in sorted(groups.items()):
        logger.info("  kb_%d: %d 条", kb_id_num, len(recs))

    # 5. 写入新 collection
    logger.info("开始写入 Per-KB collection...")
    written_counts = write_to_new_collections(client, groups, dry_run=args.dry_run)

    if args.dry_run:
        logger.info(
            "Dry run 完成，未实际写入。共 %d 个 KB，%d 条记录待迁移",
            len(groups), sum(len(r) for r in groups.values()),
        )
        return

    # 6. 验证
    logger.info("验证迁移结果...")
    if not verify_migration(client, written_counts):
        logger.error("迁移验证失败！请检查后重试。旧 collection 未删除。")
        sys.exit(1)

    # 7. 删除旧 collection（除非 --skip-delete）
    if not args.skip_delete:
        delete_old_collection(client)
    else:
        logger.info(
            "--skip-delete：旧 collection '%s' 保留未删除", OLD_COLLECTION_NAME,
        )

    logger.info("=" * 60)
    logger.info(
        "  迁移完成！共 %d 个 KB collection，%d 条记录",
        len(written_counts), sum(written_counts.values()),
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
