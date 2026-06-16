<template>
  <div class="admin-page">
    <!-- 加载中 -->
    <div v-if="loading" v-loading="loading" style="min-height: 300px;"></div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="empty-state">
      <i class="fas fa-exclamation-circle empty-icon" style="color: var(--dm-danger);"></i>
      <div class="empty-title">加载失败</div>
      <div class="empty-desc">{{ error }}</div>
      <button class="back-btn" @click="goBack">
        <i class="fas fa-arrow-left"></i> 返回列表
      </button>
    </div>

    <!-- 内容 -->
    <template v-else-if="trace">
      <!-- 顶部导航 -->
      <div class="detail-nav">
        <button class="back-btn" @click="goBack">
          <i class="fas fa-arrow-left"></i> 返回列表
        </button>
        <span class="trace-id-full">
          Trace: <code>{{ trace.trace_id }}</code>
        </span>
      </div>

      <!-- 基本信息卡片 -->
      <div class="info-card">
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">用户</span>
            <span
              class="info-value link"
              @click="goToUser(trace.user_id)"
            >
              {{ trace.username || `用户#${trace.user_id}` }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">会话</span>
            <span v-if="trace.conversation_uuid" class="info-value">
              {{ trace.conversation_title || '—' }}
              <span class="conversation-id-hint">(UUID: {{ trace.conversation_uuid }})</span>
            </span>
            <span v-else class="info-value">--</span>
          </div>
          <div class="info-item">
            <span class="info-label">知识库</span>
            <span class="info-value">{{ trace.kb_name || '--' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">耗时</span>
            <span class="info-value duration">{{ formatDuration(trace.total_duration_ms) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">意图</span>
            <span
              v-if="trace.intent_type"
              class="intent-tag"
              :class="trace.intent_type.toLowerCase()"
            >
              {{ intentLabel(trace.intent_type) }}
              <span v-if="trace.intent_method" class="method-hint">({{ trace.intent_method }})</span>
            </span>
            <span v-else class="info-value">--</span>
          </div>
          <div class="info-item">
            <span class="info-label">响应模式</span>
            <span
              v-if="trace.response_mode"
              class="response-tag"
              :class="trace.response_mode.toLowerCase()"
            >
              {{ responseLabel(trace.response_mode) }}
            </span>
            <span v-else class="info-value">--</span>
          </div>
          <div class="info-item">
            <span class="info-label">状态</span>
            <span class="info-value">
              <span class="status-icon">{{ statusEmoji(trace.status) }}</span>
              {{ statusLabel(trace.status) }}
            </span>
          </div>
        </div>
        <div class="info-question">
          <span class="info-label">问题</span>
          <span class="question-text">{{ trace.question || '--' }}</span>
        </div>
      </div>

      <!-- 阶段概览标题 -->
      <h3 class="section-title">阶段概览</h3>

      <!-- 5 阶段卡片 -->
      <div class="stages-grid">
        <div
          v-for="stage in stages"
          :key="stage.key"
          class="stage-card"
          :class="{ 'has-error': stage.data?.status === 'error' }"
        >
          <div class="stage-header">
            <span class="stage-name">{{ stage.label }}</span>
            <span class="stage-status">{{ stageStatusEmoji(stage.data?.status) }}</span>
          </div>
          <div class="stage-duration">
            {{ formatDuration(stage.data?.duration_ms) }}
          </div>
          <div class="stage-meta">
            <span v-if="stage.key === 'intent' && trace.intent_method" class="stage-meta-item">
              {{ trace.intent_method }}
            </span>
            <span v-if="stage.key === 'generate' && stage.data?.model" class="stage-meta-item">
              {{ stage.data.model }}
            </span>
            <span v-if="stage.key === 'generate' && stage.data?.ttft_ms != null" class="stage-meta-item">
              TTFT: {{ stage.data.ttft_ms }}ms
            </span>
            <span v-if="stage.key === 'retrieve' && stage.data?.fusion?.method" class="stage-meta-item">
              {{ stage.data.fusion.method.toUpperCase() }}
            </span>
            <span v-if="stage.key === 'rerank' && stage.data?.metadata?.reranker" class="stage-meta-item">
              {{ stage.data.metadata.reranker }}
            </span>
            <span v-if="stage.key === 'evidence_review' && stage.data?.summary" class="stage-meta-item"
                  :class="{ 'reject': stage.data.summary.decision === 'REJECT' }">
              {{ stage.data.summary.decision === 'REJECT' ? 'REJECT' : 'ALLOW' }}
              ({{ stage.data.summary.assertive_count }}A / {{ stage.data.summary.referential_count + stage.data.summary.rejected_count }}R)
            </span>
          </div>
          <button
            class="stage-json-btn"
            @click="toggleJson(stage.key)"
          >
            <i :class="expandedJson[stage.key] ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
            {{ expandedJson[stage.key] ? '收起JSON' : '查看JSON' }}
          </button>
        </div>
      </div>

      <!-- JSON 展开面板 -->
      <template v-for="stage in stages" :key="'json-' + stage.key">
        <div v-if="expandedJson[stage.key] && stage.data" class="json-panel">
          <div class="json-panel-header">
            <span class="json-panel-title">{{ stage.label }} 详情</span>
            <button class="json-copy-btn" @click="copyJson(stage.data)">
              <i class="fas fa-copy"></i> 复制
            </button>
          </div>
          <pre class="json-content" v-html="highlightJson(stage.data)"></pre>
        </div>
      </template>

      <!-- 错误信息 -->
      <div v-if="trace.error_message" class="error-panel">
        <div class="error-panel-header">
          <i class="fas fa-exclamation-triangle"></i>
          <span>错误信息</span>
        </div>
        <pre class="error-content">{{ trace.error_message }}</pre>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTraceDetail } from '@/api/trace'
import hljs from 'highlight.js/lib/core'
import json from 'highlight.js/lib/languages/json'

// 注册 JSON 语言
hljs.registerLanguage('json', json)

const router = useRouter()
const route = useRoute()

// ==================== 数据 ====================
const loading = ref(true)
const error = ref('')
const trace = ref(null)
const expandedJson = reactive({
  intent: false,
  rewrite: false,
  retrieve: false,
  rerank: false,
  evidence_review: false,
  generate: false,
})

// 阶段配置
const stages = computed(() => {
  if (!trace.value) return []
  return [
    { key: 'intent', label: 'Intent', data: trace.value.intent },
    { key: 'rewrite', label: 'Rewrite', data: trace.value.rewrite },
    { key: 'retrieve', label: 'Retrieve', data: trace.value.retrieve },
    { key: 'rerank', label: 'Rerank', data: trace.value.rerank },
    { key: 'evidence_review', label: 'Evidence', data: trace.value.evidence_review },
    { key: 'generate', label: 'Generate', data: trace.value.generate },
  ]
})

// ==================== 数据加载 ====================
async function loadDetail() {
  const traceId = route.params.trace_id
  if (!traceId) {
    error.value = '缺少 trace_id 参数'
    loading.value = false
    return
  }

  try {
    const { data } = await getTraceDetail(traceId)
    if (data.code === '0') {
      trace.value = data.data
    } else {
      error.value = data.message || '获取 Trace 详情失败'
    }
  } catch (e) {
    error.value = e.response?.data?.message || '网络异常，请稍后重试'
  } finally {
    loading.value = false
  }
}

// ==================== 交互 ====================
function goBack() {
  router.push('/admin/traces')
}

function goToUser(userId) {
  router.push(`/admin/users/${userId}`)
}

function toggleJson(key) {
  expandedJson[key] = !expandedJson[key]
}

async function copyJson(data) {
  try {
    await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    ElMessage.success('JSON 已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

// ==================== 工具函数 ====================
function formatDuration(ms) {
  if (ms == null) return '--'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function highlightJson(obj) {
  const jsonStr = JSON.stringify(obj, null, 2)
  const result = hljs.highlight(jsonStr, { language: 'json' })
  // 防御层：剥离 highlight.js 可能引入的非 span 标签（如 <script>），
  // JSON.stringify 已转义数据中的 HTML 实体，此层为纵深防御
  return result.value.replace(/<(?!\/?span[ >])[^>]*>/gi, '')
}

function statusEmoji(status) {
  const map = { success: '✅', error: '❌', partial: '⚠️' }
  return map[status] || '--'
}

function statusLabel(status) {
  const map = { success: '成功', error: '失败', partial: '部分成功' }
  return map[status] || status
}

function intentLabel(type) {
  const map = { KNOWLEDGE: '知识问答', CASUAL: '闲聊', META: '元查询' }
  return map[type] || type
}

function responseLabel(mode) {
  const map = { RAG: 'RAG', DIRECT_LLM: '直接 LLM', META: '元查询', CASUAL: '闲聊', FALLBACK: '兜底回复', REJECT: '证据驳回' }
  return map[mode] || mode
}

function stageStatusEmoji(status) {
  const map = { success: '✅', error: '❌' }
  return map[status] || '⏳'
}

onMounted(loadDetail)
</script>

<style scoped>
.admin-page {
  max-width: var(--dm-content-max-width);
  margin: 0 auto;
}

/* 顶部导航 */
.detail-nav {
  display: flex;
  align-items: center;
  gap: var(--dm-space-4);
  margin-bottom: var(--dm-space-5);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-2);
  padding: 6px 12px;
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-sm);
  background: var(--dm-bg-card);
  color: var(--dm-text-secondary);
  font-size: var(--dm-text-body);
  cursor: pointer;
  transition: all var(--dm-transition-fast);
}

.back-btn:hover {
  border-color: var(--dm-primary);
  color: var(--dm-primary);
}

.trace-id-full {
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
}

.trace-id-full code {
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-xs);
  color: var(--dm-text-primary);
  background: var(--dm-bg-page);
  padding: 2px 6px;
  border-radius: var(--dm-radius-xs);
  user-select: all;
}

/* 基本信息卡片 */
.info-card {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-5);
  margin-bottom: var(--dm-space-6);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--dm-space-4);
  margin-bottom: var(--dm-space-4);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--dm-space-1);
}

.info-label {
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-tertiary);
  font-weight: var(--dm-weight-medium);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: var(--dm-text-body);
  color: var(--dm-text-primary);
  font-weight: var(--dm-weight-medium);
}

.info-value.link {
  color: var(--dm-info);
  cursor: pointer;
  transition: color var(--dm-transition-fast);
}

.info-value.link:hover {
  color: var(--dm-primary);
  text-decoration: underline;
}

.info-value.duration {
  font-family: var(--dm-font-mono);
}

.conversation-id-hint {
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-tertiary);
  font-weight: var(--dm-weight-normal);
}

.info-question {
  display: flex;
  flex-direction: column;
  gap: var(--dm-space-1);
  padding-top: var(--dm-space-3);
  border-top: 1px solid var(--dm-border-light);
}

.question-text {
  font-size: var(--dm-text-body);
  color: var(--dm-text-primary);
  line-height: var(--dm-leading-body);
}

/* 意图/响应标签 */
.intent-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
}

.intent-tag.knowledge {
  background: var(--dm-info-light);
  color: var(--dm-info);
}

.intent-tag.casual {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.intent-tag.meta {
  background: var(--dm-bg-page);
  color: var(--dm-text-tertiary);
}

.method-hint {
  font-weight: var(--dm-weight-normal);
  opacity: 0.8;
}

.response-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
  background: var(--dm-bg-page);
  color: var(--dm-text-secondary);
}

.response-tag.rag {
  background: var(--dm-info-light);
  color: var(--dm-info);
}

.response-tag.direct_llm {
  background: var(--dm-warning-light);
  color: var(--dm-warning);
}

.response-tag.meta {
  background: var(--dm-bg-page);
  color: var(--dm-text-tertiary);
}

.response-tag.casual {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.response-tag.fallback {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

.response-tag.reject {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

.status-icon {
  font-size: var(--dm-text-base);
  margin-right: var(--dm-space-1);
}

/* 阶段概览 */
.section-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-4);
}

.stages-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--dm-space-4);
  margin-bottom: var(--dm-space-5);
}

.stage-card {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--dm-space-2);
  transition: border-color var(--dm-transition-fast);
}

.stage-card:hover {
  border-color: var(--dm-text-tertiary);
}

.stage-card.has-error {
  border-color: var(--dm-danger);
  background: var(--dm-danger-light);
}

.stage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stage-name {
  font-size: var(--dm-text-sm);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

.stage-status {
  font-size: var(--dm-text-base);
}

.stage-duration {
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-lg);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.stage-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.stage-meta-item {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
  background: var(--dm-bg-page);
  padding: 1px 6px;
  border-radius: var(--dm-radius-xs);
}

.stage-meta-item.reject {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
  font-weight: var(--dm-weight-semibold);
}

.stage-json-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid var(--dm-border-light);
  border-radius: var(--dm-radius-xs);
  background: transparent;
  color: var(--dm-text-tertiary);
  font-size: var(--dm-text-2xs);
  cursor: pointer;
  transition: all var(--dm-transition-fast);
  margin-top: auto;
}

.stage-json-btn:hover {
  border-color: var(--dm-info);
  color: var(--dm-info);
}

/* JSON 面板 */
.json-panel {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  margin-bottom: var(--dm-space-4);
  overflow: hidden;
}

.json-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--dm-space-3) var(--dm-space-4);
  border-bottom: 1px solid var(--dm-border-light);
  background: var(--dm-bg-page);
}

.json-panel-title {
  font-size: var(--dm-text-sm);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

.json-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-xs);
  background: var(--dm-bg-card);
  color: var(--dm-text-secondary);
  font-size: var(--dm-text-2xs);
  cursor: pointer;
  transition: all var(--dm-transition-fast);
}

.json-copy-btn:hover {
  border-color: var(--dm-info);
  color: var(--dm-info);
}

.json-content {
  padding: var(--dm-space-4);
  margin: 0;
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-2xs);
  line-height: 1.6;
  color: var(--dm-text-primary);
  background: var(--dm-bg-code);
  overflow-x: auto;
  white-space: pre;
  max-height: 400px;
  overflow-y: auto;
}

/* highlight.js 深色主题下的 JSON token 样式 */
.json-content :deep(.hljs-string) {
  color: var(--dm-json-string);
}

.json-content :deep(.hljs-number) {
  color: var(--dm-json-number);
}

.json-content :deep(.hljs-literal) {
  color: var(--dm-json-literal);
}

.json-content :deep(.hljs-keyword) {
  color: var(--dm-json-keyword);
}

/* 错误面板 */
.error-panel {
  background: var(--dm-danger-light);
  border: 1px solid var(--dm-danger);
  border-radius: var(--dm-radius-md);
  margin-top: var(--dm-space-5);
  overflow: hidden;
}

.error-panel-header {
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
  padding: var(--dm-space-3) var(--dm-space-4);
  border-bottom: 1px solid rgba(239, 68, 68, 0.2);
  color: var(--dm-danger);
  font-size: var(--dm-text-sm);
  font-weight: var(--dm-weight-semibold);
}

.error-content {
  padding: var(--dm-space-4);
  margin: 0;
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-2xs);
  line-height: 1.6;
  color: var(--dm-danger);
  white-space: pre-wrap;
  word-break: break-all;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: var(--dm-space-12) var(--dm-space-5);
  color: var(--dm-text-tertiary);
}

.empty-icon {
  font-size: var(--dm-empty-icon-size);
  margin-bottom: var(--dm-space-4);
  opacity: 0.5;
}

.empty-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-2);
}

.empty-desc {
  font-size: var(--dm-text-body);
  margin-bottom: var(--dm-space-4);
}
</style>
