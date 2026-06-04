<template>
  <div class="message-item" :class="[msg.role, { streaming: msg.status === 'streaming' }]">
    <!-- 头像 -->
    <div class="message-avatar" :class="msg.role">
      <i v-if="msg.role === 'user'" class="fas fa-user"></i>
      <i v-else class="fas fa-robot"></i>
    </div>

    <!-- 内容区 -->
    <div class="message-body">
      <div class="message-header">
        <span class="message-name">{{ msg.role === 'user' ? '你' : 'DocMind' }}</span>
      </div>

      <!-- 思考过程折叠面板（仅 assistant + 有 thinking 内容时） -->
      <div v-if="msg.role === 'assistant' && msg.thinking" class="thinking-box">
        <div class="thinking-title" @click="thinkingExpanded = !thinkingExpanded">
          <i class="fas fa-brain"></i>
          <span>思考过程</span>
          <i class="fas" :class="thinkingExpanded ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
        </div>
        <div v-show="thinkingExpanded" class="thinking-content">
          {{ msg.thinking }}
        </div>
      </div>

      <!-- 消息气泡 -->
      <div class="message-bubble" :class="msg.role">
        <!-- 流式输出中：typing 动画 -->
        <div v-if="msg.status === 'streaming' && !msg.content && !msg.error" class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>

        <!-- 有内容：Markdown 渲染 -->
        <div
          v-else-if="msg.content"
          class="markdown-body"
          v-html="renderedContent"
        ></div>

        <!-- 错误状态 -->
        <div v-if="msg.status === 'error' && msg.error" class="error-content">
          <i class="fas fa-exclamation-circle"></i>
          <span>{{ msg.error }}</span>
        </div>
      </div>

      <!-- 引用来源（仅 assistant + 有 sources 时） -->
      <div v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0" class="sources-box">
        <div class="sources-title" @click="sourcesExpanded = !sourcesExpanded">
          <i class="fas fa-book-open"></i>
          <span>引用 {{ uniqueDocCount }} 个文档（共 {{ msg.sources.length }} 个片段）</span>
          <i class="fas" :class="sourcesExpanded ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
        </div>
        <div v-show="sourcesExpanded" class="sources-list">
          <div
            v-for="(src, idx) in msg.sources"
            :key="idx"
            class="source-item"
          >
            <div class="source-header">
              <span class="source-index">[来源{{ src.chunk_index || idx + 1 }}]</span>
              <span class="source-doc">
                <i class="fas fa-file-alt"></i>
                {{ src.doc_name || '未知文档' }}
              </span>
              <span v-if="src.page" class="source-page">第{{ src.page }}页</span>
            </div>
            <div v-if="src.content" class="source-content">{{ src.content }}</div>
            <div v-else class="source-content placeholder">（无法获取片段内容）</div>
          </div>
        </div>
      </div>

      <!-- 操作栏（仅 assistant 完成后 hover 显示） -->
      <div v-if="msg.role === 'assistant' && msg.status === 'complete'" class="message-actions">
        <button class="action-btn" title="重新生成" @click="$emit('regenerate')">
          <i class="fas fa-redo"></i>
          <span>重新生成</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { renderMarkdown, wrapCodeBlocks } from '@/utils/markdown'

const props = defineProps({
  msg: { type: Object, required: true },
})

defineEmits(['regenerate'])

const thinkingExpanded = ref(true)
const sourcesExpanded = ref(true)

const renderedContent = computed(() => {
  if (!props.msg.content) return ''
  const html = renderMarkdown(props.msg.content)
  return wrapCodeBlocks(html)
})

/** 来源中去重的文档数量 */
const uniqueDocCount = computed(() => {
  if (!props.msg.sources) return 0
  const docIds = new Set(props.msg.sources.map(s => s.doc_id).filter(Boolean))
  return docIds.size
})
</script>

<style scoped>
.message-item {
  display: flex;
  gap: var(--dm-space-3);
  padding: var(--dm-space-2) 0;
  max-width: var(--dm-chat-max-width);
  margin: 0 auto;
  width: 100%;
}

/* 用户消息右对齐 */
.message-item.user {
  flex-direction: row-reverse;
}

.message-item.user .message-body {
  align-items: flex-end;
}

.message-item.user .message-header {
  flex-direction: row-reverse;
}

/* 头像 */
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--dm-radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--dm-text-body);
  flex-shrink: 0;
  margin-top: 22px;
}

.message-avatar.user {
  background: var(--dm-text-primary);
  color: white;
}

.message-avatar.assistant {
  background: var(--dm-primary);
  color: white;
}

/* 内容区 */
.message-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: 70%;
}

.message-header {
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
  margin-bottom: 6px;
}

.message-name {
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

/* 消息气泡 */
.message-bubble {
  border-radius: var(--dm-radius-md);
  padding: 14px 18px;
  font-size: var(--dm-text-body);
  line-height: var(--dm-leading-chat);
  word-break: break-word;
}

.message-bubble.user {
  background: var(--dm-text-primary);
  color: white;
  border: 1px solid var(--dm-text-primary);
}

.message-bubble.assistant {
  background: transparent;
  color: var(--dm-text-primary);
  border: none;
  padding: 0;
}

/* Typing 动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 0;
}

.typing-dot {
  width: 8px;
  height: 8px;
  background: var(--dm-text-tertiary);
  border-radius: var(--dm-radius-full);
  animation: typing 1.4s infinite ease;
}

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30%           { transform: translateY(-6px); }
}

/* 错误状态 */
.error-content {
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
  color: var(--dm-danger);
  font-size: var(--dm-text-xs);
  padding: var(--dm-space-2) 0;
}

/* Markdown 渲染样式 */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 12px 0 8px;
  line-height: var(--dm-leading-title);
  font-weight: var(--dm-weight-bold);
}

.markdown-body :deep(h1) { font-size: var(--dm-text-lg); }
.markdown-body :deep(h2) { font-size: var(--dm-text-base); }
.markdown-body :deep(h3) { font-size: var(--dm-text-body); }

.markdown-body :deep(p) {
  margin: 8px 0;
  line-height: var(--dm-leading-chat);
}

.markdown-body :deep(strong) {
  font-weight: var(--dm-weight-semibold);
}

.markdown-body :deep(code:not(pre code)) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: var(--dm-radius-xs);
  font-family: var(--dm-font-mono);
  font-size: 0.9em;
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  border-radius: var(--dm-radius-sm);
  overflow: hidden;
}

.markdown-body :deep(pre code) {
  display: block;
  background: var(--dm-bg-code);
  color: var(--dm-text-code);
  padding: 16px;
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-xs);
  line-height: 1.6;
  overflow-x: auto;
}

.markdown-body :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 3px solid var(--dm-primary);
  background: var(--dm-primary-light);
  border-radius: 0 var(--dm-radius-xs) var(--dm-radius-xs) 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
  line-height: var(--dm-leading-chat);
}

.markdown-body :deep(a) {
  color: var(--dm-primary);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

/* 代码块复制按钮 */
.markdown-body :deep(.code-block-wrapper) {
  position: relative;
}

.markdown-body :deep(.code-copy-btn) {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 32px;
  height: 32px;
  background: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: var(--dm-radius-xs);
  color: #A3A3A3;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all var(--dm-transition-fast);
}

.markdown-body :deep(.code-block-wrapper:hover .code-copy-btn) {
  opacity: 1;
}

.markdown-body :deep(.code-copy-btn:hover) {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.markdown-body :deep(.code-copy-btn .fa-check) {
  display: none;
}

.markdown-body :deep(.code-copy-btn.copied .fa-copy) {
  display: none;
}

.markdown-body :deep(.code-copy-btn.copied .fa-check) {
  display: inline;
  color: var(--dm-success);
}

/* 思考过程折叠面板 */
.thinking-box {
  margin-bottom: var(--dm-space-3);
  padding: 12px 16px;
  background: var(--dm-warning-light);
  border-radius: var(--dm-radius-sm);
  border-left: 3px solid var(--dm-warning);
}

.thinking-title {
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}

.thinking-title i:last-child {
  margin-left: auto;
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.thinking-content {
  margin-top: 8px;
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 引用来源 */
.sources-box {
  margin-top: var(--dm-space-3);
  padding: 12px 16px;
  background: var(--dm-primary-light);
  border-radius: var(--dm-radius-sm);
  border-left: 3px solid var(--dm-primary);
}

.sources-title {
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}

.sources-title i:last-child {
  margin-left: auto;
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.sources-list {
  margin-top: 8px;
}

.source-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 0;
  border-bottom: 1px solid var(--dm-border-light);
}

.source-item:last-child {
  border-bottom: none;
}

.source-header {
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
}

.source-index {
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
  font-size: var(--dm-text-2xs);
  background: var(--dm-bg-elevated);
  padding: 1px 6px;
  border-radius: var(--dm-radius-sm);
  flex-shrink: 0;
}

.source-doc {
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-primary);
  font-size: var(--dm-text-2xs);
}

.source-doc i {
  margin-right: 4px;
  font-size: var(--dm-text-3xs);
}

.source-page {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.source-content {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  line-height: var(--dm-leading-body);
  padding: 8px 12px;
  background: var(--dm-bg-page);
  border-radius: var(--dm-radius-xs);
  border-left: 2px solid var(--dm-border);
  word-break: break-word;
}

.source-content.placeholder {
  color: var(--dm-text-tertiary);
  font-style: italic;
}

/* 操作栏 */
.message-actions {
  display: flex;
  gap: var(--dm-space-2);
  margin-top: var(--dm-space-2);
  opacity: 0;
  transition: opacity var(--dm-transition-fast);
}

.message-item:hover .message-actions {
  opacity: 1;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: none;
  background: transparent;
  color: var(--dm-text-tertiary);
  font-size: var(--dm-text-2xs);
  cursor: pointer;
  border-radius: var(--dm-radius-xs);
  transition: all var(--dm-transition-fast);
}

.action-btn:hover {
  background: var(--dm-bg-page);
  color: var(--dm-text-primary);
}
</style>
