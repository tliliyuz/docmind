import api from './index'

export function register(username, password) {
  return api.post('/auth/register', { username, password })
}

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}

/**
 * 刷新 Token（Rotation：旧 refresh_token 立即失效）
 * @param {string} refreshToken - 当前 refresh_token
 */
export function refreshToken(refreshToken) {
  return api.post('/auth/refresh', { refresh_token: refreshToken })
}

/**
 * 退出登录（吊销 refresh_token）
 * @param {string} refreshToken - 需要吊销的 refresh_token
 */
export function logout(refreshToken) {
  return api.post('/auth/logout', { refresh_token: refreshToken })
}
