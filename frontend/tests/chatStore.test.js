/** chat store 单元测试 — SSE 状态机（通过回调间接测试）、消息管理、知识库选择 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

let sseCallbacks = {}  // 捕获 sendMessage 传入的回调

const mockSendMessageApi = vi.fn()
const mockFetchKBsApi = vi.fn()
const mockFetchConvDetailApi = vi.fn()

vi.mock('@/api/chat', () => ({
  sendMessage: (...args) => mockSendMessageApi(...args),
  fetchSelectableKBs: (...args) => mockFetchKBsApi(...args),
}))

vi.mock('@/api/conversation', () => ({
  fetchConversationDetail: (...args) => mockFetchConvDetailApi(...args),
}))

const mockAddConv = vi.fn()
const mockUpdateTitle = vi.fn()
const mockConvReset = vi.fn()

vi.mock('@/stores/conversation', () => ({
  useConversationStore: () => ({
    addConversation: mockAddConv,
    updateConversationTitle: mockUpdateTitle,
    reset: mockConvReset,
  }),
}))

let useChatStore

beforeEach(async () => {
  vi.resetModules()
  sseCallbacks = {}
  mockSendMessageApi.mockImplementation((_params, callbacks) => {
    if (callbacks) {
      sseCallbacks.onEvent = callbacks.onEvent
      sseCallbacks.onError = callbacks.onError
      sseCallbacks.onDone = callbacks.onDone
    }
    return { abort: vi.fn() }
  })
  setActivePinia(createPinia())
  const mod = await import('@/stores/chat')
  useChatStore = mod.useChatStore
})

afterEach(() => {
  vi.restoreAllMocks()
})

// =====================================================
// sendUserMessage() 验证
// =====================================================
describe('sendUserMessage() 验证', () => {
  it('未选知识库时抛异常', () => {
    const store = useChatStore()
    store.selectedKBId = null

    expect(() => store.sendUserMessage('测试问题')).toThrow('请先选择知识库')
  })

  it('空问题（纯空格）时抛异常', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'

    expect(() => store.sendUserMessage('   ')).toThrow('问题不能为空')
  })

  it('正常发送：插入用户消息 + assistant 占位 + 进入流式', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'

    const result = store.sendUserMessage('什么是 Kubernetes？')

    expect(store.messages).toHaveLength(2)
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[0].content).toBe('什么是 Kubernetes？')
    expect(store.messages[1].role).toBe('assistant')
    expect(store.messages[1].status).toBe('streaming')
    expect(store.streaming).toBe(true)
    expect(typeof result).toBe('string')  // msgId
  })

  it('API 参数正确传递（conversation_id/kb_id/question/deep_thinking）', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'
    store.conversationId = 'conv-1'

    store.sendUserMessage('test', true)

    expect(mockSendMessageApi).toHaveBeenCalledWith(
      {
        conversation_id: 'conv-1',
        kb_id: 'kb-1',
        question: 'test',
        deep_thinking: true,
      },
      expect.objectContaining({
        onEvent: expect.any(Function),
        onError: expect.any(Function),
        onDone: expect.any(Function),
      }),
    )
  })
})

// =====================================================
// SSE 事件回调（间接测试 handleSSEEvent 状态机）
// =====================================================
describe('SSE 事件回调（通过 sendUserMessage 触发）', () => {
  function setupStreaming(store) {
    store.selectedKBId = 'kb-1'
    const msgId = store.sendUserMessage('问题')
    const msg = store.messages.find(m => m.id === msgId)
    return { msgId, msg }
  }

  it('meta 回调（新会话）：设置 conversationId + addConversation', () => {
    const store = useChatStore()
    const { msgId } = setupStreaming(store)

    sseCallbacks.onEvent('meta', { conversation_id: 'new-conv-uuid' })

    expect(store.conversationId).toBe('new-conv-uuid')
    expect(mockAddConv).toHaveBeenCalledWith(
      expect.objectContaining({ uuid: 'new-conv-uuid', title: '新对话' }),
    )
  })

  it('meta 回调（已有会话）：不调用 addConversation', () => {
    const store = useChatStore()
    store.conversationId = 'existing-conv'
    const { msgId } = setupStreaming(store)

    sseCallbacks.onEvent('meta', { conversation_id: 'existing-conv' })

    expect(mockAddConv).not.toHaveBeenCalled()
  })

  it('thinking 回调：追加 thinking 内容', () => {
    const store = useChatStore()
    const { msgId, msg } = setupStreaming(store)

    sseCallbacks.onEvent('thinking', { delta: '思考中...' })
    sseCallbacks.onEvent('thinking', { delta: '继续...' })

    expect(msg.thinking).toBe('思考中...继续...')
  })

  it('message 回调：追加回答内容', () => {
    const store = useChatStore()
    const { msgId, msg } = setupStreaming(store)

    sseCallbacks.onEvent('message', { delta: 'Kubernetes 是' })
    sseCallbacks.onEvent('message', { delta: '一个容器编排平台。' })

    expect(msg.content).toBe('Kubernetes 是一个容器编排平台。')
  })

  it('sources 回调：设置 sources/confidence', () => {
    const store = useChatStore()
    const { msgId, msg } = setupStreaming(store)

    sseCallbacks.onEvent('sources', {
      chunks: [{ chunk_index: 1, content: 'chunk' }],
      confidence: 'medium',
      confidence_note: '部分证据可能不完整',
    })

    expect(msg.sources).toHaveLength(1)
    expect(msg.confidence).toBe('medium')
    expect(msg.confidenceNote).toBe('部分证据可能不完整')
  })

  it('finish 回调：标记 complete + serverMessageId + tokenUsage + 更新标题', () => {
    const store = useChatStore()
    store.conversationId = 'conv-1'
    const { msgId, msg } = setupStreaming(store)

    sseCallbacks.onEvent('finish', {
      message_id: 42,
      title: 'K8s 问题',
      token_usage: { prompt: 100, completion: 50, total: 150 },
    })

    expect(msg.status).toBe('complete')
    expect(msg.serverMessageId).toBe(42)
    expect(msg.tokenUsage.total).toBe(150)
    expect(store.streaming).toBe(false)
    expect(mockUpdateTitle).toHaveBeenCalledWith('conv-1', 'K8s 问题')
  })

  it('error 回调：标记 error + 记录错误信息 + 停止流式', () => {
    const store = useChatStore()
    const { msgId, msg } = setupStreaming(store)

    sseCallbacks.onEvent('error', {
      code: 'E4002',
      message: 'LLM 调用失败',
    })

    expect(msg.status).toBe('error')
    expect(msg.errorCode).toBe('E4002')
    expect(msg.error).toBe('LLM 调用失败')
    expect(store.streaming).toBe(false)
  })
})

// =====================================================
// loadConversation()
// =====================================================
describe('loadConversation()', () => {
  it('成功加载：转换服务端消息为前端格式', async () => {
    const store = useChatStore()
    mockFetchConvDetailApi.mockResolvedValueOnce({
      data: {
        data: {
          uuid: 'conv-1',
          kb_uuid: 'kb-1',
          kb_name: '测试知识库',
          kb_status: 'active',
          messages: [
            { role: 'user', content: 'Q1', id: 1, thinking_content: null, token_count: 10 },
            { role: 'assistant', content: 'A1', id: 2, thinking_content: null, token_count: 20, sources: [], confidence: 'high' },
          ],
        },
      },
    })

    await store.loadConversation('conv-1')

    expect(store.conversationId).toBe('conv-1')
    expect(store.selectedKBId).toBe('kb-1')
    expect(store.kbName).toBe('测试知识库')
    expect(store.messages).toHaveLength(2)
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[0].status).toBe('complete')
  })

  it('空消息列表：不崩溃', async () => {
    const store = useChatStore()
    mockFetchConvDetailApi.mockResolvedValueOnce({
      data: { data: { messages: [] } },
    })

    await store.loadConversation('conv-empty')

    expect(store.messages).toEqual([])
  })

  it('API 失败：抛异常', async () => {
    const store = useChatStore()
    mockFetchConvDetailApi.mockRejectedValueOnce(new Error('会话不存在'))

    await expect(store.loadConversation('bad-id')).rejects.toThrow('会话不存在')
  })
})

// =====================================================
// regenerate()
// =====================================================
describe('regenerate()', () => {
  it('找到最后用户消息：移除助手消息并重新流式', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'
    store.messages = [
      { id: 'u1', role: 'user', content: 'Q1', status: 'complete' },
      { id: 'a1', role: 'assistant', content: 'A1', status: 'complete', sources: [] },
    ]

    store.regenerate()

    expect(store.messages).toHaveLength(2)
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[1].role).toBe('assistant')
    expect(store.messages[1].status).toBe('streaming')
  })

  it('无用户消息：不抛异常', () => {
    const store = useChatStore()
    store.messages = []

    expect(() => store.regenerate()).not.toThrow()
  })
})

// =====================================================
// abort() / onDone
// =====================================================
describe('abort() / onDone', () => {
  it('abort 有内容：标记 complete', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'
    store.sendUserMessage('test')
    const msg = store.messages[1]
    msg.content = '部分回答'

    store.abort()

    expect(msg.status).toBe('complete')
    expect(store.streaming).toBe(false)
  })

  it('abort 无内容：标记 error（已停止生成）', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'
    store.sendUserMessage('test')
    const msg = store.messages[1]

    store.abort()

    expect(msg.status).toBe('error')
    expect(msg.error).toBe('已停止生成')
  })

  it('onDone 有内容：标记 complete', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'
    store.sendUserMessage('test')
    const msg = store.messages[1]
    msg.content = '完整回答'

    sseCallbacks.onDone()

    expect(msg.status).toBe('complete')
    expect(store.streaming).toBe(false)
  })

  it('onDone 无内容：标记 error（连接中断）', () => {
    const store = useChatStore()
    store.selectedKBId = 'kb-1'
    store.sendUserMessage('test')
    const msg = store.messages[1]

    sseCallbacks.onDone()

    expect(msg.status).toBe('error')
    expect(msg.error).toContain('连接中断')
  })
})

// =====================================================
// reset()
// =====================================================
describe('reset()', () => {
  it('清除所有状态并调用 convStore.reset()', () => {
    const store = useChatStore()
    store.messages = [{ id: 'm1', role: 'user', content: 'test' }]
    store.conversationId = 'conv-1'
    store.streaming = true
    store.selectedKBId = 'kb-1'

    store.reset()

    expect(store.messages).toEqual([])
    expect(store.conversationId).toBeNull()
    expect(store.streaming).toBe(false)
    expect(mockConvReset).toHaveBeenCalled()
  })
})
