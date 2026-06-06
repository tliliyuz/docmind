/**
 * SSE 流式解析工具
 *
 * 基于 fetch + ReadableStream 实现 SSE 读取（支持 POST 请求体）。
 * 事件类型：meta / thinking / message / sources / finish / error
 * 心跳帧（`: ping\n\n`）自动忽略。
 */

/**
 * 解析单个 SSE 原始文本块为结构化事件
 * @param {string} raw - 以 \n\n 分隔的单个事件文本
 * @returns {{ event: string, data: object|null }}
 */
export function parseSSEEvent(raw) {
  const lines = raw.split('\n')
  let event = 'message'
  let dataLines = []

  for (const line of lines) {
    // 忽略心跳注释帧（以 : 开头）
    if (line.startsWith(':')) continue
    if (line.startsWith('event: ')) {
      event = line.slice(7).trim()
    } else if (line.startsWith('data: ')) {
      dataLines.push(line.slice(6))
    }
  }

  // data 可能是多行，拼接后尝试 JSON 解析
  const dataStr = dataLines.join('\n')
  let data = null
  if (dataStr) {
    try {
      data = JSON.parse(dataStr)
    } catch {
      // JSON 解析失败时保留原始字符串
      data = { raw: dataStr }
    }
  }

  return { event, data }
}

/** 执行 Token 刷新（SSE 专用，与 Axios 拦截器共享刷新逻辑） */
async function refreshSSEToken() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) throw new Error('无 refresh_token')

  const res = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  if (!res.ok) throw new Error('Token 刷新失败')

  const json = await res.json()
  const { access_token, refresh_token: newRefreshToken } = json.data
  localStorage.setItem('access_token', access_token)
  localStorage.setItem('refresh_token', newRefreshToken)
  return access_token
}

/**
 * 创建 SSE 流式请求并逐事件回调
 *
 * @param {string} url - 请求地址（如 /api/chat）
 * @param {object} options
 * @param {object} options.body - POST 请求体（会被 JSON.stringify）
 * @param {string} options.token - Bearer Token
 * @param {function} options.onEvent - 事件回调 (eventType: string, data: object) => void
 * @param {function} [options.onError] - 错误回调 (error: Error) => void
 * @param {function} [options.onDone] - 流结束回调 () => void
 * @returns {{ abort: () => void }} 返回 abort 函数用于手动中断
 */
export function createSSEStream(url, options) {
  const { body, onEvent, onError, onDone } = options
  const controller = new AbortController()

  const doFetch = async (tokenParam) => {
    try {
      let response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tokenParam ? { Authorization: `Bearer ${tokenParam}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      // 401 + E5003 → 尝试刷新 Token 并重试一次
      if (response.status === 401) {
        let errorData
        try {
          errorData = await response.json()
        } catch {
          errorData = {}
        }

        if (errorData.code === 'E5003') {
          try {
            const newToken = await refreshSSEToken()
            // 重试请求
            response = await fetch(url, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${newToken}`,
              },
              body: JSON.stringify(body),
              signal: controller.signal,
            })
          } catch (refreshErr) {
            // 刷新失败 → 清除 token → 跳转登录
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('user')
            if (window.location.pathname !== '/login') {
              window.location.href = '/login'
            }
            onError?.(new Error('认证已过期，请重新登录'))
            return
          }
        } else {
          // 其他 401 错误
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('user')
          if (window.location.pathname !== '/login') {
            window.location.href = '/login'
          }
          onError?.(new Error(errorData.message || '认证失败'))
          return
        }
      }

      // 非 200 响应：尝试解析 JSON 错误
      if (!response.ok) {
        let errorData
        try {
          errorData = await response.json()
        } catch {
          errorData = { code: `HTTP_${response.status}`, message: `请求失败: ${response.status}` }
        }
        onError?.(new Error(errorData.message || `HTTP ${response.status}`))
        return
      }

      // 读取 SSE 流
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // 按 \n\n 分割事件
        const parts = buffer.split('\n\n')
        buffer = parts.pop() // 保留未完成的片段

        for (const part of parts) {
          if (!part.trim()) continue
          const { event, data } = parseSSEEvent(part)
          if (data !== null) {
            onEvent?.(event, data)
          }
        }
      }

      // 处理缓冲区残留
      if (buffer.trim()) {
        const { event, data } = parseSSEEvent(buffer)
        if (data !== null) {
          onEvent?.(event, data)
        }
      }

      onDone?.()
    } catch (err) {
      if (err.name === 'AbortError') {
        // 用户主动中断，不算错误
        onDone?.()
      } else {
        onError?.(err)
      }
    }
  }

  // 从 localStorage 获取最新 token
  const token = localStorage.getItem('access_token')
  doFetch(token)

  return {
    abort() {
      controller.abort()
    },
  }
}
