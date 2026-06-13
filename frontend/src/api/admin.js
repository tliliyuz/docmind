import api from './index'

// ==================== 管理后台 API ====================
// 对齐 API.md §7：所有端点需 role=admin，非 admin 返回 403 E5005

/** GET /api/admin/stats — 系统全局统计 */
export function getAdminStats() {
  return api.get('/admin/stats')
}

/** GET /api/admin/knowledge-bases — 全部知识库列表（跨用户管理视图）
 * @param {Object} params — { page, page_size, user_id, status, visibility, search }
 */
export function getAdminKnowledgeBases(params = {}) {
  return api.get('/admin/knowledge-bases', { params })
}

/** GET /api/admin/documents — 全部文档列表（跨知识库视图）
 * @param {Object} params — { kb_id, page, page_size, status, filename, sort_by, order }
 */
export function getAdminDocuments(params = {}) {
  return api.get('/admin/documents', { params })
}

/** GET /api/admin/stats/traces — Trace 统计数据（ECharts 图表数据源）
 * @param {Object} params — { days, group_by }
 * @returns {Object} { trend, latency, tokens, intent_distribution, response_distribution }
 */
export function getTraceStats(params = {}) {
  return api.get('/admin/stats/traces', { params })
}

// ==================== 用户管理 API — 对齐 API.md §7.7 ====================

/** GET /api/admin/users — 用户列表（分页+筛选）
 * @param {Object} params — { page, page_size, role, status, search }
 */
export function getAdminUsers(params = {}) {
  return api.get('/admin/users', { params })
}

/** GET /api/admin/users/{userId} — 用户详情（含统计+Token 聚合）
 * @param {number} userId
 */
export function getAdminUserDetail(userId) {
  return api.get(`/admin/users/${userId}`)
}

/** PUT /api/admin/users/{userId}/status — 禁用/启用用户
 * @param {number} userId
 * @param {string} status — "active" | "disabled"
 */
export function changeUserStatus(userId, status) {
  return api.put(`/admin/users/${userId}/status`, { status })
}

/** POST /api/admin/users/{userId}/reset-password — 重置用户密码
 * @param {number} userId
 * @param {string} newPassword
 */
export function resetUserPassword(userId, newPassword) {
  return api.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword })
}
