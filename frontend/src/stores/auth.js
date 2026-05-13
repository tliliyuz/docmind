import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const token = ref(localStorage.getItem('access_token') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  /** 登录 — 调用 API 并持久化 token 和用户信息到 localStorage */
  async function loginAction(username, password) {
    const res = await loginApi(username, password)
    const { access_token } = res.data.data
    token.value = access_token
    localStorage.setItem('access_token', access_token)

    // 从 JWT payload 解析用户信息（中间件已验证签名）
    const payload = JSON.parse(atob(access_token.split('.')[1]))
    user.value = {
      id: parseInt(payload.sub),
      username: payload.username,
      role: payload.role
    }
    localStorage.setItem('user', JSON.stringify(user.value))
    return user.value
  }

  /** 注册 — 仅调用 API，不自动登录 */
  async function registerAction(username, password) {
    const res = await registerApi(username, password)
    return res.data.data
  }

  /** 退出登录 */
  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
  }

  return {
    user,
    token,
    isLoggedIn,
    isAdmin,
    login: loginAction,
    register: registerAction,
    logout
  }
})
