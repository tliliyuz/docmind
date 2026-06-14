# ADR-015: Admin 角色变更端点移除

**状态**：已采纳（2026-06-13）
**决策者**：开发团队
**关联文档**：API.md §7 / ARCHITECTURE.md §9b

## 上下文

Admin 用户管理接口设计了 `PUT /api/admin/users/{user_id}/role` 端点，用于变更用户角色。

## 决策

v1 MVP 不提供 admin 直接变更用户角色的功能。删除该端点及相关 Service/Schema。

## 理由

- 角色变更为敏感操作，需配合审计日志（`user_operations` 表，v2）方可安全实现
- 无审计日志的角色变更是合规风险
- 当前无业务场景需要 admin 批量调整角色

## 后果

- 删除 `update_admin_user_role` 路由、`AdminUserRoleRequest` Schema、`change_user_role` Service 函数
- 前端移除「变更角色」按钮和交互
