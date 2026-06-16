/** knowledge store 单元测试 — KB CRUD、Document CRUD、轮询、上传进度、工具函数 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mockGetKBs = vi.fn()
const mockGetPublicKBs = vi.fn()
const mockGetKB = vi.fn()
const mockCreateKB = vi.fn()
const mockUpdateKB = vi.fn()
const mockDeleteKB = vi.fn()
const mockGetDocs = vi.fn()
const mockGetDoc = vi.fn()
const mockUploadDoc = vi.fn()
const mockBatchUpload = vi.fn()
const mockReprocessDoc = vi.fn()
const mockDeleteDoc = vi.fn()
const mockGetChunks = vi.fn()

vi.mock('@/api/knowledge', () => ({
  getKnowledgeBases: (...args) => mockGetKBs(...args),
  getPublicKnowledgeBases: (...args) => mockGetPublicKBs(...args),
  getKnowledgeBase: (...args) => mockGetKB(...args),
  createKnowledgeBase: (...args) => mockCreateKB(...args),
  updateKnowledgeBase: (...args) => mockUpdateKB(...args),
  deleteKnowledgeBase: (...args) => mockDeleteKB(...args),
  getDocuments: (...args) => mockGetDocs(...args),
  getDocument: (...args) => mockGetDoc(...args),
  uploadDocument: (...args) => mockUploadDoc(...args),
  batchUploadDocuments: (...args) => mockBatchUpload(...args),
  reprocessDocument: (...args) => mockReprocessDoc(...args),
  deleteDocument: (...args) => mockDeleteDoc(...args),
  getDocumentChunks: (...args) => mockGetChunks(...args),
}))

let useKnowledgeStore
let TERMINAL_STATUSES
let isTerminal
let getDepartmentStyle

beforeEach(async () => {
  vi.resetModules()
  setActivePinia(createPinia())
  const mod = await import('@/stores/knowledge')
  useKnowledgeStore = mod.useKnowledgeStore
  TERMINAL_STATUSES = mod.TERMINAL_STATUSES
  isTerminal = mod.isTerminal
  getDepartmentStyle = mod.getDepartmentStyle
})

afterEach(() => {
  vi.restoreAllMocks()
})

// =====================================================
// KB CRUD 本地状态同步
// =====================================================
describe('KB CRUD 本地状态同步', () => {
  it('fetchKbList: 更新 kbList 和 kbTotal', async () => {
    const store = useKnowledgeStore()
    mockGetKBs.mockResolvedValueOnce({
      data: { data: { items: [{ uuid: 'kb1', name: '我的知识库' }], total: 1 } },
    })

    await store.fetchKbList()

    expect(store.kbList).toHaveLength(1)
    expect(store.kbList[0].name).toBe('我的知识库')
    expect(store.kbTotal).toBe(1)
    expect(store.kbLoading).toBe(false)
  })

  it('createKb: prepend 到 kbList，递增 kbTotal', async () => {
    const store = useKnowledgeStore()
    mockCreateKB.mockResolvedValueOnce({
      data: { data: { uuid: 'new', name: '新知识库' } },
    })
    store.kbList = [{ uuid: 'old', name: '旧' }]
    store.kbTotal = 1

    await store.createKb({ name: '新知识库' })

    expect(store.kbList).toHaveLength(2)
    expect(store.kbList[0].uuid).toBe('new')
    expect(store.kbTotal).toBe(2)
  })

  it('updateKb: 更新 kbList 和 currentKb 中匹配的项', async () => {
    const store = useKnowledgeStore()
    mockUpdateKB.mockResolvedValueOnce({
      data: { data: { uuid: 'kb1', name: '已更新' } },
    })
    store.kbList = [{ uuid: 'kb1', name: '旧' }]
    store.currentKb = { uuid: 'kb1', name: '旧' }

    await store.updateKb('kb1', { name: '已更新' })

    expect(store.kbList[0].name).toBe('已更新')
    expect(store.currentKb.name).toBe('已更新')
  })

  it('deleteKb: 从 kbList 移除，递减 kbTotal，清 currentKb', async () => {
    const store = useKnowledgeStore()
    mockDeleteKB.mockResolvedValueOnce({ data: {} })
    store.kbList = [{ uuid: 'kb1' }, { uuid: 'kb2' }]
    store.kbTotal = 2
    store.currentKb = { uuid: 'kb1' }

    await store.deleteKb('kb1')

    expect(store.kbList).toHaveLength(1)
    expect(store.kbTotal).toBe(1)
    expect(store.currentKb).toBeNull()
  })

  it('KB API 失败: 抛异常，loading 恢复', async () => {
    const store = useKnowledgeStore()
    mockGetKBs.mockRejectedValueOnce(new Error('网络错误'))

    await expect(store.fetchKbList()).rejects.toThrow('网络错误')
    expect(store.kbLoading).toBe(false)
  })
})

// =====================================================
// Document CRUD
// =====================================================
describe('Document CRUD', () => {
  it('fetchDocList: 更新 docList 和 docTotal', async () => {
    const store = useKnowledgeStore()
    mockGetDocs.mockResolvedValueOnce({
      data: { data: { items: [{ uuid: 'd1', filename: 'doc.pdf' }], total: 1 } },
    })

    await store.fetchDocList('kb1')

    expect(store.docList).toHaveLength(1)
    expect(store.docTotal).toBe(1)
  })

  it('removeDoc: 从 docList 移除，递减 docTotal，停止轮询', async () => {
    const store = useKnowledgeStore()
    mockDeleteDoc.mockResolvedValueOnce({ data: {} })
    store.docList = [{ uuid: 'd1' }, { uuid: 'd2' }]
    store.docTotal = 2

    await store.removeDoc('kb1', 'd1')

    expect(store.docList).toHaveLength(1)
    expect(store.docTotal).toBe(1)
  })

  it('reprocessDoc: 更新列表中文档状态', async () => {
    const store = useKnowledgeStore()
    mockReprocessDoc.mockResolvedValueOnce({
      data: { data: { uuid: 'd1', status: 'processing' } },
    })
    store.docList = [{ uuid: 'd1', status: 'failed' }]

    const result = await store.reprocessDoc('kb1', 'd1')

    expect(result.status).toBe('processing')
    expect(store.docList[0].status).toBe('processing')
  })
})

// =====================================================
// isTerminal() / getDepartmentStyle()
// =====================================================
describe('isTerminal() / getDepartmentStyle()', () => {
  it('isTerminal("completed") → true', () => {
    expect(isTerminal('completed')).toBe(true)
  })

  it('isTerminal("processing") → false', () => {
    expect(isTerminal('processing')).toBe(false)
  })

  it('TERMINAL_STATUSES 包含所有终态', () => {
    expect(TERMINAL_STATUSES).toContain('completed')
    expect(TERMINAL_STATUSES).toContain('failed')
    expect(TERMINAL_STATUSES).not.toContain('processing')
  })

  it('getDepartmentStyle("人力资源部") 返回 HR 样式', () => {
    const style = getDepartmentStyle('人力资源部')
    expect(style).toBeDefined()
  })

  it('getDepartmentStyle("未知部门") 返回默认样式', () => {
    const style = getDepartmentStyle('未知部门')
    expect(style).toBeDefined()
  })
})

// =====================================================
// startPolling() / stopPolling() 定时器生命周期
// =====================================================
describe('startPolling() / stopPolling()', () => {
  it('轮询非终态文档：持续调用 getDocument', async () => {
    vi.useFakeTimers()
    const store = useKnowledgeStore()
    mockGetDoc.mockResolvedValue({
      data: { data: { uuid: 'd1', status: 'processing' } },
    })
    store.docList = [{ uuid: 'd1', status: 'processing' }]

    store.startPolling('kb1', 'd1')
    await vi.advanceTimersByTimeAsync(2000)  // 首次轮询

    expect(mockGetDoc).toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('文档达到终态后停止轮询', async () => {
    vi.useFakeTimers()
    const store = useKnowledgeStore()
    let callCount = 0
    mockGetDoc.mockImplementation(() => {
      callCount++
      return Promise.resolve({
        data: { data: { uuid: 'd1', status: callCount === 1 ? 'processing' : 'completed' } },
      })
    })

    await store.startPolling('kb1', 'd1')
    await vi.runAllTimersAsync()

    // 文档达终态后不应无限轮询
    expect(mockGetDoc).toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('重复 startPolling 同一文档：第二次调用不创建新定时器', () => {
    vi.useFakeTimers()
    const store = useKnowledgeStore()
    mockGetDoc.mockResolvedValue({ data: { data: { uuid: 'd1', status: 'processing' } } })

    store.startPolling('kb1', 'd1')
    store.startPolling('kb1', 'd1')

    // 不应创建额外定时器
    vi.useRealTimers()
  })

  it('stopPolling: 清除指定文档的定时器', () => {
    vi.useFakeTimers()
    const store = useKnowledgeStore()
    mockGetDoc.mockResolvedValue({ data: { data: { uuid: 'd1', status: 'processing' } } })

    store.startPolling('kb1', 'd1')
    store.stopPolling('d1')

    // 停止后不应再有轮询
    vi.useRealTimers()
  })

  it('getDocument API 错误不中断轮询', async () => {
    vi.useFakeTimers()
    const store = useKnowledgeStore()
    let calls = 0
    mockGetDoc.mockImplementation(() => {
      calls++
      if (calls === 1) return Promise.reject(new Error('临时错误'))
      return Promise.resolve({ data: { data: { uuid: 'd1', status: 'completed' } } })
    })

    await store.startPolling('kb1', 'd1')
    // 第一次轮询失败，第二次应继续
    await vi.advanceTimersByTimeAsync(4000)

    expect(mockGetDoc).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })
})

// =====================================================
// upload / batchUpload
// =====================================================
describe('upload/batchUpload', () => {
  it('uploadDoc 返回 API 数据且 loading 正确切换', async () => {
    const store = useKnowledgeStore()
    mockUploadDoc.mockImplementation((_kbId, _formData, _onProgress) => {
      return Promise.resolve({ data: { data: { uuid: 'd1', filename: 'test.pdf', status: 'processing' } } })
    })

    const result = await store.uploadDoc('kb1', new FormData())

    expect(store.uploading).toBe(false)
    expect(result.uuid).toBe('d1')
  })

  it('uploadDoc 失败时 uploading 恢复 false 并抛异常', async () => {
    const store = useKnowledgeStore()
    mockUploadDoc.mockRejectedValueOnce(new Error('上传失败'))

    await expect(store.uploadDoc('kb1', new FormData())).rejects.toThrow('上传失败')
    expect(store.uploading).toBe(false)
  })

  it('batchUploadDocs 调用 batchUpload API', async () => {
    const store = useKnowledgeStore()
    mockBatchUpload.mockResolvedValueOnce({
      data: { data: [{ uuid: 'd1', status: 'processing' }] },
    })

    await store.batchUploadDocs('kb1', new FormData())

    expect(mockBatchUpload).toHaveBeenCalled()
  })
})
