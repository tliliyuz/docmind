import api from './index'

// ==================== 知识库 CRUD ====================

/** 获取当前用户的知识库列表 */
export function getKnowledgeBases(params = {}) {
  return api.get('/knowledge-bases', { params })
}

/** 获取公开知识库列表（跨用户，仅 public+active） */
export function getPublicKnowledgeBases(params = {}) {
  return api.get('/knowledge-bases/public', { params })
}

/** 获取知识库详情 */
export function getKnowledgeBase(id) {
  return api.get(`/knowledge-bases/${id}`)
}

/** 创建知识库 */
export function createKnowledgeBase(data) {
  return api.post('/knowledge-bases', data)
}

/** 更新知识库 */
export function updateKnowledgeBase(id, data) {
  return api.put(`/knowledge-bases/${id}`, data)
}

/** 删除知识库（异步，返回 202） */
export function deleteKnowledgeBase(id) {
  return api.delete(`/knowledge-bases/${id}`)
}

// ==================== 文档管理 ====================

/** 获取知识库下的文档列表 */
export function getDocuments(kbId, params = {}) {
  return api.get(`/knowledge-bases/${kbId}/documents`, { params })
}

/** 获取单个文档详情 */
export function getDocument(kbId, docId) {
  return api.get(`/knowledge-bases/${kbId}/documents/${docId}`)
}

/** 上传文档 */
export function uploadDocument(kbId, formData, onUploadProgress) {
  return api.post(`/knowledge-bases/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress
  })
}

/** 批量上传文档 */
export function batchUploadDocuments(kbId, formData, onUploadProgress) {
  return api.post(`/knowledge-bases/${kbId}/documents/batch-upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress
  })
}

/** 重新处理文档 */
export function reprocessDocument(kbId, docId) {
  return api.post(`/knowledge-bases/${kbId}/documents/${docId}/reprocess`)
}

/** 删除文档（异步清理） */
export function deleteDocument(kbId, docId) {
  return api.delete(`/knowledge-bases/${kbId}/documents/${docId}`)
}

/** 获取文档分块列表 */
export function getDocumentChunks(kbId, docId, params = {}) {
  return api.get(`/knowledge-bases/${kbId}/documents/${docId}/chunks`, { params })
}
