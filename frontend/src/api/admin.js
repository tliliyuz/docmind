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
