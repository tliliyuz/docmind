/** conversation store 单元测试 — 分页加载、时间分组、重命名/删除、addConversation */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mockFetchConversations = vi.fn()
const mockRenameApi = vi.fn()
const mockDeleteApi = vi.fn()

vi.mock('@/api/conversation', () => ({
  fetchConversations: (...args) => mockFetchConversations(...args),
  renameConversation: (...args) => mockRenameApi(...args),
  deleteConversation: (...args) => mockDeleteApi(...args),
}))

let useConversationStore

beforeEach(async () => {
  vi.resetModules()
  setActivePinia(createPinia())
  const mod = await import('@/stores/conversation')
  useConversationStore = mod.useConversationStore
})

afterEach(() => {
  vi.restoreAllMocks()
})

// =====================================================
// loadConversations() 分页
// =====================================================
describe('loadConversations() 分页', () => {
  it('单页取完（items < pageSize）不继续请求', async () => {
    const store = useConversationStore()
    mockFetchConversations.mockResolvedValueOnce({
      data: { data: { items: [{ uuid: 'a', title: '测试' }], total: 1 } },
    })

    await store.loadConversations()

    expect(mockFetchConversations).toHaveBeenCalledTimes(1)
    expect(store.conversations).toHaveLength(1)
    expect(store.loading).toBe(false)
  })

  it('多页循环直到全部取完', async () => {
    const store = useConversationStore()
    // 每页 50 条返回，最后一页少于 50
    const page1 = Array.from({ length: 50 }, (_, i) => ({ uuid: `p1-${i}` }))
    const page2 = Array.from({ length: 30 }, (_, i) => ({ uuid: `p2-${i}` }))
    mockFetchConversations
      .mockResolvedValueOnce({
        data: { data: { items: page1, total: 80 } },
      })
      .mockResolvedValueOnce({
        data: { data: { items: page2, total: 80 } },
      })

    await store.loadConversations()

    expect(mockFetchConversations).toHaveBeenCalledTimes(2)
    expect(store.conversations).toHaveLength(80)
  })

  it('空结果：conversations 为空数组', async () => {
    const store = useConversationStore()
    mockFetchConversations.mockResolvedValueOnce({
      data: { data: { items: [], total: 0 } },
    })

    await store.loadConversations()

    expect(store.conversations).toEqual([])
    expect(mockFetchConversations).toHaveBeenCalledTimes(1)
  })

  it('API 异常：loading 恢复 false，不崩溃', async () => {
    const store = useConversationStore()
    mockFetchConversations.mockRejectedValueOnce(new Error('网络错误'))

    await store.loadConversations()

    expect(store.loading).toBe(false)
  })
})

// =====================================================
// groupedConversations 时间分组
// =====================================================
describe('groupedConversations 时间分组', () => {
  function makeConv(uuid, lastMessageAt, overrides = {}) {
    return { uuid, title: 'conv', last_message_at: lastMessageAt, ...overrides }
  }

  it('最近 24 小时内 → today', () => {
    const store = useConversationStore()
    const now = new Date()
    store.conversations = [makeConv('a', now.toISOString())]

    expect(store.groupedConversations.today).toHaveLength(1)
    expect(store.groupedConversations.yesterday).toHaveLength(0)
  })

  it('昨天 → yesterday', () => {
    const store = useConversationStore()
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000)
    // 设置为昨天 12:00（确保不在 today 范围内）
    yesterday.setHours(12, 0, 0, 0)
    store.conversations = [makeConv('b', yesterday.toISOString())]

    expect(store.groupedConversations.yesterday).toHaveLength(1)
    expect(store.groupedConversations.today).toHaveLength(0)
  })

  it('3 天前 → recent', () => {
    const store = useConversationStore()
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000)
    store.conversations = [makeConv('c', threeDaysAgo.toISOString())]

    expect(store.groupedConversations.recent).toHaveLength(1)
  })

  it('30 天前 → older', () => {
    const store = useConversationStore()
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    store.conversations = [makeConv('d', thirtyDaysAgo.toISOString())]

    expect(store.groupedConversations.older).toHaveLength(1)
  })

  it('仅 created_at 时回退使用 created_at 分组', () => {
    const store = useConversationStore()
    const now = new Date()
    store.conversations = [makeConv('e', null, {
      updated_at: null,
      created_at: now.toISOString(),
    })]

    expect(store.groupedConversations.today).toHaveLength(1)
  })
})

// =====================================================
// renameConversation() / deleteConversation()
// =====================================================
describe('renameConversation() / deleteConversation()', () => {
  it('重命名成功：API 调用 + 本地状态更新', async () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a', title: '旧标题' }]
    mockRenameApi.mockResolvedValueOnce({ data: {} })

    await store.renameConversation('a', '新标题')

    expect(mockRenameApi).toHaveBeenCalledWith('a', '新标题')
    expect(store.conversations[0].title).toBe('新标题')
  })

  it('重命名 API 失败：抛异常，本地状态不变', async () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a', title: '旧标题' }]
    mockRenameApi.mockRejectedValueOnce(new Error('权限不足'))

    await expect(store.renameConversation('a', '新标题')).rejects.toThrow('权限不足')
    expect(store.conversations[0].title).toBe('旧标题')
  })

  it('删除成功：API 调用 + 从本地列表移除', async () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a' }, { uuid: 'b' }]
    mockDeleteApi.mockResolvedValueOnce({ data: {} })

    await store.deleteConversation('a')

    expect(mockDeleteApi).toHaveBeenCalledWith('a')
    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].uuid).toBe('b')
  })

  it('删除 API 失败：抛异常，本地列表不变', async () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a' }]
    mockDeleteApi.mockRejectedValueOnce(new Error('服务器错误'))

    await expect(store.deleteConversation('a')).rejects.toThrow('服务器错误')
    expect(store.conversations).toHaveLength(1)
  })

  it('删除不在列表中的会话：仍调 API，本地不动', async () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a' }]
    mockDeleteApi.mockResolvedValueOnce({ data: {} })

    await store.deleteConversation('not-exist')

    expect(mockDeleteApi).toHaveBeenCalledWith('not-exist')
    expect(store.conversations).toHaveLength(1)
  })
})

// =====================================================
// addConversation() / updateConversationTitle()
// =====================================================
describe('addConversation() / updateConversationTitle()', () => {
  it('addConversation 新 UUID：prepend 到列表头部', () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a' }]

    store.addConversation({ uuid: 'b' })

    expect(store.conversations).toHaveLength(2)
    expect(store.conversations[0].uuid).toBe('b')
  })

  it('addConversation 已存在 UUID：更新而非重复', () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a', title: '旧' }]

    store.addConversation({ uuid: 'a', title: '新' })

    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].title).toBe('新')
  })

  it('updateConversationTitle：找到则更新标题，未找到则无操作', () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a', title: '旧' }]

    store.updateConversationTitle('a', '新标题')
    expect(store.conversations[0].title).toBe('新标题')

    store.updateConversationTitle('not-exist', 'x')
    expect(store.conversations).toHaveLength(1)
  })
})

// =====================================================
// reset()
// =====================================================
describe('reset()', () => {
  it('清除所有状态', () => {
    const store = useConversationStore()
    store.conversations = [{ uuid: 'a' }]
    store.loading = true

    store.reset()

    expect(store.conversations).toEqual([])
    expect(store.loading).toBe(false)
  })
})
