# ADR-003: 孤儿会话检测（original_kb_id 备份字段）

**状态**：已采纳（2026-06-13）
**决策者**：开发团队
**关联文档**：API.md §5 / DATABASE.md §2.5

## 上下文

FK `ON DELETE SET NULL` 在 MySQL 层自动将 `conversations.kb_id` 置空，`_enrich_kb_status` 看到 `kb_id=None` 返回 `kb_status=None`，前端 `isKbOrphaned` 永远为 `false`。信息不可逆丢失——无法区分「从未关联 KB」和「KB 已删除」。

## 决策

在 Celery 物理删除 KB **之前**批量备份 `kb_id` → `original_kb_id` 和 `kb.name` → `original_kb_name`，恢复被 FK SET NULL 擦除的历史信息。

`kb_status` 三态：`active`（kb_id 非空+可访问）/ `deleted`（kb_id 为空+original_kb_id 非空）/ `unavailable`（kb_id 非空+权限不足）。

## 理由

- 不改 FK 行为（`ON DELETE SET NULL`），最小化变更范围
- 批量 `UPDATE` 避免 ORM 逐行循环
- 信息恢复后前端可准确提示用户

## 后果

- 新增 `original_kb_id`/`original_kb_name` 两列
- `_delete_kb_async` 新增步骤 3.5：物理删除 KB 前批量备份
