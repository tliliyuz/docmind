import api from './index'

// ==================== Trace 链路追踪 API ====================
// 对齐 API.md §7.5：所有端点需 role=admin

/** GET /api/admin/traces — Trace 列表（分页+筛选）
 * @param {Object} params — { page, page_size, user_id, status, intent_type, response_mode, start_date, end_date, search }
 */
export function getTraceList(params = {}) {
  return api.get('/admin/traces', { params })
}

/** GET /api/admin/traces/{trace_id} — Trace 详情（含各阶段 JSON）
 * @param {string} traceId — Trace ID（UUID）
 */
export function getTraceDetail(traceId) {
  return api.get(`/admin/traces/${traceId}`)
}
