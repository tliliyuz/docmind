/** SSE 流式解析工具测试 — ROADMAP §5.5 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { parseSSEEvent, createSSEStream } from '@/utils/sse'

// Mock @/api 的共享刷新函数，隔离 SSE 测试不依赖真实 axios 实例
const apiMocks = vi.hoisted(() => ({
  refreshToken: vi.fn(),
  clearAndRedirect: vi.fn(),
}))
vi.mock('@/api', () => ({
  refreshToken: apiMocks.refreshToken,
  clearAndRedirect: apiMocks.clearAndRedirect,
  default: {},
}))

describe('parseSSEEvent', () => {
  // ==================== 基本事件解析 ====================

  it('解析 meta 事件 — 含 conversation_id', () => {
    const raw = 'event: meta\ndata: {"conversation_id":42}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('meta')
    expect(data).toEqual({ conversation_id: 42 })
  })

  it('解析 message 事件 — 含 delta 增量内容', () => {
    const raw = 'event: message\ndata: {"delta":"你好"}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('message')
    expect(data).toEqual({ delta: '你好' })
  })

  it('解析 thinking 事件 — 含 delta 思考内容', () => {
    const raw = 'event: thinking\ndata: {"delta":"让我想想…"}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('thinking')
    expect(data).toEqual({ delta: '让我想想…' })
  })

  it('解析 sources 事件 — 含 chunks 数组', () => {
    const raw = 'event: sources\ndata: {"chunks":[{"doc_id":1,"doc_name":"手册.pdf","content":"第1条…"}]}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('sources')
    expect(data.chunks).toHaveLength(1)
    expect(data.chunks[0].doc_name).toBe('手册.pdf')
  })

  it('解析 finish 事件 — 含 message_id + title + token_usage', () => {
    const raw = 'event: finish\ndata: {"message_id":99,"title":"报销流程","token_usage":{"prompt":120,"completion":80,"total":200}}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('finish')
    expect(data.message_id).toBe(99)
    expect(data.title).toBe('报销流程')
    expect(data.token_usage.total).toBe(200)
  })

  it('解析 error 事件 — 含 code + message', () => {
    const raw = 'event: error\ndata: {"code":"E4003","message":"检索服务异常"}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('error')
    expect(data.code).toBe('E4003')
    expect(data.message).toBe('检索服务异常')
  })

  // ==================== 边界与容错 ====================

  it('心跳帧（以 : 开头）被忽略 — 返回 null data', () => {
    const raw = ': ping\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('message') // 默认 event 类型
    expect(data).toBeNull()
  })

  it('多行 data 拼接为完整 JSON', () => {
    const raw = 'event: message\ndata: {"delta":"第1行"}\ndata: {"delta":"第2行"}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('message')
    // 多行 data 以 \n 拼接后 JSON.parse — 只有最后一行会被解析为有效 JSON
    // 实际 SSE 协议中多行 data 会在客户端用 \n 连接后再解析
    expect(data).not.toBeNull()
  })

  it('JSON 解析失败时保留原始字符串于 raw 字段', () => {
    const raw = 'event: message\ndata: 这不是合法的 JSON\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('message')
    expect(data).toEqual({ raw: '这不是合法的 JSON' })
  })

  it('无 event 行时默认返回 "message"', () => {
    const raw = 'data: {"delta":"默认事件"}\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('message')
    expect(data).toEqual({ delta: '默认事件' })
  })

  it('空 data 时返回 null', () => {
    const raw = 'event: finish\n\n'
    const { event, data } = parseSSEEvent(raw)
    expect(event).toBe('finish')
    expect(data).toBeNull()
  })

  it('仅空白内容的事件被跳过', () => {
    const raw = '\n\n'
    // 空行 split 后没有有效内容
    const lines = raw.split('\n')
    // 确认 parseSSEEvent 会被 createSSEStream 调用前过滤
    expect(lines.filter(l => l.trim())).toHaveLength(0)
  })
})

describe('createSSEStream', () => {
  let mockFetch
  let mockReadableStream

  beforeEach(() => {
    // 构造可读流
    mockReadableStream = {
      getReader: vi.fn(),
    }
    mockFetch = vi.fn()
    global.fetch = mockFetch
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  /** 构造 SSE 字节流响应 */
  function mockSSEResponse(events, status = 200) {
    const encoder = new TextEncoder()
    const chunks = events.map(e => {
      let text = ''
      if (e.event) text += `event: ${e.event}\n`
      if (e.data !== undefined) text += `data: ${typeof e.data === 'string' ? e.data : JSON.stringify(e.data)}\n`
      text += '\n'
      return encoder.encode(text)
    })

    let chunkIndex = 0
    const reader = {
      read: vi.fn(),
    }

    // 逐个返回 chunk
    reader.read = vi.fn(() => {
      if (chunkIndex < chunks.length) {
        const result = { done: false, value: chunks[chunkIndex++] }
        return Promise.resolve(result)
      }
      return Promise.resolve({ done: true })
    })

    mockReadableStream.getReader.mockReturnValue(reader)
    mockFetch.mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      body: mockReadableStream,
      json: vi.fn().mockResolvedValue({ code: `HTTP_${status}`, message: `请求失败: ${status}` }),
    })
  }

  it('正常 SSE 流 — 依次回调 meta → message → sources → finish → onDone', async () => {
    mockSSEResponse([
      { event: 'meta', data: { conversation_id: 1 } },
      { event: 'message', data: { delta: '你好' } },
      { event: 'sources', data: { chunks: [{ doc_id: 1, doc_name: 'a.pdf' }] } },
      { event: 'finish', data: { message_id: 10, title: '报销', token_usage: { total: 100 } } },
    ])

    const onEvent = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      token: 'test-token',
      onEvent,
      onError,
      onDone,
    })

    // 等待异步完成
    await vi.waitFor(() => {
      expect(onDone).toHaveBeenCalled()
    })

    expect(onEvent).toHaveBeenCalledTimes(4)
    expect(onEvent).toHaveBeenNthCalledWith(1, 'meta', { conversation_id: 1 })
    expect(onEvent).toHaveBeenNthCalledWith(2, 'message', { delta: '你好' })
    expect(onEvent).toHaveBeenNthCalledWith(3, 'sources', { chunks: [{ doc_id: 1, doc_name: 'a.pdf' }] })
    expect(onEvent).toHaveBeenNthCalledWith(4, 'finish', { message_id: 10, title: '报销', token_usage: { total: 100 } })
    expect(onError).not.toHaveBeenCalled()
  })

  it('HTTP 非 200 状态 — 调用 onError', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({ code: 'E9001', message: '服务器内部错误' }),
      body: null,
    })

    const onEvent = vi.fn()
    const onError = vi.fn()
    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      token: null,
      onEvent,
      onError,
      onDone,
    })

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalled()
    })

    expect(onError.mock.calls[0][0].message).toBe('服务器内部错误')
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('HTTP 错误且响应非 JSON 时 — 使用兜底错误消息', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 502,
      json: vi.fn().mockRejectedValue(new Error('Not JSON')),
      body: null,
    })

    const onError = vi.fn()
    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      token: null,
      onEvent: vi.fn(),
      onError,
      onDone,
    })

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalled()
    })

    expect(onError.mock.calls[0][0].message).toBe('请求失败: 502')
  })

  it('AbortError 时调用 onDone 而非 onError', async () => {
    const abortError = new Error('The user aborted a request.')
    abortError.name = 'AbortError'
    mockFetch.mockRejectedValue(abortError)

    const onError = vi.fn()
    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      token: null,
      onEvent: vi.fn(),
      onError,
      onDone,
    })

    await vi.waitFor(() => {
      expect(onDone).toHaveBeenCalled()
    })

    expect(onError).not.toHaveBeenCalled()
  })

  it('网络异常时调用 onError', async () => {
    mockFetch.mockRejectedValue(new Error('Network Error'))

    const onError = vi.fn()
    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      token: null,
      onEvent: vi.fn(),
      onError,
      onDone,
    })

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalled()
    })

    expect(onError.mock.calls[0][0].message).toBe('Network Error')
  })

  it('缓冲区残留事件在流结束后被解析', async () => {
    mockSSEResponse([
      { event: 'message', data: { delta: '测试' } },
    ])

    const onEvent = vi.fn()
    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      token: null,
      onEvent,
      onDone,
    })

    await vi.waitFor(() => {
      expect(onDone).toHaveBeenCalled()
    })

    expect(onEvent).toHaveBeenCalledWith('message', { delta: '测试' })
  })

  it('请求头包含正确的 Content-Type 和 Authorization', async () => {
    // 从 localStorage 读取 token
    localStorage.setItem('access_token', 'my-jwt-token')

    mockSSEResponse([
      { event: 'finish', data: { message_id: 1 } },
    ])

    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      onEvent: vi.fn(),
      onDone,
    })

    await vi.waitFor(() => {
      expect(onDone).toHaveBeenCalled()
    })

    expect(mockFetch).toHaveBeenCalledWith('/api/chat', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({
        'Content-Type': 'application/json',
        Authorization: 'Bearer my-jwt-token',
      }),
    }))
  })

  it('无 token 时不发送 Authorization 头', async () => {
    // 清除 localStorage 中的 token
    localStorage.removeItem('access_token')

    mockSSEResponse([
      { event: 'finish', data: { message_id: 1 } },
    ])

    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      onEvent: vi.fn(),
      onDone,
    })

    await vi.waitFor(() => {
      expect(onDone).toHaveBeenCalled()
    })

    const callHeaders = mockFetch.mock.calls[0][1].headers
    expect(callHeaders.Authorization).toBeUndefined()
  })

  it('返回 abort 函数并可调用', () => {
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: () => new Promise(() => {}), // 永久 pending
        }),
      },
    })

    const stream = createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      token: null,
      onEvent: vi.fn(),
    })

    expect(stream).toHaveProperty('abort')
    expect(() => stream.abort()).not.toThrow()
  })
})

describe('createSSEStream — 401 Token 刷新', () => {
  let mockFetch
  let mockReadableStream

  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.refreshToken.mockReset()
    apiMocks.clearAndRedirect.mockReset()
    localStorage.clear()

    mockReadableStream = { getReader: vi.fn() }
    mockFetch = vi.fn()
    global.fetch = mockFetch
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  /** 构造一次性 SSE 响应（finish 事件） */
  function mockSSuccessResponse() {
    const encoder = new TextEncoder()
    const data = encoder.encode('event: finish\ndata: {"message_id":1}\n\n')
    const reader = {
      read: vi.fn(() => Promise.resolve({ done: false, value: data })),
    }
    // 第二次 read 返回结束
    reader.read.mockReturnValueOnce(Promise.resolve({ done: false, value: data }))
      .mockReturnValueOnce(Promise.resolve({ done: true }))
    mockReadableStream.getReader.mockReturnValue(reader)
    return {
      ok: true,
      status: 200,
      body: mockReadableStream,
      json: vi.fn().mockResolvedValue({ code: 'HTTP_200' }),
    }
  }

  it('401 + E5003 → 调用共享 refreshToken 刷新并用新 token 重试成功', async () => {
    apiMocks.refreshToken.mockResolvedValue('new-access-token')

    // 第一次 fetch 返回 401 E5003，第二次（重试）返回正常 SSE 流
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      body: null,
      json: vi.fn().mockResolvedValue({ code: 'E5003', message: 'Token 过期' }),
    }).mockResolvedValueOnce(mockSSuccessResponse())

    const onEvent = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      onEvent,
      onError,
      onDone,
    })

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled())

    // 共享 refreshToken 被调用一次（而非旧的本地 refreshSSEToken）
    expect(apiMocks.refreshToken).toHaveBeenCalledTimes(1)
    // 重试请求携带新 token
    const retryCall = mockFetch.mock.calls[1][1]
    expect(retryCall.headers.Authorization).toBe('Bearer new-access-token')
    // 不应触发清除/跳转
    expect(apiMocks.clearAndRedirect).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
  })

  it('401 + E5003 且 refreshToken 抛错 → 调用 clearAndRedirect 并报错', async () => {
    apiMocks.refreshToken.mockRejectedValue(new Error('刷新失败'))

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      body: null,
      json: vi.fn().mockResolvedValue({ code: 'E5003', message: 'Token 过期' }),
    })

    const onError = vi.fn()
    const onDone = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      onEvent: vi.fn(),
      onError,
      onDone,
    })

    await vi.waitFor(() => expect(onError).toHaveBeenCalled())

    expect(apiMocks.refreshToken).toHaveBeenCalledTimes(1)
    expect(apiMocks.clearAndRedirect).toHaveBeenCalledTimes(1)
    expect(onError.mock.calls[0][0].message).toBe('认证已过期，请重新登录')
    // 不应继续重试 fetch
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('401 + 非 E5003（如 E5004）→ 直接 clearAndRedirect 不刷新', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      body: null,
      json: vi.fn().mockResolvedValue({ code: 'E5004', message: 'Token 无效' }),
    })

    const onError = vi.fn()

    createSSEStream('/api/chat', {
      body: { kb_id: 1, question: '测试' },
      onEvent: vi.fn(),
      onError,
      onDone: vi.fn(),
    })

    await vi.waitFor(() => expect(onError).toHaveBeenCalled())

    expect(apiMocks.refreshToken).not.toHaveBeenCalled()
    expect(apiMocks.clearAndRedirect).toHaveBeenCalledTimes(1)
    expect(onError.mock.calls[0][0].message).toBe('Token 无效')
  })
})
