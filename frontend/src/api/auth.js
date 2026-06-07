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

/**
 * 修改密码（改密后全部 refresh_token 吊销，须重新登录）
 * @param {string} oldPassword - 当前密码
 * @param {string} newPassword - 新密码
 */
export function changePassword(oldPassword, newPassword) {
  return api.put('/auth/password', { old_password: oldPassword, new_password: newPassword })
}
