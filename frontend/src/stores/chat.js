/**
 * Chat Store — 聊天状态管理
 *
 * 管理问答消息列表、SSE 流式消费、会话 ID、知识库选择等。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { sendMessage as apiSendMessage, fetchSelectableKBs } from '@/api/chat'
import { fetchConversationDetail } from '@/api/conversation'
import { useConversationStore } from '@/stores/conversation'

let clientIdCounter = 0
function genClientId() {
  return `client_${Date.now()}_${++clientIdCounter}`
}

export const useChatStore = defineStore('chat', () => {
  // ===== 状态 =====

  /** 消息列表 */
  const messages = ref([])

  /** 当前会话 ID（null 表示新对话） */
  const conversationId = ref(null)

  /** 是否正在流式接收 */
  const streaming = ref(false)

  /** 当前 SSE 流引用（用于 abort） */
  const currentStream = ref(null)

  /** 选中的知识库 ID */
  const selectedKBId = ref(null)

  /** 可选知识库列表 { mine: [], public: [] } */
  const selectableKBs = ref({ mine: [], public: [] })

  /** 加载知识库列表中 */
  const loadingKBs = ref(false)

  // ===== 计算属性 =====

  /** 消息列表是否为空 */
  const isEmpty = computed(() => messages.value.length === 0)

  /** 最后一条消息 */
  const lastMessage = computed(() => {
    return messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  })

  /** 是否有正在流式接收的助手消息 */
  const hasStreamingMessage = computed(() => {
    return messages.value.some(m => m.role === 'assistant' && m.status === 'streaming')
  })

  // ===== 知识库相关 =====

  /** 加载可选知识库列表 */
  async function loadSelectableKBs() {
    loadingKBs.value = true
    try {
      const data = await fetchSelectableKBs()
      selectableKBs.value = data || { mine: [], public: [] }

      // 默认选中：优先 localStorage 缓存，否则第一个 mine KB
      if (!selectedKBId.value) {
        const lastKBId = localStorage.getItem('last_kb_id')
        const allKBs = [...(data.mine || []), ...(data.public || [])]
        if (lastKBId && allKBs.some(kb => kb.id === Number(lastKBId))) {
          selectedKBId.value = Number(lastKBId)
        } else if (data.mine && data.mine.length > 0) {
          selectedKBId.value = data.mine[0].id
        } else if (data.public && data.public.length > 0) {
          selectedKBId.value = data.public[0].id
        }
      }
    } catch (err) {
      console.error('加载知识库列表失败:', err)
    } finally {
      loadingKBs.value = false
    }
  }

  /** 设置选中的知识库 */
  function setSelectedKB(kbId) {
    selectedKBId.value = kbId
    localStorage.setItem('last_kb_id', String(kbId))
  }

  // ===== 消息操作 =====

  /** 发送消息 */
  function sendUserMessage(question, deepThinking = false) {
    if (!selectedKBId.value) {
      throw new Error('请先选择知识库')
    }
    if (!question.trim()) {
      throw new Error('问题不能为空')
    }

    // 插入用户消息
    const userMsg = {
      id: genClientId(),
      role: 'user',
      content: question,
      status: 'complete',
    }
    messages.value.push(userMsg)

    // 插入助手占位消息
    const assistantMsg = {
      id: genClientId(),
      role: 'assistant',
      content: '',
      thinking: null,
      sources: null,
      status: 'streaming',
      error: null,
      title: null,
      tokenUsage: null,
      serverMessageId: null,
    }
    messages.value.push(assistantMsg)

    streaming.value = true

    // 发起 SSE 请求
    const stream = apiSendMessage(
      {
        conversation_id: conversationId.value,
        kb_id: selectedKBId.value,
        question,
        deep_thinking: deepThinking,
      },
      {
        onEvent(eventType, data) {
          handleSSEEvent(assistantMsg.id, eventType, data)
        },
        onError(error) {
          handleError(assistantMsg.id, error)
        },
        onDone() {
          handleDone(assistantMsg.id)
        },
      }
    )

    currentStream.value = stream
    return assistantMsg.id
  }

  /** 处理 SSE 事件 */
  function handleSSEEvent(msgId, eventType, data) {
    const msg = messages.value.find(m => m.id === msgId)
    if (!msg) return

    switch (eventType) {
      case 'meta':
        // 记录会话 ID（新对话时后端自动创建）
        if (data.conversation_id) {
          conversationId.value = data.conversation_id
          // 通知会话列表 Store 新增会话
          try {
            const convStore = useConversationStore()
            convStore.addConversation({
              id: data.conversation_id,
              kb_id: selectedKBId.value,
              title: '新对话',
              message_count: 1,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            })
          } catch { /* store 可能未初始化 */ }
        }
        break

      case 'thinking':
        // 思考内容增量追加（仅实时展示，不落库）
        if (data.delta) {
          msg.thinking = (msg.thinking || '') + data.delta
        }
        break

      case 'message':
        // 答案内容增量追加
        if (data.delta) {
          msg.content += data.delta
        }
        break

      case 'sources':
        // 引用来源
        msg.sources = data.chunks || []
        break

      case 'finish':
        // 完成
        msg.status = 'complete'
        if (data.message_id) {
          msg.serverMessageId = data.message_id
        }
        if (data.title) {
          msg.title = data.title
          // 更新会话列表中的标题
          if (conversationId.value) {
            try {
              const convStore = useConversationStore()
              convStore.updateConversationTitle(conversationId.value, data.title)
            } catch { /* store 可能未初始化 */ }
          }
        }
        if (data.token_usage) {
          msg.tokenUsage = data.token_usage
        }
        streaming.value = false
        currentStream.value = null
        break

      case 'error':
        // 错误
        msg.status = 'error'
        msg.error = data.message || '未知错误'
        msg.errorCode = data.code
        streaming.value = false
        currentStream.value = null
        break
    }
  }

  /** 处理网络/请求错误 */
  function handleError(msgId, error) {
    const msg = messages.value.find(m => m.id === msgId)
    if (msg) {
      msg.status = 'error'
      msg.error = error.message || '网络异常，请检查连接'
    }
    streaming.value = false
    currentStream.value = null
  }

  /** 流结束处理 */
  function handleDone(msgId) {
    const msg = messages.value.find(m => m.id === msgId)
    // 如果还在 streaming 状态（可能是网络断开导致流提前结束），标记完成
    if (msg && msg.status === 'streaming') {
      if (!msg.content && !msg.error) {
        msg.status = 'error'
        msg.error = '连接中断，未收到完整响应'
      } else {
        msg.status = 'complete'
      }
    }
    streaming.value = false
    currentStream.value = null
  }

  /** 中止当前流式输出 */
  function abort() {
    if (currentStream.value) {
      currentStream.value.abort()
      currentStream.value = null
    }
    streaming.value = false
    // 将最后一条 streaming 状态的助手消息标记为完成
    const lastStreaming = messages.value.findLast(
      m => m.role === 'assistant' && m.status === 'streaming'
    )
    if (lastStreaming) {
      if (!lastStreaming.content && !lastStreaming.error) {
        lastStreaming.status = 'error'
        lastStreaming.error = '已停止生成'
      } else {
        lastStreaming.status = 'complete'
      }
    }
  }

  /** 清空消息列表，开始新对话 */
  function clearMessages() {
    abort()
    messages.value = []
    conversationId.value = null
  }

  /** 设置当前会话（用于加载历史会话） */
  function setConversation(id) {
    conversationId.value = id
  }

  /** 加载历史会话消息（从会话详情接口） */
  async function loadConversation(id) {
    try {
      const res = await fetchConversationDetail(id)
      const data = res.data.data

      conversationId.value = data.id
      selectedKBId.value = data.kb_id

      // 转换后端消息格式为前端格式
      messages.value = (data.messages || []).map(msg => ({
        id: `server_${msg.id}`,
        role: msg.role,
        content: msg.content || '',
        thinking: null,        // thinking_content 不落库，历史中不存在
        sources: null,
        status: 'complete',
        error: null,
        title: null,
        tokenUsage: null,
        serverMessageId: msg.id,
      }))

      return data
    } catch (err) {
      console.error('加载会话详情失败:', err)
      throw err
    }
  }

  /** 重新生成最后一条助手消息 */
  function regenerate() {
    // 找到最后一条用户消息
    const lastUserMsg = messages.value.findLast(m => m.role === 'user')
    if (!lastUserMsg) return

    // 删除最后一条助手消息
    const lastAssistantIdx = messages.value.findLastIndex(m => m.role === 'assistant')
    if (lastAssistantIdx >= 0) {
      messages.value.splice(lastAssistantIdx, 1)
    }

    // 重新发送
    const question = lastUserMsg.content
    sendUserMessage(question, false)
  }

  /** 重置全部状态（退出登录 / 切换账号时调用） */
  function reset() {
    abort()
    messages.value = []
    conversationId.value = null
    streaming.value = false
    currentStream.value = null
    selectedKBId.value = null
    selectableKBs.value = { mine: [], public: [] }
    loadingKBs.value = false
    localStorage.removeItem('last_kb_id')
    // 重置会话列表 Store
    try {
      const convStore = useConversationStore()
      convStore.reset()
    } catch { /* store 可能未初始化 */ }
  }

  return {
    // 状态
    messages,
    conversationId,
    streaming,
    selectedKBId,
    selectableKBs,
    loadingKBs,

    // 计算属性
    isEmpty,
    lastMessage,
    hasStreamingMessage,

    // 方法
    loadSelectableKBs,
    setSelectedKB,
    sendUserMessage,
    loadConversation,
    abort,
    clearMessages,
    setConversation,
    regenerate,
    reset,
  }
})
