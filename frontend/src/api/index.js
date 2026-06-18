import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

// ===== Token 自动刷新机制 =====
// 对齐 FRONTEND.md §1.3.1：401+E5003 → refresh → 重放原请求
// 防并发刷新：isRefreshing 标志位 + requestQueue 队列

let isRefreshing = false
let requestQueue = []  // [{ resolve, reject }]

/** 处理刷新队列：刷新成功后统一重放排队中的请求 */
function processQueue(error, newToken) {
  requestQueue.forEach(({ resolve, reject, config }) => {
    if (error) {
      reject(error)
    } else {
      config.headers.Authorization = `Bearer ${newToken}`
      resolve(api(config))
    }
  })
  requestQueue = []
}

/** 清除本地 token 并跳转登录页 */
export function clearAndRedirect() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user')
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

/** 执行 Token 刷新（独立调用，不经过拦截器循环）。
 *  刷新后同步更新 Pinia store，防止 store 内持过期/已吊销 refresh_token
 *  导致后续 store.refresh() 失败而踢下线。
 *
 *  统一入口：Axios 响应拦截器与 SSE 流式请求（utils/sse.js）共用此函数，
 *  避免 SSE 路径单独实现刷新逻辑时漏同步 Pinia store（历史 bug）。 */
export async function refreshToken() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    throw new Error('无 refresh_token')
  }
  // 使用 axios 原生调用，绕过拦截器避免死循环
  const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken }, {
    timeout: 10000,
    headers: { 'Content-Type': 'application/json' }
  })
  const { access_token, refresh_token: newRefreshToken } = res.data.data
  localStorage.setItem('access_token', access_token)
  localStorage.setItem('refresh_token', newRefreshToken)

  // 同步更新 Pinia store 的 token 对，确保 store.refresh() 使用最新 refresh_token
  // （避免 store 用已吊销的旧 token 调 refresh 导致用户被踢下线）
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    authStore.setTokens(access_token, newRefreshToken)
    authStore.scheduleRefresh()
  } catch {
    // store 尚未初始化时忽略（如未挂载 Pinia 的独立 axios 调用场景）
  }

  return access_token
}

// 请求拦截器 — 自动附加 Bearer Token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器 — 401 时自动刷新 Token 并重放
api.interceptors.response.use(
  response => response,
  async error => {
    const originalConfig = error.config

    // 非 401 或已重试过的请求，直接拒绝
    if (error.response?.status !== 401 || originalConfig._retry) {
      return Promise.reject(error)
    }

    const code = error.response?.data?.code

    // E5002：用户名或密码错误 / E5010：用户被禁用 → 非 token 问题，透传错误给调用方
    if (code === 'E5002' || code === 'E5010') {
      return Promise.reject(error)
    }

    // E5003：Token 过期 → 尝试刷新
    if (code === 'E5003') {
      if (isRefreshing) {
        // 已有刷新请求在进行中，排队等待
        return new Promise((resolve, reject) => {
          requestQueue.push({ resolve, reject, config: originalConfig })
        })
      }

      isRefreshing = true
      originalConfig._retry = true

      try {
        const newToken = await refreshToken()
        // 刷新成功，重放原请求
        originalConfig.headers.Authorization = `Bearer ${newToken}`
        processQueue(null, newToken)
        return api(originalConfig)
      } catch (refreshError) {
        // 刷新失败 → 清除全部 token → 跳转登录
        processQueue(refreshError, null)
        clearAndRedirect()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // 其他 401（E5004/E5005/E5006/E5007/E5008/E5009 等）→ 清除 token 跳转登录
    clearAndRedirect()
    return Promise.reject(error)
  }
)

export default api
