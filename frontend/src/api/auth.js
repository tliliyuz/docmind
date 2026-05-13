import api from './index'

export function register(username, password) {
  return api.post('/auth/register', { username, password })
}

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}
