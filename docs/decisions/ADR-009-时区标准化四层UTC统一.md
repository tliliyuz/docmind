# ADR-009: 时区标准化——四层 UTC 统一

**状态**：已采纳（2026-06-09）
**决策者**：开发团队
**关联文档**：ARCHITECTURE.md §11 / DATABASE.md §0 / DEVELOPMENT.md §7 / CLAUDE.md

## 上下文

MySQL DATETIME 列不存储时区，PyMySQL/aiomysql 驱动返回 naive datetime → Pydantic 序列化无时区后缀 → 前端 `new Date()` 当成本地时间，偏差 8 小时。

## 方案演进

| 尝试 | 方案 | 结果 |
|:---|:---|:---|
| v1 | `DateTime(timezone=True)` | ❌ 对 PyMySQL/aiomysql 驱动不生效 |
| v2 | Pydantic `PlainSerializer` 强制补 `Z` | ⚠️ 表现层补丁，Pydantic 感知识别 |
| v3（最终） | `UTCDateTime` TypeDecorator | ✅ 数据层修复，ORM→Pydantic→API 全链路透明 |

## 决策

四层 UTC 统一：
1. **数据库**：MySQL 连接串 `init_command=SET time_zone='%2B00:00'`；ORM `UTCDateTime` TypeDecorator
2. **后端**：禁止 `datetime.utcnow()`，统一 `datetime.now(timezone.utc)`
3. **API**：Pydantic 序列化 aware datetime 自动输出 ISO 8601 + `+00:00`
4. **前端**：`new Date(isoString)` 自动转换为本地时区显示

## 理由

- 数据层修复优于表现层补丁
- TypeDecorator 对 Pydantic 透明，零侵入
- 四层约定写入 CLAUDE.md，后续开发自动遵守

## 后果

- 所有 ORM DateTime 列改为 `UTCDateTime`
- 7 个模型文件受影响
