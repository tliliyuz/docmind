# ADR-005: KB/文档删除策略——物理删除 + FK CASCADE

**状态**：已采纳（2026-05-15）
**决策者**：开发团队
**关联文档**：API.md §3§4 / DATABASE.md §4 / ARCHITECTURE.md §4.5§7.1

## 上下文

KB 删除流程存在设计矛盾：API.md 写了「批量删除 chunks/documents/kb 记录」，但紧接着标记 `status=deleted`——物理删除后行已不存在，无法 UPDATE。同时 `ON DELETE CASCADE` 外键成为死代码。

## 决策

方案 B：Celery 异步物理删除 + FK CASCADE 兜底。

核心流程（KB 级）：
```
DELETE /api/knowledge-bases/{id}
→ kb.status = deleting → 返回 202
→ Celery Worker:
  1. collection.delete(where={"kb_id": kb_id})   — ChromaDB
  2. 删除 uploads/{kb_id}/                           — 磁盘文件
  3. DELETE FROM knowledge_bases WHERE id=?          — MySQL 物理删除
     └─ FK CASCADE → documents → chunks（兜底）
```

文档级同理。

## 理由

- 消除软删除与 FK CASCADE 的矛盾
- `deleting` 状态仅作为中间态（客户端 → 202），不持久化为终态
- 数据库层 FK CASCADE 确保清理完整性，即使 Celery 步骤部分失败

## 后果

- `DocumentStatus` 枚举移除 `DELETED`，`TERMINAL_STATUSES` 移除 `'deleted'`
- SQLAlchemy `relationship()` 必须加 `passive_deletes=True`
- Celery 任务分发前必须 `await db.commit()`
