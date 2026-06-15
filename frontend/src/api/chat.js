/**
 * Chat API 封装
 *
 * 基于 fetch + SSE 实现流式问答。
 * 使用 utils/sse.js 的 createSSEStream 处理事件流。
 */

import api from './index.js'
import { createSSEStream } from '@/utils/sse'

/**
 * 获取 localStorage 中的 access_token
 * @returns {string|null}
 */
function getToken() {
  return localStorage.getItem('access_token')
}

/**
 * 发送问答请求（SSE 流式）
 *
 * @param {object} params
 * @param {string|null} params.conversation_id - 会话 UUID，新对话传 null
 * @param {string} params.kb_id - 知识库 UUID
 * @param {string} params.question - 用户问题（≤2000 字符）
 * @param {boolean} [params.deep_thinking=false] - 是否启用深度思考
 * @param {object} callbacks
 * @param {function} callbacks.onEvent - 事件回调 (eventType: string, data: object) => void
 * @param {function} [callbacks.onError] - 错误回调 (error: Error) => void
 * @param {function} [callbacks.onDone] - 流结束回调 () => void
 * @returns {{ abort: () => void }} 返回 abort 函数用于手动中断
 */
export function sendMessage(params, callbacks) {
  const { onEvent, onError, onDone } = callbacks

  return createSSEStream('/api/chat', {
    body: {
      conversation_id: params.conversation_id ?? null,
      kb_id: params.kb_id,
      question: params.question,
      deep_thinking: params.deep_thinking ?? false,
    },
    token: getToken(),
    onEvent,
    onError,
    onDone,
  })
}

/**
 * 获取可用于问答的知识库列表（分组）
 *
 * @returns {Promise<{mine: Array, public: Array}>}
 */
export async function fetchSelectableKBs() {
  const response = await api.get('/knowledge-bases/selectable')
  return response.data.data
}
