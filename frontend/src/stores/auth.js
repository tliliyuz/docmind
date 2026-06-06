import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, refreshToken as refreshApi, logout as logoutApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const token = ref(localStorage.getItem('access_token') || '')
  const refreshTokenValue = ref(localStorage.getItem('refresh_token') || '')

  /** access_token 过期前自动刷新的定时器 ID */
  let refreshTimerId = null

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  /** 统一存储 token 对到 state + localStorage */
  function setTokens(accessToken, refreshTokenStr) {
    token.value = accessToken
    refreshTokenValue.value = refreshTokenStr
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshTokenStr)
  }

  /** 解析 JWT payload 中的用户信息 */
  function parseJwtUser(accessToken) {
    try {
      const payload = JSON.parse(atob(accessToken.split('.')[1]))
      return {
        id: parseInt(payload.sub),
        username: payload.username,
        role: payload.role
      }
    } catch {
      return null
    }
  }

  /** 启动 Token 自动刷新定时器（到期前 60s 触发） */
  function scheduleRefresh() {
    clearRefreshTimer()
    try {
      const payload = JSON.parse(atob(token.value.split('.')[1]))
      const expiresAt = payload.exp * 1000  // JWT exp 是秒级时间戳
      const now = Date.now()
      const delay = Math.max(expiresAt - now - 60 * 1000, 5000)  // 提前 60s，最少 5s
      refreshTimerId = setTimeout(() => {
        refresh()
      }, delay)
    } catch {
      // JWT 解析失败不启动定时器
    }
  }

  /** 清除自动刷新定时器 */
  function clearRefreshTimer() {
    if (refreshTimerId) {
      clearTimeout(refreshTimerId)
      refreshTimerId = null
    }
  }

  /** 登录 — 调用 API 并持久化 token 对到 localStorage */
  async function loginAction(username, password) {
    const res = await loginApi(username, password)
    const { access_token, refresh_token } = res.data.data
    setTokens(access_token, refresh_token)

    user.value = parseJwtUser(access_token)
    localStorage.setItem('user', JSON.stringify(user.value))

    // 启动自动刷新
    scheduleRefresh()
    return user.value
  }

  /** 刷新 Token — 调用 refresh API 换取新 token 对 */
  async function refresh() {
    if (!refreshTokenValue.value) {
      throw new Error('无 refresh_token')
    }
    try {
      const res = await refreshApi(refreshTokenValue.value)
      const { access_token, refresh_token } = res.data.data
      setTokens(access_token, refresh_token)

      // 更新用户信息（可能变化）
      const newUser = parseJwtUser(access_token)
      if (newUser) {
        user.value = newUser
        localStorage.setItem('user', JSON.stringify(newUser))
      }

      // 重新启动定时器
      scheduleRefresh()
      return true
    } catch (err) {
      // 刷新失败 → 清除全部状态
      clearState()
      throw err
    }
  }

  /** 注册 — 仅调用 API，不自动登录 */
  async function registerAction(username, password) {
    const res = await registerApi(username, password)
    return res.data.data
  }

  /** 清除本地状态（token + user + 定时器） */
  function clearState() {
    clearRefreshTimer()
    user.value = null
    token.value = ''
    refreshTokenValue.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  }

  /** 退出登录 — 调后端吊销 refresh_token + 清除本地状态 */
  async function logout() {
    // 尝试调后端吊销 refresh_token（失败不影响本地清除）
    if (refreshTokenValue.value) {
      try {
        await logoutApi(refreshTokenValue.value)
      } catch {
        // 吊销失败不阻塞退出流程
      }
    }
    clearState()
  }

  return {
    // 状态
    user,
    token,
    refreshToken: refreshTokenValue,
    isLoggedIn,
    isAdmin,

    // 方法
    setTokens,
    login: loginAction,
    register: registerAction,
    refresh,
    logout,
    scheduleRefresh,
    clearRefreshTimer,
  }
})
