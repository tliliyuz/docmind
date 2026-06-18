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
          ref="markdownBody"
          class="markdown-body"
          v-html="renderedContent"
        ></div>

        <!-- 错误状态 -->
        <div v-if="msg.status === 'error' && msg.error" class="error-content">
          <i class="fas fa-exclamation-circle"></i>
          <span>{{ msg.error }}</span>
        </div>
      </div>

      <!-- 置信度警告（证据审计发现问题时展示，§4.2.5） -->
      <div v-if="msg.role === 'assistant' && showConfidenceWarning" class="confidence-warning">
        <div class="confidence-warning-header">
          <i class="fas fa-exclamation-triangle"></i>
          <span>{{ confidenceWarningText }}</span>
        </div>
        <div v-if="msg.confidenceNote" class="confidence-warning-detail">
          {{ msg.confidenceNote }}
        </div>
      </div>

      <!-- 引用来源（仅 assistant + 有 sources + LLM 未声明"未找到"时） -->
      <div v-if="msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && !isAnswerNotFound" class="sources-box">
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
              <span class="source-index">[来源{{ idx + 1 }}]</span>
              <span class="source-doc">
                <i class="fas fa-file-alt"></i>
                {{ src.doc_name || '未知文档' }}
              </span>
              <span v-if="src.section_path || src.section_title" class="source-section">
                <i class="fas fa-list-ul"></i>
                {{ src.section_path || src.section_title }}
              </span>
              <span v-if="src.page" class="source-page">第{{ src.page }}页</span>
            </div>
            <!-- 智能预览：优先使用 preview_text 定位展示，降级回 content 前 200 字符 -->
            <div
              v-if="src.preview_text || src.content"
              class="source-content"
              v-html="getSourcePreviewHtml(src)"
            ></div>
            <div v-else class="source-content placeholder">（无法获取片段内容）</div>
          </div>
        </div>
      </div>

      <!-- 操作栏（仅 assistant 完成后 hover 显示，孤儿会话隐藏重新生成） -->
      <div v-if="msg.role === 'assistant' && msg.status === 'complete' && !chatStore.isKbOrphaned && !chatStore.isKbEmpty" class="message-actions">
        <button class="action-btn" title="重新生成" @click="$emit('regenerate')">
          <i class="fas fa-redo"></i>
          <span>重新生成</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { renderMarkdown, wrapCodeBlocks } from '@/utils/markdown'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const props = defineProps({
  msg: { type: Object, required: true },
})

defineEmits(['regenerate'])

const thinkingExpanded = ref(true)
const sourcesExpanded = ref(true)
const markdownBody = ref(null)

const renderedContent = computed(() => {
  if (!props.msg.content) return ''
  const html = renderMarkdown(props.msg.content)
  return wrapCodeBlocks(html)
})

/** 代码复制按钮点击事件委托（替代内联 onclick，兼容 CSP） */
function handleCodeCopyClick(event) {
  const btn = event.target.closest('.code-copy-btn')
  if (!btn) return

  const wrapper = btn.closest('.code-block-wrapper')
  if (!wrapper) return

  const code = wrapper.querySelector('code')
  if (!code) return

  navigator.clipboard.writeText(code.textContent).then(() => {
    btn.classList.add('copied')
    setTimeout(() => btn.classList.remove('copied'), 1500)
  })
}

onMounted(() => {
  if (markdownBody.value) {
    markdownBody.value.addEventListener('click', handleCodeCopyClick)
  }
})

onBeforeUnmount(() => {
  if (markdownBody.value) {
    markdownBody.value.removeEventListener('click', handleCodeCopyClick)
  }
})

/** 来源中去重的文档数量 */
const uniqueDocCount = computed(() => {
  if (!props.msg.sources) return 0
  const docIds = new Set(props.msg.sources.map(s => s.doc_id).filter(Boolean))
  return docIds.size
})

/** LLM 回答是否声明"未找到相关信息"（此时应抑制来源展示）
    对齐 API.md §6.1：LLM 判定文档不相关时 sources 事件不发送，
    前端作为安全网兜同样逻辑。 */
const isAnswerNotFound = computed(() => {
  if (!props.msg.content) return false
  return props.msg.content.includes('未找到相关信息') ||
    props.msg.content.includes('知识库中未找到')
})

/** 是否展示置信度警告（证据审计发现问题时，§4.2.5） */
const showConfidenceWarning = computed(() => {
  if (!props.msg.confidence) return false
  return props.msg.confidence === 'low' || props.msg.confidence === 'medium'
})

/** 置信度警告文案 */
const confidenceWarningText = computed(() => {
  if (props.msg.confidence === 'low') {
    return '以下答案可能存在偏差，建议核实原始文档。'
  }
  return '以下答案部分内容可能不准确，请注意核实。'
})

// ==================== Sources 智能预览 ====================
// 对齐 ARCHITECTURE.md §5.1.7 前端渲染规格
// Evidence Highlight：后端计算 highlight_start/end，前端纯切片渲染

/** HTML 转义（防 XSS，v-html 渲染前对用户可控文本转义） */
function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
  return String(text).replace(/[&<>"']/g, c => map[c])
}

/**
 * 生成来源预览 HTML（含 <mark> 高亮）
 *
 * 后端已通过 BM25 句级定位计算 highlight_start / highlight_end，
 * 前端纯切片渲染，不做任何匹配逻辑。
 *
 * @param {Object} src — 来源 chunk 对象（含 preview_text / highlight_start / highlight_end）
 * @returns {string} — 转义后的 HTML 字符串
 */
function getSourcePreviewHtml(src) {
  const displayText = src.preview_text || (src.content || '').slice(0, 200)
  if (!displayText) return ''

  const markStyle = 'background:var(--dm-evidence-highlight-bg);color:var(--dm-text-primary);padding:1px 3px;border-radius:2px;box-decoration-break:clone'

  // 后端已计算高亮区间，直接切片渲染
  if (src.preview_text && src.highlight_start != null && src.highlight_end != null) {
    const s = Math.max(0, src.highlight_start)
    const e = Math.min(displayText.length, src.highlight_end)
    if (s < e) {
      const before = escapeHtml(displayText.slice(0, s))
      const matched = escapeHtml(displayText.slice(s, e))
      const after = escapeHtml(displayText.slice(e))
      return `${before}<mark style="${markStyle}">${matched}</mark>${after}`
    }
  }

  // 无高亮区间：纯文本展示
  return escapeHtml(displayText)
}
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
  width: var(--dm-space-9);
  height: var(--dm-space-9);
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
  margin-bottom: var(--dm-space-1_5);
}

.message-name {
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

/* 消息气泡 */
.message-bubble {
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-3_5) 18px;
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
  gap: var(--dm-space-1);
  padding: var(--dm-space-3) 0;
}

.typing-dot {
  width: var(--dm-space-2);
  height: var(--dm-space-2);
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
  margin: var(--dm-space-3) 0 var(--dm-space-2);
  line-height: var(--dm-leading-title);
  font-weight: var(--dm-weight-bold);
}

.markdown-body :deep(h1) { font-size: var(--dm-text-lg); }
.markdown-body :deep(h2) { font-size: var(--dm-text-base); }
.markdown-body :deep(h3) { font-size: var(--dm-text-body); }

.markdown-body :deep(p) {
  margin: var(--dm-space-2) 0;
  line-height: var(--dm-leading-chat);
}

.markdown-body :deep(strong) {
  font-weight: var(--dm-weight-semibold);
}

.markdown-body :deep(code:not(pre code)) {
  background: var(--dm-code-inline-bg);
  padding: 2px var(--dm-space-1_5);
  border-radius: var(--dm-radius-xs);
  font-family: var(--dm-font-mono);
  font-size: var(--dm-code-inline-font-size);
}

.markdown-body :deep(pre) {
  margin: var(--dm-space-3) 0;
  border-radius: var(--dm-radius-sm);
  overflow: hidden;
}

.markdown-body :deep(pre code) {
  display: block;
  background: var(--dm-bg-code);
  color: var(--dm-text-code);
  padding: var(--dm-space-4);
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-xs);
  line-height: 1.6;
  overflow-x: auto;
}

.markdown-body :deep(blockquote) {
  margin: var(--dm-space-3) 0;
  padding: var(--dm-space-2) var(--dm-space-4);
  border-left: 3px solid var(--dm-primary);
  background: var(--dm-primary-light);
  border-radius: 0 var(--dm-radius-xs) var(--dm-radius-xs) 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: var(--dm-space-2) 0;
  padding-left: var(--dm-space-6);
}

.markdown-body :deep(li) {
  margin: var(--dm-space-1) 0;
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
  top: var(--dm-space-2);
  right: var(--dm-space-2);
  width: var(--dm-space-8);
  height: var(--dm-space-8);
  background: var(--dm-code-copy-btn-bg);
  border: none;
  border-radius: var(--dm-radius-xs);
  color: var(--dm-text-tertiary);
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
  background: var(--dm-code-copy-btn-hover-bg);
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
  padding: var(--dm-space-3) var(--dm-space-4);
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
  gap: var(--dm-space-1_5);
  cursor: pointer;
  user-select: none;
}

.thinking-title i:last-child {
  margin-left: auto;
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.thinking-content {
  margin-top: var(--dm-space-2);
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 置信度警告（证据审计发现，§4.2.5） */
.confidence-warning {
  margin-top: var(--dm-space-3);
  padding: var(--dm-space-3) var(--dm-space-4);
  background: var(--dm-warning-light);
  border-radius: var(--dm-radius-sm);
  border-left: 3px solid var(--dm-warning);
}

.confidence-warning-header {
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-warning-dark);
}

.confidence-warning-header i {
  font-size: var(--dm-text-body);
  flex-shrink: 0;
}

.confidence-warning-detail {
  margin-top: var(--dm-space-1_5);
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-secondary);
  line-height: var(--dm-leading-body);
}

/* 引用来源 */
.sources-box {
  margin-top: var(--dm-space-3);
  padding: var(--dm-space-3) var(--dm-space-4);
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
  gap: var(--dm-space-1_5);
  cursor: pointer;
  user-select: none;
}

.sources-title i:last-child {
  margin-left: auto;
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.sources-list {
  margin-top: var(--dm-space-2);
}

.source-item {
  display: flex;
  flex-direction: column;
  gap: var(--dm-space-1_5);
  padding: var(--dm-space-2_5) 0;
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
  padding: 1px var(--dm-space-1_5);
  border-radius: var(--dm-radius-sm);
  flex-shrink: 0;
}

.source-doc {
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-primary);
  font-size: var(--dm-text-2xs);
}

.source-doc i {
  margin-right: var(--dm-space-1);
  font-size: var(--dm-text-3xs);
}

.source-page {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.source-section {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.source-section i {
  margin-right: var(--dm-space-1);
  font-size: var(--dm-text-3xs);
}

.source-content {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  line-height: var(--dm-leading-body);
  padding: var(--dm-space-2) var(--dm-space-3);
  background: var(--dm-bg-page);
  border-radius: var(--dm-radius-xs);
  border-left: 2px solid var(--dm-border);
  word-break: break-word;
}

.source-content.placeholder {
  color: var(--dm-text-tertiary);
  font-style: italic;
}

/* 智能预览高亮标记（v-html 渲染，需 :deep() 穿透）
   对齐 ARCHITECTURE.md §5.1.7：引用片段用 <mark> 黄色背景高亮 */
.source-content :deep(mark) {
  background: var(--dm-evidence-highlight-bg);
  color: var(--dm-text-primary);
  padding: 1px 3px;
  border-radius: 2px;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
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
  gap: var(--dm-space-1);
  padding: var(--dm-space-1) var(--dm-space-2);
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
