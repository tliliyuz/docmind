/**
 * 会话管理 API
 *
 * 对齐 API.md §5 会话接口：
 * - GET    /conversations          会话列表（分页）
 * - GET    /conversations/{id}     会话详情（含消息历史）
 * - PUT    /conversations/{id}     重命名会话
 * - DELETE /conversations/{id}     删除会话
 */

import api from './index'

/**
 * 获取会话列表（分页，按 updated_at DESC）
 * @param {number} page - 页码，默认 1
 * @param {number} pageSize - 每页条数，默认 20
 */
export function fetchConversations(page = 1, pageSize = 20) {
  return api.get('/conversations', { params: { page, page_size: pageSize } })
}

/**
 * 获取会话详情（含消息历史）
 * @param {string} id - 会话 UUID
 */
export function fetchConversationDetail(id) {
  return api.get(`/conversations/${id}`)
}

/**
 * 重命名会话
 * @param {string} id - 会话 UUID
 * @param {string} title - 新标题
 */
export function renameConversation(id, title) {
  return api.put(`/conversations/${id}`, { title })
}

/**
 * 删除会话（硬删除，含全部消息）
 * @param {string} id - 会话 UUID
 */
export function deleteConversation(id) {
  return api.delete(`/conversations/${id}`)
}
