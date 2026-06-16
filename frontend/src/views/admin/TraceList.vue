<template>
  <div class="admin-page">
    <!-- 页面描述 -->
    <div class="detail-header">
      <p class="detail-desc">查看问答链路追踪记录，分析各阶段耗时与状态</p>
    </div>

    <!-- 概览卡片 -->
    <div class="stat-cards-row">
      <div class="stat-card">
        <div class="stat-icon success">
          <i class="fas fa-check-circle"></i>
        </div>
        <div>
          <div class="stat-value">
            {{ summary.success }} <span class="stat-sep">/</span>
            {{ summary.error }} <span class="stat-sep">/</span>
            {{ summary.running }}
          </div>
          <div class="stat-label">成功 / 失败 / 运行中</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon primary">
          <i class="fas fa-percentage"></i>
        </div>
        <div>
          <div class="stat-value">{{ summary.success_rate }}%</div>
          <div class="stat-label">成功率</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon warning">
          <i class="fas fa-clock"></i>
        </div>
        <div>
          <div class="stat-value">{{ formatSummaryDuration(summary.avg_duration_ms) }} <span class="stat-unit">s</span></div>
          <div class="stat-label">平均耗时</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon danger">
          <i class="fas fa-tachometer-alt"></i>
        </div>
        <div>
          <div class="stat-value">{{ formatSummaryDuration(summary.p95_duration_ms) }} <span class="stat-unit">s</span></div>
          <div class="stat-label">P95 耗时</div>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-input
          v-model="searchText"
          placeholder="搜索问题..."
          size="default"
          clearable
          class="filter-input-lg"
          @input="onSearchInput"
          @clear="onSearchClear"
        >
          <template #prefix>
            <i class="fas fa-search search-icon"></i>
          </template>
        </el-input>
        <el-select
          v-model="filterStatus"
          placeholder="状态"
          clearable
          size="default"
          class="filter-input-sm"
          @change="reloadList"
        >
          <el-option label="全部" value="" />
          <el-option label="成功" value="success" />
          <el-option label="失败" value="error" />
          <el-option label="部分" value="partial" />
        </el-select>
        <el-select
          v-model="filterIntent"
          placeholder="意图"
          clearable
          size="default"
          class="filter-input-st"
          @change="reloadList"
        >
          <el-option label="全部" value="" />
          <el-option label="知识问答" value="KNOWLEDGE" />
          <el-option label="闲聊" value="CASUAL" />
          <el-option label="元查询" value="META" />
        </el-select>
        <el-select
          v-model="filterResponse"
          placeholder="响应模式"
          clearable
          size="default"
          class="filter-input-md"
          @change="reloadList"
        >
          <el-option label="全部" value="" />
          <el-option label="RAG" value="RAG" />
          <el-option label="直接 LLM 回答" value="DIRECT_LLM" />
          <el-option label="元查询" value="META" />
          <el-option label="闲聊" value="CASUAL" />
          <el-option label="兜底回复" value="FALLBACK" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          size="default"
          class="filter-input-xxl"
          :clearable="true"
          @change="reloadList"
        />
        <span v-if="total > 0" class="total-hint">共 {{ total }} 条记录</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && list.length === 0" class="empty-state">
      <i class="fas fa-search empty-icon"></i>
      <div class="empty-title">暂无 Trace 记录</div>
      <div class="empty-desc">系统中还没有任何链路追踪数据</div>
    </div>

    <!-- 表格 -->
    <el-table
      v-else
      :data="list"
      v-loading="loading"
      class="table-full"
      row-key="trace_id"
      highlight-current-row
      @row-click="goToDetail"
    >
      <el-table-column label="Trace ID" width="110" align="center">
        <template #default="{ row }">
          <span
            class="trace-id-cell"
            :title="row.trace_id"
            @click.stop="copyTraceId(row.trace_id)"
          >
            {{ row.trace_id.slice(0, 8) }}…
            <i class="fas fa-copy copy-icon"></i>
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="username" label="用户" width="100" align="center">
        <template #default="{ row }">
          <span
            class="user-link"
            @click.stop="goToUser(row.user_id)"
          >
            {{ row.username || `用户#${row.user_id}` }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="kb_name" label="知识库" min-width="140">
        <template #default="{ row }">
          <span class="kb-name-text">{{ row.kb_name || '--' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="question" label="问题" min-width="200">
        <template #default="{ row }">
          <span class="question-text" :title="row.question">
            {{ truncate(row.question, 20) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="total_duration_ms" label="耗时" width="100" align="center">
        <template #default="{ row }">
          <span class="duration-text">{{ formatDuration(row.total_duration_ms) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="intent_type" label="意图" width="110" align="center">
        <template #default="{ row }">
          <span
            v-if="row.intent_type"
            class="intent-tag"
            :class="row.intent_type.toLowerCase()"
          >
            {{ intentLabel(row.intent_type) }}
          </span>
          <span v-else class="text-muted">--</span>
        </template>
      </el-table-column>
      <el-table-column prop="response_mode" label="响应" width="110" align="center">
        <template #default="{ row }">
          <span
            v-if="row.response_mode"
            class="response-tag"
            :class="row.response_mode.toLowerCase()"
          >
            {{ responseLabel(row.response_mode) }}
          </span>
          <span v-else class="text-muted">--</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80" align="center">
        <template #default="{ row }">
          <span class="status-icon" :title="statusLabel(row.status)">
            {{ statusEmoji(row.status) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="160" align="center">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="pagination-wrap">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTraceList } from '@/api/trace'
import { formatDateTime } from '@/utils/format'

const router = useRouter()

// ==================== 列表数据 ====================
const loading = ref(false)
const list = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const searchText = ref('')
const filterStatus = ref('')
const filterIntent = ref('')
const filterResponse = ref('')
const dateRange = ref(null)

// 概览统计（基于全量筛选结果，由后端计算）
const summary = ref({
  success: 0,
  error: 0,
  running: 0,
  success_rate: '0.0',
  avg_duration_ms: 0,
  p95_duration_ms: 0,
})

let searchTimer = null

// ==================== 数据加载 ====================
async function loadList() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize,
    }
    if (searchText.value) params.search = searchText.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterIntent.value) params.intent_type = filterIntent.value
    if (filterResponse.value) params.response_mode = filterResponse.value
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0].toISOString()
      params.end_date = dateRange.value[1].toISOString()
    }

    const { data } = await getTraceList(params)
    if (data.code === '0') {
      list.value = data.data.items
      total.value = data.data.total
      if (data.data.summary) {
        summary.value = data.data.summary
      }
    } else {
      ElMessage.error(data.message || '获取 Trace 列表失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '网络异常，请稍后重试')
  } finally {
    loading.value = false
  }
}

function reloadList() {
  currentPage.value = 1
  loadList()
}

function onPageChange(page) {
  currentPage.value = page
  loadList()
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reloadList, 300)
}

function onSearchClear() {
  reloadList()
}

// ==================== 交互 ====================
function goToDetail(row) {
  router.push(`/admin/traces/${row.trace_id}`)
}

function goToUser(userId) {
  router.push(`/admin/users/${userId}`)
}

async function copyTraceId(traceId) {
  try {
    await navigator.clipboard.writeText(traceId)
    ElMessage.success('Trace ID 已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

// ==================== 工具函数 ====================
function truncate(str, len) {
  if (!str) return '--'
  return str.length > len ? str.slice(0, len) + '…' : str
}

function formatDuration(ms) {
  if (ms == null) return '--'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatSummaryDuration(ms) {
  if (ms == null || ms === 0) return '0.00'
  return (ms / 1000).toFixed(2)
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
  const map = { RAG: 'RAG', DIRECT_LLM: '直接 LLM', META: '元查询', CASUAL: '闲聊', FALLBACK: '兜底回复' }
  return map[mode] || mode
}

onMounted(loadList)
</script>

<style scoped>
.admin-page {
  max-width: var(--dm-content-max-width);
  margin: 0 auto;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--dm-space-6);
}

.detail-desc {
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
  margin-top: var(--dm-space-1);
}

/* 概览卡片 */
.stat-cards-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--dm-space-5);
  margin-bottom: var(--dm-space-5);
}

.stat-card {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-5);
  display: flex;
  align-items: center;
  gap: var(--dm-space-4);
}

.stat-icon {
  width: var(--dm-space-12);
  height: var(--dm-space-12);
  border-radius: var(--dm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--dm-text-lg);
  flex-shrink: 0;
}

.stat-icon.primary { background: var(--dm-primary-light); color: var(--dm-primary); }
.stat-icon.success { background: var(--dm-success-light); color: var(--dm-success); }
.stat-icon.warning { background: var(--dm-warning-light); color: var(--dm-warning); }
.stat-icon.danger  { background: var(--dm-danger-light);  color: var(--dm-danger); }

.stat-value {
  font-size: var(--dm-text-xl);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.stat-sep {
  color: var(--dm-text-tertiary);
  font-weight: var(--dm-weight-normal);
  margin: 0 2px;
}

.stat-unit {
  font-size: var(--dm-text-sm);
  font-weight: var(--dm-weight-normal);
  color: var(--dm-text-secondary);
}

.stat-label {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  margin-top: var(--dm-space-1);
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--dm-space-5);
}

.filter-left {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  flex-wrap: wrap;
}

.total-hint {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-tertiary);
  margin-left: var(--dm-space-2);
}

/* Trace ID 单元格 */
.trace-id-cell {
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-2xs);
  color: var(--dm-info);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-1);
  transition: color var(--dm-transition-fast);
}

.trace-id-cell:hover {
  color: var(--dm-primary);
}

.copy-icon {
  font-size: var(--dm-text-3xs);
  opacity: 0;
  transition: opacity var(--dm-transition-fast);
}

.trace-id-cell:hover .copy-icon {
  opacity: 1;
}

/* 用户链接 */
.user-link {
  color: var(--dm-info);
  cursor: pointer;
  font-size: var(--dm-text-xs);
  transition: color var(--dm-transition-fast);
}

.user-link:hover {
  color: var(--dm-primary);
  text-decoration: underline;
}

/* 知识库名 */
.kb-name-text {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
}

/* 问题文本 */
.question-text {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-primary);
}

/* 耗时 */
.duration-text {
  font-family: var(--dm-font-mono);
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
}

/* 意图标签 */
.intent-tag {
  display: inline-block;
  padding: 2px var(--dm-space-2);
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

/* 响应模式标签 */
.response-tag {
  display: inline-block;
  padding: 2px var(--dm-space-2);
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

/* 状态图标 */
.status-icon {
  font-size: var(--dm-text-base);
}

/* 通用 */
.text-muted {
  color: var(--dm-text-tertiary);
  font-size: var(--dm-text-xs);
}

/* 表格行可点击 */
.el-table {
  cursor: pointer;
}

/* 分页 */
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: var(--dm-space-5);
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
}

/* 筛选栏输入框宽度 */
.filter-input-sm  { width: 120px; }
.filter-input-st  { width: 130px; }
.filter-input-md  { width: 140px; }
.filter-input-lg  { width: 220px; }
.filter-input-xxl { width: 260px; }

/* 通用工具类 */
.table-full { width: 100%; }
.search-icon { color: var(--dm-text-tertiary); }
</style>
