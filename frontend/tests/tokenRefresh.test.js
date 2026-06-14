/** Token 自动刷新测试 — ROADMAP §6.6 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

describe('Axios 拦截器 — 请求拦截器', () => {
  let api

  beforeEach(async () => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.resetModules()
    const mod = await import('@/api/index')
    api = mod.default
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('请求拦截器自动附加 Authorization 头', async () => {
    localStorage.setItem('access_token', 'my-token')

    const mockAdapter = vi.fn().mockResolvedValue({ data: {} })
    api.defaults.adapter = mockAdapter

    await api.get('/test')

    const callConfig = mockAdapter.mock.calls[0][0]
    expect(callConfig.headers.Authorization).toBe('Bearer my-token')
  })

  it('无 token 时不附加 Authorization 头', async () => {
    const mockAdapter = vi.fn().mockResolvedValue({ data: {} })
    api.defaults.adapter = mockAdapter

    await api.get('/test')

    const callConfig = mockAdapter.mock.calls[0][0]
    expect(callConfig.headers.Authorization).toBeUndefined()
  })

  it('非 401 错误直接拒绝（不触发刷新）', async () => {
    localStorage.setItem('access_token', 'token')
    localStorage.setItem('refresh_token', 'refresh')

    const error500 = {
      response: { status: 500, data: { code: 'E9001', message: '服务器错误' } },
      config: { headers: {} },
    }

    const mockAdapter = vi.fn().mockRejectedValue(error500)
    api.defaults.adapter = mockAdapter

    await expect(api.get('/test')).rejects.toEqual(error500)
    // Token 不应被清除
    expect(localStorage.getItem('access_token')).toBe('token')
  })

  it('401 + E5004 Token 无效时清除 token', async () => {
    localStorage.setItem('access_token', 'token')
    localStorage.setItem('refresh_token', 'refresh')

    const error401 = {
      response: { status: 401, data: { code: 'E5004', message: 'Token 无效' } },
      config: { headers: {} },
    }

    const mockAdapter = vi.fn().mockRejectedValue(error401)
    api.defaults.adapter = mockAdapter

    await expect(api.get('/test')).rejects.toThrow()

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('401 + E5002 密码错误时不触发清除（透传给调用方）', async () => {
    localStorage.setItem('access_token', 'token')
    localStorage.setItem('refresh_token', 'refresh')

    const error401 = {
      response: { status: 401, data: { code: 'E5002', message: '用户名或密码错误' } },
      config: { headers: {} },
    }

    const mockAdapter = vi.fn().mockRejectedValue(error401)
    api.defaults.adapter = mockAdapter

    await expect(api.get('/test')).rejects.toEqual(error401)

    // E5002 是业务错误（密码错误），token 不应被清除
    expect(localStorage.getItem('access_token')).toBe('token')
    expect(localStorage.getItem('refresh_token')).toBe('refresh')
  })

  it('401 + E5003 且无 refresh_token 时清除 token', async () => {
    localStorage.setItem('access_token', 'expired-token')
    // 不设置 refresh_token

    const error401 = {
      response: { status: 401, data: { code: 'E5003', message: 'Token 过期' } },
      config: { headers: {}, _retry: false },
    }

    const mockAdapter = vi.fn().mockRejectedValue(error401)
    api.defaults.adapter = mockAdapter

    await expect(api.get('/test')).rejects.toThrow()

    expect(localStorage.getItem('access_token')).toBeNull()
  })
})

describe('authStore Token 管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.resetModules()
  })

  it('setTokens 同时更新 localStorage 和 state', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    store.setTokens('new-access', 'new-refresh')

    expect(store.token).toBe('new-access')
    expect(store.refreshToken).toBe('new-refresh')
    expect(localStorage.getItem('access_token')).toBe('new-access')
    expect(localStorage.getItem('refresh_token')).toBe('new-refresh')
  })

  it('logout 清除全部本地状态', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    store.setTokens('access', 'refresh')
    await store.logout()

    expect(store.token).toBe('')
    expect(store.refreshToken).toBe('')
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('logout 后端吊销失败时仍清除本地状态', async () => {
    // Mock fetch to simulate backend failure
    const originalFetch = global.fetch
    global.fetch = vi.fn().mockRejectedValue(new Error('网络错误'))

    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    store.setTokens('access', 'refresh')
    await store.logout()

    // 即使后端失败，本地状态也要清除
    expect(store.token).toBe('')
    expect(store.refreshToken).toBe('')
    expect(localStorage.getItem('access_token')).toBeNull()

    global.fetch = originalFetch
  })

  it('从 localStorage 恢复 token 状态', async () => {
    localStorage.setItem('access_token', 'stored-access')
    localStorage.setItem('refresh_token', 'stored-refresh')
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'test', role: 'user' }))

    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    expect(store.token).toBe('stored-access')
    expect(store.refreshToken).toBe('stored-refresh')
    expect(store.isLoggedIn).toBe(true)
    expect(store.user.username).toBe('test')
  })

  it('isLoggedIn 在无 token 时为 false', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    expect(store.isLoggedIn).toBe(false)
  })

  it('isAdmin 在用户角色为 admin 时为 true', async () => {
    localStorage.setItem('access_token', 'token')
    localStorage.setItem('refresh_token', 'refresh')
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'admin', role: 'admin' }))

    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    expect(store.isAdmin).toBe(true)
  })
})

describe('conversationStore 会话管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
  })

  it('初始状态为空列表', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useConversationStore } = await import('@/stores/conversation')
    const store = useConversationStore()

    expect(store.conversations).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('addConversation 新增会话到列表头部', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useConversationStore } = await import('@/stores/conversation')
    const store = useConversationStore()

    store.addConversation({ uuid: 'uuid-1', title: '会话1' })
    store.addConversation({ uuid: 'uuid-2', title: '会话2' })

    expect(store.conversations).toHaveLength(2)
    expect(store.conversations[0].uuid).toBe('uuid-2')  // 新增的在头部
    expect(store.conversations[1].uuid).toBe('uuid-1')
  })

  it('addConversation 去重：重复 ID 更新而非新增', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useConversationStore } = await import('@/stores/conversation')
    const store = useConversationStore()

    store.addConversation({ uuid: 'uuid-dup', title: '原标题' })
    store.addConversation({ uuid: 'uuid-dup', title: '更新标题' })

    expect(store.conversations).toHaveLength(1)
    expect(store.conversations[0].title).toBe('更新标题')
  })

  it('updateConversationTitle 更新指定会话标题', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useConversationStore } = await import('@/stores/conversation')
    const store = useConversationStore()

    store.addConversation({ uuid: 'uuid-title', title: '旧标题' })
    store.updateConversationTitle('uuid-title', '新标题')

    expect(store.conversations[0].title).toBe('新标题')
  })

  it('updateConversationTitle 不存在的 ID 不报错', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useConversationStore } = await import('@/stores/conversation')
    const store = useConversationStore()

    store.addConversation({ uuid: 'uuid-noexist', title: '标题' })
    store.updateConversationTitle('uuid-nonexist', '不存在')

    expect(store.conversations[0].title).toBe('标题')
  })

  it('reset 清空所有状态', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useConversationStore } = await import('@/stores/conversation')
    const store = useConversationStore()

    store.addConversation({ id: 1, title: '会话' })
    store.reset()

    expect(store.conversations).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('groupedConversations 按时间正确分组', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())

    const { useConversationStore } = await import('@/stores/conversation')
    const store = useConversationStore()

    const now = new Date()
    const today = now.toISOString()
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString()
    const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString()
    const tenDaysAgo = new Date(now.getTime() - 10 * 24 * 60 * 60 * 1000).toISOString()

    store.conversations = [
      { id: 1, title: '今天', updated_at: today },
      { id: 2, title: '昨天', updated_at: yesterday },
      { id: 3, title: '三天前', updated_at: threeDaysAgo },
      { id: 4, title: '十天前', updated_at: tenDaysAgo },
    ]

    const groups = store.groupedConversations
    expect(groups.today).toHaveLength(1)
    expect(groups.today[0].title).toBe('今天')
    expect(groups.yesterday).toHaveLength(1)
    expect(groups.yesterday[0].title).toBe('昨天')
    expect(groups.recent).toHaveLength(1)
    expect(groups.recent[0].title).toBe('三天前')
    expect(groups.older).toHaveLength(1)
    expect(groups.older[0].title).toBe('十天前')
  })
})
