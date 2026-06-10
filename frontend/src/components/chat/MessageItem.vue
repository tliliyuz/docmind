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
              <span class="source-index">[来源{{ src.chunk_index || idx + 1 }}]</span>
              <span class="source-doc">
                <i class="fas fa-file-alt"></i>
                {{ src.doc_name || '未知文档' }}
              </span>
              <span v-if="src.page" class="source-page">第{{ src.page }}页</span>
            </div>
            <!-- 智能预览：优先使用 preview_text 定位展示，降级回 content 前 200 字符 -->
            <div
              v-if="src.preview_text || src.content"
              class="source-content"
              v-html="getSourcePreviewHtml(src, msg.content)"
            ></div>
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
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { renderMarkdown, wrapCodeBlocks } from '@/utils/markdown'

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

// ==================== Sources 智能预览 ====================
// 对齐 ARCHITECTURE.md §5.1.7 前端渲染规格

/** HTML 转义（防 XSS，v-html 渲染前对用户可控文本转义） */
function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
  return String(text).replace(/[&<>"']/g, c => map[c])
}

/**
 * 从 LLM 回答中提取 [来源N] 后的引用片段（对齐后端 _locate_preview 逻辑）
 * @param {number} chunkIndex — 来源编号
 * @param {string} assistantContent — LLM 完整回答
 * @returns {string|null} — 提取到的搜索片段（≤50 字符），失败返回 null
 */
function extractSnippet(chunkIndex, assistantContent) {
  const pattern = new RegExp(`\\[来源${chunkIndex}\\]([^\\[]*)`)
  const match = pattern.exec(assistantContent)
  if (!match) return null

  let snippet = match[1].trim()
  // 去除可能混入的其他 [来源M] 标记（对齐后端 re.sub(r'\[来源\d+\]', '', snippet)）
  snippet = snippet.replace(/\[来源\d+\]/g, '').trim()
  if (snippet.length < 4) return null

  // 跳过开头的标点符号
  snippet = snippet.replace(/^[，,。！？\s]+/, '')
  // 截取前 50 字符作为搜索关键词
  snippet = snippet.slice(0, 50)
  // 清理尾部不完整的词/标点
  snippet = snippet.replace(/[，,。！？\s]+$/, '')

  return snippet.length >= 3 ? snippet : null
}

/**
 * 空白字符规范化：将所有连续空白（空格/换行/制表符等）替换为单个空格。
 * 对齐后端 _locate_preview 的 re.sub(r'\s+', ' ', ...) 逻辑。
 */
function normalizeWhitespace(text) {
  return text.replace(/\s+/g, ' ')
}

/**
 * 构建原始文本 → 规范化文本的字符位置映射。
 * normPosMap[normalizedIdx] = originalIdx
 * 用于在规范化匹配成功后回溯到原始文本位置。
 */
function buildNormPosMap(original) {
  const map = []
  for (let i = 0; i < original.length; i++) {
    if (/\s/.test(original[i])) {
      // 连续空白只映射第一个字符到规范化位置
      if (i === 0 || !/\s/.test(original[i - 1])) {
        map.push(i)
      }
    } else {
      map.push(i)
    }
  }
  return map
}

/** 判断是否为规范化空白序列的起始位置（非空白 或 连续空白的首个） */
function isNormCharStart(original, pos) {
  return !/\s/.test(original[pos]) || pos === 0 || !/\s/.test(original[pos - 1])
}

/**
 * 生成来源预览 HTML（含 <mark> 高亮）
 * 优先使用 preview_text（后端定位的 ±100 字符上下文窗口），
 * 降级使用 content 前 200 字符。
 *
 * 匹配策略：规范化空白字符后匹配（对齐后端 _locate_preview 的 re.sub(r'\s+', ' ', ...)），
 * 解决 LLM 回答含 \n 而 chunk 原始文本含空格的不一致问题。
 *
 * @param {Object} src — 来源 chunk 对象
 * @param {string} assistantContent — LLM 完整回答（用于提取引用片段）
 * @returns {string} — 转义后的 HTML 字符串
 */
function getSourcePreviewHtml(src, assistantContent) {
  // 1. 确定展示文本：优先 preview_text，降级 content 前 200 字符
  const displayText = src.preview_text || (src.content || '').slice(0, 200)

  if (!displayText) return ''

  // 2. 尝试提取 LLM 引用片段并在展示文本中定位
  //    同时尝试两种模式：A) [来源N]后跟文字 B) 文字后跟[来源N]
  if (src.preview_text && assistantContent) {
    let snippet = extractSnippet(src.chunk_index, assistantContent)
    if (!snippet) {
      // 回退：尝试匹配「文字[来源N]」模式（LLM 将引用标在句末）
      snippet = extractSnippetAfter(src.chunk_index, assistantContent)
    }
    if (snippet) {
      // 规范化空白后匹配（对齐后端 _locate_preview 的 re.sub(r'\s+', ' ', ...)）
      // LLM 回答中 snippet 含 \n，chunk 原始文本含空格，需统一处理
      const normSnippet = normalizeWhitespace(snippet).toLowerCase()
      const normDisplay = normalizeWhitespace(displayText).toLowerCase()

      const normIdx = normDisplay.indexOf(normSnippet)
      if (normIdx >= 0) {
        // 规范化匹配成功 → 回溯到原始文本位置
        const posMap = buildNormPosMap(displayText)
        const origStart = posMap[normIdx]
        // 计算原始文本中的结束位置：规范化 snippet 长度对应的原始范围
        let origEnd = origStart
        let normCount = 0
        for (let i = origStart; i < displayText.length && normCount < normSnippet.length; i++) {
          if (isNormCharStart(displayText, i)) {
            normCount++
          }
          origEnd = i + 1
        }

        const before = escapeHtml(displayText.slice(0, origStart))
        const matched = escapeHtml(displayText.slice(origStart, origEnd))
        const after = escapeHtml(displayText.slice(origEnd))
        // 使用内联样式确保黄色高亮在任何 CSS 环境下可见
        const markStyle = 'background:#FFE082;color:#1A1A1A;padding:1px 3px;border-radius:2px;box-decoration-break:clone'
        return `${before}<mark style="${markStyle}">${matched}</mark>${after}`
      }
    }
  }

  // 3. 无匹配或降级场景：纯文本展示
  return escapeHtml(displayText)
}

/**
 * 回退提取：「文字[来源N]」模式 — LLM 将引用标在引用句末尾
 * 取 [来源N] 前 50 字符作为搜索片段
 */
function extractSnippetAfter(chunkIndex, assistantContent) {
  const pattern = new RegExp(`(.{1,50})\\[来源${chunkIndex}\\]`)
  const match = pattern.exec(assistantContent)
  if (!match) return null

  let snippet = match[1].trim()
  snippet = snippet.replace(/^[，,。！？\s]+/, '')
  snippet = snippet.replace(/[，,。！？\s]+$/, '')
  return snippet.length >= 3 ? snippet : null
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
  background: var(--dm-code-inline-bg);
  padding: 2px 6px;
  border-radius: var(--dm-radius-xs);
  font-family: var(--dm-font-mono);
  font-size: var(--dm-code-inline-font-size);
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

/* 智能预览高亮标记（v-html 渲染，需 :deep() 穿透）
   对齐 ARCHITECTURE.md §5.1.7：引用片段用 <mark> 黄色背景高亮
   使用可见黄色替代 --dm-warning-light（#FFFBEB 过淡不可辨） */
.source-content :deep(mark) {
  background: #FFF3B0;
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
