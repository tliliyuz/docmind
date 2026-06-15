import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getKnowledgeBases,
  getPublicKnowledgeBases,
  getKnowledgeBase,
  createKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase,
  getDocuments,
  getDocument,
  uploadDocument,
  batchUploadDocuments,
  reprocessDocument,
  deleteDocument,
  getDocumentChunks
} from '@/api/knowledge'

/** 文档终态集合 — 与后端 DocumentStatus.TERMINAL_STATUSES 保持一致 */
export const TERMINAL_STATUSES = [
  'completed',
  'success_with_warnings',
  'partial_failed',
  'failed'
]

/** 文档终态 Set — O(1) 查找优化，由 TERMINAL_STATUSES 派生，消除重复定义 */
export const TERMINAL_STATUSES_SET = new Set(TERMINAL_STATUSES)

/** 判断文档状态是否为终态 */
export function isTerminal(status) {
  return TERMINAL_STATUSES_SET.has(status)
}

/** 根据知识库名称匹配部门色 */
export function getDepartmentStyle(name) {
  const lower = (name || '').toLowerCase()
  if (lower.includes('hr') || lower.includes('人事') || lower.includes('人力')) {
    return { color: 'var(--dm-hr-color)', bg: 'var(--dm-hr-bg)', icon: 'fa-users', dept: 'hr' }
  }
  if (lower.includes('it') || lower.includes('技术') || lower.includes('信息') || lower.includes('开发')) {
    return { color: 'var(--dm-it-color)', bg: 'var(--dm-it-bg)', icon: 'fa-laptop-code', dept: 'it' }
  }
  if (lower.includes('行政') || lower.includes('管理') || lower.includes('admin')) {
    return { color: 'var(--dm-admin-color)', bg: 'var(--dm-admin-bg)', icon: 'fa-building', dept: 'admin' }
  }
  if (lower.includes('业务') || lower.includes('销售') || lower.includes('市场') || lower.includes('biz')) {
    return { color: 'var(--dm-biz-color)', bg: 'var(--dm-biz-bg)', icon: 'fa-chart-line', dept: 'biz' }
  }
  if (lower.includes('财务') || lower.includes('金融') || lower.includes('finance')) {
    return { color: 'var(--dm-finance-color)', bg: 'var(--dm-finance-bg)', icon: 'fa-coins', dept: 'finance' }
  }
  // 默认
  return { color: 'var(--dm-primary)', bg: 'var(--dm-primary-light)', icon: 'fa-folder', dept: 'default' }
}

export const useKnowledgeStore = defineStore('knowledge', () => {
  // ==================== 知识库状态 ====================
  const kbList = ref([])
  const kbLoading = ref(false)
  const kbTotal = ref(0)

  /** 公开知识库列表 */
  const publicKbList = ref([])
  const publicKbLoading = ref(false)
  const publicKbTotal = ref(0)

  const currentKb = ref(null)

  // ==================== 文档状态 ====================
  const docList = ref([])
  const docLoading = ref(false)
  const docTotal = ref(0)

  // ==================== 上传状态 ====================
  const uploading = ref(false)
  const uploadProgress = ref({ percent: 0, speed: 0, eta: '' })

  // ==================== 分块预览状态 ====================
  const chunkList = ref([])
  const chunkLoading = ref(false)
  const chunkTotal = ref(0)

  // ==================== 轮询管理 ====================
  /** @type {Map<string, number>} docUuid → interval timer */
  const pollingTimers = new Map()

  // ==================== 知识库操作 ====================

  /** 获取知识库列表 */
  async function fetchKbList(params = {}) {
    kbLoading.value = true
    try {
      const { data } = await getKnowledgeBases(params)
      kbList.value = data.data.items
      kbTotal.value = data.data.total
    } finally {
      kbLoading.value = false
    }
  }

  /** 获取知识库详情 */
  async function fetchKbDetail(id) {
    const { data } = await getKnowledgeBase(id)
    currentKb.value = data.data
    return currentKb.value
  }

  /** 获取公开知识库列表 */
  async function fetchPublicKbList(params = {}) {
    publicKbLoading.value = true
    try {
      const { data } = await getPublicKnowledgeBases(params)
      publicKbList.value = data.data.items
      publicKbTotal.value = data.data.total
    } finally {
      publicKbLoading.value = false
    }
  }

  /** 创建知识库 */
  async function createKb(kbData) {
    const { data } = await createKnowledgeBase(kbData)
    kbList.value.unshift(data.data)
    kbTotal.value++
    return data.data
  }

  /** 更新知识库 */
  async function updateKb(id, kbData) {
    const { data } = await updateKnowledgeBase(id, kbData)
    // 更新列表中的项
    const idx = kbList.value.findIndex(k => k.uuid === id)
    if (idx !== -1) kbList.value[idx] = data.data
    // 更新当前详情
    if (currentKb.value?.uuid === id) currentKb.value = data.data
    return data.data
  }

  /** 删除知识库 */
  async function deleteKb(id) {
    await deleteKnowledgeBase(id)
    kbList.value = kbList.value.filter(k => k.uuid !== id)
    kbTotal.value--
    if (currentKb.value?.uuid === id) currentKb.value = null
  }

  // ==================== 文档操作 ====================

  /** 获取文档列表 */
  async function fetchDocList(kbId, params = {}) {
    docLoading.value = true
    try {
      const { data } = await getDocuments(kbId, params)
      docList.value = data.data.items
      docTotal.value = data.data.total
    } finally {
      docLoading.value = false
    }
  }

  /** 上传文档 */
  async function uploadDoc(kbId, formData) {
    uploading.value = true
    uploadProgress.value = { percent: 0, speed: 0, eta: '' }
    const startTime = Date.now()

    try {
      const { data } = await uploadDocument(kbId, formData, (progressEvent) => {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        const elapsed = (Date.now() - startTime) / 1000
        const speed = elapsed > 0
          ? (progressEvent.loaded / elapsed / 1024).toFixed(0)
          : 0
        const remaining = speed > 0
          ? ((progressEvent.total - progressEvent.loaded) / (speed * 1024)).toFixed(0)
          : '--'
        uploadProgress.value = {
          percent,
          speed: speed + ' KB/s',
          eta: remaining + 's'
        }
      })
      return data.data
    } finally {
      uploading.value = false
    }
  }

  /** 批量上传文档 */
  async function batchUploadDocs(kbId, formData) {
    uploading.value = true
    uploadProgress.value = { percent: 0, speed: 0, eta: '' }
    const startTime = Date.now()

    try {
      const { data } = await batchUploadDocuments(kbId, formData, (progressEvent) => {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        const elapsed = (Date.now() - startTime) / 1000
        const speed = elapsed > 0
          ? (progressEvent.loaded / elapsed / 1024).toFixed(0)
          : 0
        uploadProgress.value = { percent, speed: speed + ' KB/s', eta: '--' }
      })
      return data.data
    } finally {
      uploading.value = false
    }
  }

  /** 重新处理文档 */
  async function reprocessDoc(kbId, docId) {
    const { data } = await reprocessDocument(kbId, docId)
    // 更新列表中该文档状态
    const doc = docList.value.find(d => d.uuid === docId)
    if (doc) doc.status = data.data.status
    return data.data
  }

  /** 删除文档 */
  async function removeDoc(kbId, docId) {
    await deleteDocument(kbId, docId)
    docList.value = docList.value.filter(d => d.uuid !== docId)
    docTotal.value--
    stopPolling(docId)
  }

  // ==================== 分块操作 ====================

  /** 获取文档分块列表 */
  async function fetchDocChunks(kbId, docId, params = {}) {
    chunkLoading.value = true
    try {
      const { data } = await getDocumentChunks(kbId, docId, params)
      chunkList.value = data.data.items
      chunkTotal.value = data.data.total
      return data.data
    } finally {
      chunkLoading.value = false
    }
  }

  // ==================== 状态轮询 ====================

  /** 轮询文档状态直到终态 */
  function startPolling(kbId, docId) {
    if (pollingTimers.has(docId)) return

    const POLL_INTERVAL = 2000
    const POLL_TIMEOUT = 5 * 60 * 1000
    const startTime = Date.now()

    const timer = setInterval(async () => {
      // 超时保护
      if (Date.now() - startTime > POLL_TIMEOUT) {
        stopPolling(docId)
        return
      }

      try {
        const { data } = await getDocument(kbId, docId)
        const doc = data.data
        // 更新列表中的文档
        const idx = docList.value.findIndex(d => d.uuid === docId)
        if (idx !== -1) docList.value[idx] = doc

        if (isTerminal(doc.status)) {
          stopPolling(docId)
        }
      } catch {
        // 网络错误不中断轮询
      }
    }, POLL_INTERVAL)

    pollingTimers.set(docId, timer)
  }

  /** 停止轮询 */
  function stopPolling(docId) {
    const timer = pollingTimers.get(docId)
    if (timer) {
      clearInterval(timer)
      pollingTimers.delete(docId)
    }
  }

  /** 清理所有轮询 */
  function clearAllPolling() {
    pollingTimers.forEach(timer => clearInterval(timer))
    pollingTimers.clear()
  }

  // ==================== 重置 ====================
  function resetKbState() {
    kbList.value = []
    kbTotal.value = 0
    currentKb.value = null
  }

  function resetDocState() {
    docList.value = []
    docTotal.value = 0
    chunkList.value = []
    chunkTotal.value = 0
    clearAllPolling()
  }

  return {
    // 知识库
    kbList, kbLoading, kbTotal, currentKb,
    publicKbList, publicKbLoading, publicKbTotal,
    fetchKbList, fetchPublicKbList, fetchKbDetail, createKb, updateKb, deleteKb,
    // 文档
    docList, docLoading, docTotal,
    fetchDocList, uploadDoc, batchUploadDocs, reprocessDoc, removeDoc,
    // 上传
    uploading, uploadProgress,
    // 分块
    chunkList, chunkLoading, chunkTotal, fetchDocChunks,
    // 轮询
    startPolling, stopPolling, clearAllPolling,
    // 重置
    resetKbState, resetDocState
  }
})
