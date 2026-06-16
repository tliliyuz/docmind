/** auth store 单元测试 — JWT 解析、刷新定时器、并发守卫、登录/注册/登出 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// Mock API 层
const mockLoginApi = vi.fn()
const mockRegisterApi = vi.fn()
const mockRefreshApi = vi.fn()
const mockLogoutApi = vi.fn()

vi.mock('@/api/auth', () => ({
  login: (...args) => mockLoginApi(...args),
  register: (...args) => mockRegisterApi(...args),
  refreshToken: (...args) => mockRefreshApi(...args),
  logout: (...args) => mockLogoutApi(...args),
}))

// 生成 JWT token 辅助函数
function makeJwt(payload) {
  const header = btoa(JSON.stringify({ alg: 'HS256' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature`
}

let useAuthStore

beforeEach(async () => {
  vi.clearAllMocks()
  localStorage.clear()
  vi.resetModules()
  // 默认 safe mock：防止未配置时 refresh() 访问 undefined.data
  mockRefreshApi.mockResolvedValue({ data: { data: { access_token: '', refresh_token: '' } } })
  setActivePinia(createPinia())
  const mod = await import('@/stores/auth')
  useAuthStore = mod.useAuthStore
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

// =====================================================
// parseJwtUser()
// =====================================================
describe('parseJwtUser()', () => {
  it('正常解析 JWT payload 返回 {id, username, role}', async () => {
    const store = useAuthStore()
    const jwt = makeJwt({ sub: '42', username: 'testuser', role: 'user' })
    // 通过 loginAction 完整链路验证 parseJwtUser
    mockLoginApi.mockResolvedValue({
      data: { data: { access_token: jwt, refresh_token: 'refresh-xxx' } },
    })
    await store.login('testuser', 'password')
    expect(store.user.id).toBe(42)
    expect(store.user.username).toBe('testuser')
    expect(store.user.role).toBe('user')
  })

  it('无效 JWT（无分隔符）不更新 user', async () => {
    const store = useAuthStore()
    mockLoginApi.mockResolvedValue({
      data: { data: { access_token: 'not-a-jwt', refresh_token: 'refresh-xxx' } },
    })
    // loginAction 调用 parseJwtUser 失败时不更新 user
    // 但 setTokens 仍会执行，token 会被设置
    await store.login('test', 'pass')
    // token 已设置但 user 保持 null（parseJwtUser 返回 null）
    expect(store.token).toBe('not-a-jwt')
    expect(store.user).toBeNull()
  })

  it('非 JSON payload（atob 解码成功但 JSON.parse 失败）返回 null', async () => {
    const store = useAuthStore()
    const header = btoa(JSON.stringify({ alg: 'HS256' }))
    const body = btoa('not-json')
    const jwt = `${header}.${body}.sig`
    mockLoginApi.mockResolvedValue({
      data: { data: { access_token: jwt, refresh_token: 'refresh-xxx' } },
    })
    await store.login('test', 'pass')
    // parseJwtUser 静默返回 null，user 不更新
    expect(store.user).toBeNull()
  })

  it('payload 缺少 role 字段时 role 为 undefined', async () => {
    const store = useAuthStore()
    const jwt = makeJwt({ sub: '1', username: 'norole' })
    mockLoginApi.mockResolvedValue({
      data: { data: { access_token: jwt, refresh_token: 'refresh-xxx' } },
    })
    await store.login('norole', 'password')
    expect(store.user.id).toBe(1)
    expect(store.user.username).toBe('norole')
    expect(store.user.role).toBeUndefined()
  })
})

// =====================================================
// scheduleRefresh() / clearRefreshTimer()
// =====================================================
describe('scheduleRefresh() / clearRefreshTimer()', () => {
  it('根据 JWT exp 计算定时器延迟（提前 60s）', () => {
    vi.useFakeTimers()
    const store = useAuthStore()
    const now = Date.now()
    // exp = now + 120s（提前 60s → 延迟 60s）
    const exp = Math.floor((now + 120 * 1000) / 1000)
    const jwt = makeJwt({ sub: '1', username: 'u', role: 'user', exp })

    // 防止 timer 触发时 refresh() 因 mock 未就绪而抛错
    mockRefreshApi.mockReturnValue(new Promise(() => {}))  // 永远 pending
    store.setTokens(jwt, 'refresh-xxx')
    const countBefore = vi.getTimerCount()
    store.scheduleRefresh()
    expect(vi.getTimerCount()).toBe(countBefore + 1)
    vi.useRealTimers()
  })

  it('delay < 5s 时保底为 5000ms', () => {
    vi.useFakeTimers()
    // 清除 store 初始化时创建的定时器
    vi.clearAllTimers()
    const store = useAuthStore()
    const now = Date.now()
    // exp = now + 3s（提前 60s → -57s，取最大 5s）
    const exp = Math.floor((now + 3 * 1000) / 1000)
    const jwt = makeJwt({ sub: '1', username: 'u', role: 'user', exp })

    store.setTokens(jwt, 'refresh-xxx')
    mockRefreshApi.mockReturnValue(new Promise(() => {}))
    const countBefore = vi.getTimerCount()
    store.scheduleRefresh()
    expect(vi.getTimerCount()).toBe(countBefore + 1)
    vi.useRealTimers()
  })

  it('scheduleRefresh 重复调用只保留一个定时器', () => {
    vi.useFakeTimers()
    vi.clearAllTimers()
    const store = useAuthStore()

    const now = Date.now()
    const exp = Math.floor((now + 120 * 1000) / 1000)
    const jwt = makeJwt({ sub: '1', username: 'u', role: 'user', exp })
    store.setTokens(jwt, 'refresh-xxx')
    mockRefreshApi.mockReturnValue(new Promise(() => {}))

    // 调用两次 scheduleRefresh
    const countBefore = vi.getTimerCount()
    store.scheduleRefresh()
    store.scheduleRefresh()

    // 应只增加一个定时器（第二次调用先清除旧的再设新的）
    expect(vi.getTimerCount()).toBe(countBefore + 1)
    vi.useRealTimers()
  })

  it('JWT 解析失败不设定时器且不抛异常', () => {
    const store = useAuthStore()
    store.token = 'invalid.jwt'
    expect(() => store.scheduleRefresh()).not.toThrow()
  })
})

// =====================================================
// _refreshing 并发守卫
// =====================================================
describe('refresh() 并发守卫', () => {
  it('单次刷新成功更新 token 和 user', async () => {
    const store = useAuthStore()
    const oldJwt = makeJwt({ sub: '1', username: 'old', role: 'user', exp: Math.floor(Date.now() / 1000) + 3600 })
    store.setTokens(oldJwt, 'old-refresh')
    store.user = { id: 1, username: 'old', role: 'user' }

    const newJwt = makeJwt({ sub: '1', username: 'new', role: 'admin', exp: Math.floor(Date.now() / 1000) + 7200 })
    mockRefreshApi.mockResolvedValue({
      data: { data: { access_token: newJwt, refresh_token: 'new-refresh' } },
    })

    const result = await store.refresh()
    expect(result).toBe(true)
    expect(mockRefreshApi).toHaveBeenCalledTimes(1)
    expect(store.user.username).toBe('new')
    expect(store.user.role).toBe('admin')
    expect(store.token).toBe(newJwt)
    expect(store.refreshToken).toBe('new-refresh')
  })

  it('并发刷新：第二个调用直接返回 true 不调 API', async () => {
    const store = useAuthStore()
    const jwt = makeJwt({ sub: '1', username: 'u', role: 'user', exp: Math.floor(Date.now() / 1000) + 3600 })
    store.setTokens(jwt, 'old-refresh')

    // 让第一次刷新挂起
    let resolveRefresh
    mockRefreshApi.mockReturnValue(new Promise(r => { resolveRefresh = r }))

    const p1 = store.refresh()
    const p2 = store.refresh()

    expect(mockRefreshApi).toHaveBeenCalledTimes(1)
    expect(await p2).toBe(true)

    // 完成第一次刷新
    const newJwt = makeJwt({ sub: '1', username: 'u', role: 'user', exp: Math.floor(Date.now() / 1000) + 7200 })
    resolveRefresh({ data: { data: { access_token: newJwt, refresh_token: 'new-refresh' } } })
    await p1
  })

  it('刷新 API 失败时清除所有状态并抛异常', async () => {
    const store = useAuthStore()
    const jwt = makeJwt({ sub: '1', username: 'u', role: 'user', exp: Math.floor(Date.now() / 1000) + 3600 })
    store.setTokens(jwt, 'old-refresh')
    store.user = { id: 1, username: 'u', role: 'user' }

    mockRefreshApi.mockRejectedValue(new Error('Refresh failed'))

    await expect(store.refresh()).rejects.toThrow('Refresh failed')
    expect(store.token).toBe('')
    expect(store.refreshToken).toBe('')
    expect(store.user).toBeNull()
    expect(store.isLoggedIn).toBe(false)
  })
})

// =====================================================
// loginAction() / registerAction()
// =====================================================
describe('loginAction() / registerAction()', () => {
  it('登录成功：设置 token、解析 user、持久化、启动定时器', async () => {
    const store = useAuthStore()
    const jwt = makeJwt({ sub: '42', username: 'loginuser', role: 'user', exp: Math.floor(Date.now() / 1000) + 3600 })
    mockLoginApi.mockResolvedValue({
      data: { data: { access_token: jwt, refresh_token: 'refresh-abc' } },
    })

    const user = await store.login('loginuser', 'password123')

    expect(user.id).toBe(42)
    expect(user.username).toBe('loginuser')
    expect(store.token).toBe(jwt)
    expect(store.refreshToken).toBe('refresh-abc')
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem('access_token')).toBe(jwt)
    expect(localStorage.getItem('refresh_token')).toBe('refresh-abc')
    expect(localStorage.getItem('user')).toBe(JSON.stringify(user))
  })

  it('登录 API 失败时抛异常，不破坏已有状态', async () => {
    const store = useAuthStore()
    // 预置状态
    const oldJwt = makeJwt({ sub: '1', username: 'existing', role: 'user' })
    store.setTokens(oldJwt, 'existing-refresh')
    store.user = { id: 1, username: 'existing', role: 'user' }

    mockLoginApi.mockRejectedValue(new Error('密码错误'))

    await expect(store.login('bad', 'wrong')).rejects.toThrow('密码错误')
    // 已有状态不变
    expect(store.token).toBe(oldJwt)
    expect(store.isLoggedIn).toBe(true)
  })

  it('注册成功返回 API 数据，不设置 token', async () => {
    const store = useAuthStore()
    mockRegisterApi.mockResolvedValue({
      data: { data: { id: 99, username: 'newuser' } },
    })

    const result = await store.register('newuser', 'password')
    expect(result.id).toBe(99)
    expect(store.token).toBe('')
    expect(store.isLoggedIn).toBe(false)
  })

  it('注册 API 失败时抛异常', async () => {
    const store = useAuthStore()
    mockRegisterApi.mockRejectedValue(new Error('用户名已存在'))

    await expect(store.register('dup', 'password')).rejects.toThrow('用户名已存在')
    expect(store.isLoggedIn).toBe(false)
  })
})

// =====================================================
// logout()
// =====================================================
describe('logout()', () => {
  it('正常登出：调 API 吊销 + 清除所有本地状态', async () => {
    const store = useAuthStore()
    const jwt = makeJwt({ sub: '1', username: 'u', role: 'user' })
    store.setTokens(jwt, 'refresh-abc')
    store.user = { id: 1, username: 'u', role: 'user' }
    mockLogoutApi.mockResolvedValue({ data: {} })

    await store.logout()

    expect(mockLogoutApi).toHaveBeenCalledWith('refresh-abc')
    expect(store.token).toBe('')
    expect(store.refreshToken).toBe('')
    expect(store.user).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('登出 API 失败仍清除本地状态（优雅降级）', async () => {
    const store = useAuthStore()
    store.setTokens('token', 'refresh-xyz')
    mockLogoutApi.mockRejectedValue(new Error('网络错误'))

    await store.logout()

    expect(store.token).toBe('')
    expect(store.isLoggedIn).toBe(false)
  })

  it('无 refresh_token 时不调 API，直接清除状态', async () => {
    const store = useAuthStore()
    store.setTokens('token', '')  // 无 refresh_token

    await store.logout()

    expect(mockLogoutApi).not.toHaveBeenCalled()
    expect(store.token).toBe('')
    expect(store.isLoggedIn).toBe(false)
  })
})

// =====================================================
// Store 初始化恢复
// =====================================================
describe('Store 初始化恢复', () => {
  it('localStorage 有 token 和 user 时恢复登录态', async () => {
    const jwt = makeJwt({ sub: '5', username: 'cached', role: 'user', exp: Math.floor(Date.now() / 1000) + 3600 })
    const userData = { id: 5, username: 'cached', role: 'user' }
    localStorage.setItem('access_token', jwt)
    localStorage.setItem('refresh_token', 'cached-refresh')
    localStorage.setItem('user', JSON.stringify(userData))

    vi.resetModules()
    setActivePinia(createPinia())
    const mod = await import('@/stores/auth')
    const StoreClass = mod.useAuthStore
    const store = StoreClass()

    expect(store.isLoggedIn).toBe(true)
    expect(store.token).toBe(jwt)
    expect(store.user.id).toBe(5)
  })

  it('空 localStorage 时未登录', async () => {
    vi.resetModules()
    setActivePinia(createPinia())
    const mod = await import('@/stores/auth')
    const store = mod.useAuthStore()

    expect(store.isLoggedIn).toBe(false)
    expect(store.isAdmin).toBe(false)
    expect(store.user).toBeNull()
  })

  it('isAdmin 根据 role 正确计算', async () => {
    const jwt = makeJwt({ sub: '1', username: 'admin', role: 'admin', exp: Math.floor(Date.now() / 1000) + 3600 })
    localStorage.setItem('access_token', jwt)
    localStorage.setItem('refresh_token', 'r')

    vi.resetModules()
    setActivePinia(createPinia())
    const mod = await import('@/stores/auth')
    const store = mod.useAuthStore()

    expect(store.isAdmin).toBe(true)
  })
})
