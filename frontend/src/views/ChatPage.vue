<template>
  <div class="chat-page">
    <!-- 顶部知识库选择器：双下拉框隔离「我的」和「公共」 -->
    <div class="kb-selector-bar">
      <div class="kb-selector-inner">
        <span class="kb-label">
          <i class="fas fa-database"></i>
          知识库
        </span>
        <!-- 我的知识库 -->
        <el-select
          v-if="chatStore.selectableKBs.mine.length"
          :model-value="selectedMineKBId"
          placeholder="我的知识库"
          size="default"
          :loading="chatStore.loadingKBs"
          @change="handleKBChange"
        >
          <el-option
            v-for="kb in chatStore.selectableKBs.mine"
            :key="'mine-' + kb.uuid"
            :label="kb.name"
            :value="kb.uuid"
          />
        </el-select>
        <!-- 公共知识库 -->
        <el-select
          v-if="chatStore.selectableKBs.public.length"
          :model-value="selectedPublicKBId"
          placeholder="公共知识库"
          size="default"
          :loading="chatStore.loadingKBs"
          @change="handleKBChange"
        >
          <el-option
            v-for="kb in chatStore.selectableKBs.public"
            :key="'public-' + kb.uuid"
            :label="kb.name + ' (' + (kb.username || '未知') + ')'"
            :value="kb.uuid"
          />
        </el-select>
        <!-- 无任何可选知识库 -->
        <span v-if="!hasAnyKB" class="kb-empty-hint">暂无可用的知识库</span>
      </div>
    </div>

    <!-- 孤儿会话警告 Banner -->
    <div v-if="chatStore.isKbOrphaned && !chatStore.isEmpty" class="orphan-banner">
      <i class="fas fa-exclamation-triangle orphan-banner-icon"></i>
      <div class="orphan-banner-text">
        <span v-if="chatStore.kbStatus === 'deleted'">
          该会话关联的知识库「{{ chatStore.kbName || '未知' }}」已被删除。
        </span>
        <span v-else-if="chatStore.kbStatus === 'unavailable'">
          该会话关联的知识库「{{ chatStore.kbName || '未知' }}」已不可访问。
        </span>
        <span>历史消息仍可查看，如需继续提问，请重新选择一个知识库。</span>
      </div>
      <button class="orphan-banner-btn" @click="handleOrphanNewChat">
        <i class="fas fa-plus"></i>
        新建对话
      </button>
    </div>

    <!-- 消息区域：空态 or 消息列表 -->
    <div class="chat-message-area">
      <WelcomeScreen
        v-if="chatStore.isEmpty"
        @select="handleQuickQuestion"
      />
      <MessageList
        v-else
        ref="messageListRef"
        :messages="chatStore.messages"
        @regenerate="chatStore.regenerate()"
      />
    </div>

    <!-- 输入框 -->
    <ChatInput
      ref="chatInputRef"
      :streaming="chatStore.streaming"
      :placeholder="orphanInputPlaceholder"
      :disabled="chatStore.isKbOrphaned && !chatStore.isEmpty"
      @send="handleSend"
      @stop="chatStore.abort()"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import WelcomeScreen from '@/components/chat/WelcomeScreen.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()

const messageListRef = ref(null)
const chatInputRef = ref(null)

/** 当前选中的 KB 是否属于「我的知识库」分组 */
const selectedMineKBId = computed(() => {
  if (!chatStore.selectedKBId) return null
  const found = chatStore.selectableKBs.mine.find(k => k.uuid === chatStore.selectedKBId)
  return found ? found.uuid : null
})

/** 当前选中的 KB 是否属于「公共知识库」分组 */
const selectedPublicKBId = computed(() => {
  if (!chatStore.selectedKBId) return null
  const found = chatStore.selectableKBs.public.find(k => k.uuid === chatStore.selectedKBId)
  return found ? found.uuid : null
})

/** 是否有任何可选知识库 */
const hasAnyKB = computed(() => {
  return chatStore.selectableKBs.mine.length > 0 || chatStore.selectableKBs.public.length > 0
})

/** 孤儿会话时的输入框 placeholder */
const orphanInputPlaceholder = computed(() => {
  if (!chatStore.isKbOrphaned) return undefined
  if (chatStore.kbStatus === 'deleted') {
    return '此会话关联的知识库已删除，无法继续提问'
  }
  return '此会话关联的知识库不可访问，无法继续提问'
})

/**
 * 根据路由参数初始化会话
 * 对齐 FRONTEND.md §4.1：优先 conversation_id，降级 kb_id
 */
async function initFromRoute() {
  const conversationIdParam = route.query.conversation_id
  const kbIdParam = route.query.kb_id

  if (conversationIdParam) {
    // 继续对话：加载历史消息
    try {
      const data = await chatStore.loadConversation(conversationIdParam)
      // 如果路由同时指定了 kb_id，以会话的 kb_uuid 为准
      if (data.kb_uuid) {
        chatStore.setSelectedKB(data.kb_uuid)
      }
    } catch {
      // 会话不存在或无权限，降级为新对话
      ElMessage.warning('会话不存在或已删除')
      if (kbIdParam) {
        chatStore.setSelectedKB(kbIdParam)
      }
      chatStore.clearMessages()
      // 清除无效的 conversation_id 参数
      router.replace({ query: kbIdParam ? { kb_id: kbIdParam } : {} })
    }
  } else if (kbIdParam) {
    // 新对话但指定了 KB
    chatStore.setSelectedKB(kbIdParam)
    chatStore.clearMessages()
  }
  // 都没有 → 保持当前状态（新对话）
}

onMounted(async () => {
  await chatStore.loadSelectableKBs()
  await initFromRoute()
})

/** 监听路由 query 变化（点击 Sidebar 切换会话时触发） */
watch(
  () => route.query.conversation_id,
  async (newVal, oldVal) => {
    // 仅在值变化时处理（避免 onMounted 后重复触发）
    if (newVal !== oldVal) {
      if (newVal) {
        try {
          await chatStore.loadConversation(newVal)
        } catch {
          // 会话不存在或无权限，降级为新对话
          ElMessage.warning('会话不存在或已删除')
          chatStore.clearMessages()
          router.replace({ query: {} })
        }
      } else {
        // conversation_id 被清除 → 新对话
        chatStore.clearMessages()
      }
    }
  }
)

/** 路由标题 */
watch(() => route.name, () => {
  document.title = '智能问答 - DocMind'
}, { immediate: true })

/** 切换知识库 */
function handleKBChange(kbId) {
  chatStore.setSelectedKB(kbId)
  if (!chatStore.isEmpty) {
    chatStore.clearMessages()
  }
  // 新建对话，清除 conversation_id
  router.push('/chat')
}

/** 孤儿会话新建对话 */
async function handleOrphanNewChat() {
  try {
    await ElMessageBox.confirm(
      '当前会话关联的知识库已不可用。你可以新建一个对话并选择知识库，或继续查看当前会话的历史消息。',
      '新建对话',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '新建对话',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    // 用户选择「新建对话」→ 清除消息，进入新对话
    chatStore.clearMessages()
    router.push('/chat')
  } catch (action) {
    if (action === 'cancel') {
      // 用户选择「取消」→ 保持在当前页面（只读查看历史消息）
    }
    // 关闭弹窗 → 不做任何操作
  }
}

/** 发送消息 */
function handleSend({ question, deepThinking }) {
  if (chatStore.isKbOrphaned && !chatStore.isEmpty) {
    ElMessage.warning('此会话关联的知识库已不可用，请新建对话')
    return
  }
  if (!chatStore.selectedKBId) {
    ElMessage.warning('请先选择一个知识库')
    return
  }
  try {
    chatStore.sendUserMessage(question, deepThinking)
  } catch (err) {
    ElMessage.error(err.message || '发送失败')
  }
}

/** 快捷问题卡片点击 */
function handleQuickQuestion(question) {
  if (!chatStore.selectedKBId) {
    ElMessage.warning('请先选择一个知识库')
    return
  }
  chatStore.sendUserMessage(question, false)
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--dm-bg-chat);
}

/* flex 子元素 min-height: 0 防止内容撑开父容器导致外层滚动 */
.chat-message-area {
  min-height: 0;
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 知识库选择器 */
.kb-selector-bar {
  flex-shrink: 0;
  padding: var(--dm-space-3) var(--dm-space-6);
  border-bottom: 1px solid var(--dm-border-light);
  background: var(--dm-bg-card);
}

.kb-selector-inner {
  max-width: var(--dm-chat-max-width);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
}

.kb-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-secondary);
  white-space: nowrap;
}

.kb-label i {
  color: var(--dm-primary);
}

/* 双下拉框各自最小宽度，防止过窄 */
.kb-selector-inner .el-select {
  min-width: 160px;
}

.kb-empty-hint {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-tertiary);
}

/* 孤儿会话警告 Banner */
.orphan-banner {
  flex-shrink: 0;
  padding: var(--dm-space-3) var(--dm-space-6);
  background: #FFF8E1;
  border-bottom: 1px solid #FFE082;
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  max-width: 100%;
}

.orphan-banner-icon {
  color: #F57F17;
  font-size: var(--dm-text-sm);
  flex-shrink: 0;
}

.orphan-banner-text {
  flex: 1;
  font-size: var(--dm-text-xs);
  color: #5D4037;
  line-height: 1.5;
}

.orphan-banner-btn {
  flex-shrink: 0;
  padding: 6px 14px;
  border: 1px solid #F57F17;
  border-radius: var(--dm-radius-sm);
  background: transparent;
  color: #F57F17;
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-medium);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  transition: all var(--dm-transition-fast);
}

.orphan-banner-btn:hover {
  background: #FFF3E0;
  border-color: #E65100;
  color: #E65100;
}
</style>
