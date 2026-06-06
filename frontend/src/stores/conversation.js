/**
 * 会话列表 Store
 *
 * 独立管理会话列表状态，与 chat.js 解耦。
 * 对齐 FRONTEND.md §4.5.1：时间分组 / 重命名 / 删除 / 高亮当前会话。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchConversations,
  renameConversation as renameApi,
  deleteConversation as deleteApi,
} from '@/api/conversation'

export const useConversationStore = defineStore('conversation', () => {
  // ===== 状态 =====

  /** 全部会话列表（按 updated_at DESC 排序） */
  const conversations = ref([])

  /** 加载中 */
  const loading = ref(false)

  // ===== 计算属性 =====

  /** 按时间分组的会话列表（今天 / 昨天 / 近 7 天 / 更早） */
  const groupedConversations = computed(() => {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
    const sevenDaysAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)

    const groups = {
      today: [],
      yesterday: [],
      recent: [],   // 近 7 天
      older: [],    // 更早
    }

    for (const conv of conversations.value) {
      const updatedAt = new Date(conv.updated_at)
      if (updatedAt >= today) {
        groups.today.push(conv)
      } else if (updatedAt >= yesterday) {
        groups.yesterday.push(conv)
      } else if (updatedAt >= sevenDaysAgo) {
        groups.recent.push(conv)
      } else {
        groups.older.push(conv)
      }
    }

    return groups
  })

  // ===== 操作 =====

  /** 加载全部会话列表（自动循环分页直到取完） */
  async function loadConversations() {
    loading.value = true
    try {
      const allItems = []
      let page = 1
      const pageSize = 50  // 每页 50 条，减少请求次数

      while (true) {
        const res = await fetchConversations(page, pageSize)
        const { items, total } = res.data.data
        allItems.push(...(items || []))
        if (allItems.length >= total || !items || items.length < pageSize) {
          break
        }
        page++
      }

      conversations.value = allItems
    } catch (err) {
      console.error('加载会话列表失败:', err)
    } finally {
      loading.value = false
    }
  }

  /** 重命名会话 */
  async function renameConversation(id, title) {
    await renameApi(id, title)
    // 更新本地状态
    const conv = conversations.value.find(c => c.id === id)
    if (conv) {
      conv.title = title
    }
  }

  /** 删除会话 */
  async function deleteConversation(id) {
    await deleteApi(id)
    // 从本地列表移除
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx >= 0) {
      conversations.value.splice(idx, 1)
    }
  }

  /** 新会话 prepend 到列表头部（SSE finish 事件后调用） */
  function addConversation(conv) {
    // 去重：如果已存在则更新
    const existing = conversations.value.find(c => c.id === conv.id)
    if (existing) {
      Object.assign(existing, conv)
      return
    }
    conversations.value.unshift(conv)
  }

  /** 更新会话标题（LLM 生成标题后调用） */
  function updateConversationTitle(id, title) {
    const conv = conversations.value.find(c => c.id === id)
    if (conv) {
      conv.title = title
    }
  }

  /** 重置状态（退出登录时调用） */
  function reset() {
    conversations.value = []
    loading.value = false
  }

  return {
    // 状态
    conversations,
    loading,

    // 计算属性
    groupedConversations,

    // 方法
    loadConversations,
    renameConversation,
    deleteConversation,
    addConversation,
    updateConversationTitle,
    reset,
  }
})
