# ADR-001: 外部资源 UUID 化

**状态**：已采纳（2026-06-13）
**决策者**：开发团队
**关联文档**：ARCHITECTURE.md §8.11 / API.md §7 / DATABASE.md §2

## 上下文

外部 API 暴露数据库自增 `id`（如 `/api/knowledge-bases/1`），存在信息泄露风险（可推测数据量）且不符合 RESTful 资源标识最佳实践。

## 决策

采用**双字段方案**：保留 `id BIGINT AUTO_INCREMENT` 作为内部主键，新增 `uuid CHAR(36) UNIQUE` 作为外部暴露标识。

改造范围：Knowledge Base、Document、Conversation 三个外部资源。Trace 移除响应中的自增 id。

不改造资源：User（Admin 内部使用）、Message（仅 SSE 返回）、Chunk（内部结构）。

## 理由

1. 内部主键保持整数，确保 JOIN/索引性能不受 UUID 影响
2. API 边界 UUID↔ID 转换集中在 `uuid_helpers.py`，业务层代码零改动
3. ChromaDB 内部继续使用 integer `kb_id`/`doc_id`，向量库不受影响
4. 迁移脚本幂等化（`_column_exists()`/`_constraint_exists()`），支持部分执行后重跑

## 后果

- 所有外部 API 路径从 `{id}` 改为 `{uuid}`，前端需同步更新
- 新增 `resolve_uuid_to_id()` 依赖注入层，每个端点一次查询开销可忽略
