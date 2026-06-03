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
            :key="'mine-' + kb.id"
            :label="kb.name"
            :value="kb.id"
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
            :key="'public-' + kb.id"
            :label="kb.name + ' (' + (kb.username || '未知') + ')'"
            :value="kb.id"
          />
        </el-select>
        <!-- 无任何可选知识库 -->
        <span v-if="!hasAnyKB" class="kb-empty-hint">暂无可用的知识库</span>
      </div>
    </div>

    <!-- 消息区域：空态 or 消息列表 -->
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

    <!-- 输入框 -->
    <ChatInput
      ref="chatInputRef"
      :streaming="chatStore.streaming"
      @send="handleSend"
      @stop="chatStore.abort()"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import WelcomeScreen from '@/components/chat/WelcomeScreen.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const route = useRoute()
const chatStore = useChatStore()

const messageListRef = ref(null)
const chatInputRef = ref(null)

/** 当前选中的 KB 是否属于「我的知识库」分组 */
const selectedMineKBId = computed(() => {
  if (!chatStore.selectedKBId) return null
  const found = chatStore.selectableKBs.mine.find(k => k.id === chatStore.selectedKBId)
  return found ? found.id : null
})

/** 当前选中的 KB 是否属于「公共知识库」分组 */
const selectedPublicKBId = computed(() => {
  if (!chatStore.selectedKBId) return null
  const found = chatStore.selectableKBs.public.find(k => k.id === chatStore.selectedKBId)
  return found ? found.id : null
})

/** 是否有任何可选知识库 */
const hasAnyKB = computed(() => {
  return chatStore.selectableKBs.mine.length > 0 || chatStore.selectableKBs.public.length > 0
})

onMounted(() => {
  chatStore.loadSelectableKBs()
})

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
}

/** 发送消息 */
function handleSend({ question, deepThinking }) {
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
.chat-page > :nth-child(2) {
  min-height: 0;
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
</style>
