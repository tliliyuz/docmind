<template>
  <div class="admin-page">
    <!-- 页面描述（标题已在 AdminLayout header 中展示） -->
    <div class="detail-header">
      <p class="detail-desc">查看所有文档（跨知识库管理）</p>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-input
          v-model="searchFilename"
          placeholder="搜索文件名..."
          size="default"
          clearable
          style="width: 220px;"
          @input="onSearchInput"
          @clear="onSearchClear"
        >
          <template #prefix>
            <i class="fas fa-search" style="color: var(--dm-text-tertiary);"></i>
          </template>
        </el-input>
        <el-select
          v-model="filterStatus"
          placeholder="全部状态"
          clearable
          size="default"
          style="width: 140px;"
          @change="reloadList"
        >
          <el-option label="全部状态" value="" />
          <el-option label="已上传" value="uploaded" />
          <el-option label="解析中" value="parsing" />
          <el-option label="分块中" value="chunking" />
          <el-option label="向量化中" value="embedding" />
          <el-option label="写入向量库" value="vector_storing" />
          <el-option label="已完成" value="completed" />
          <el-option label="有警告" value="success_with_warnings" />
          <el-option label="部分失败" value="partial_failed" />
          <el-option label="失败" value="failed" />
          <el-option label="删除中" value="deleting" />
        </el-select>
        <el-select
          v-model="sortBy"
          size="default"
          style="width: 120px;"
          @change="reloadList"
        >
          <el-option label="上传时间" value="created_at" />
          <el-option label="文件大小" value="file_size" />
          <el-option label="文件名" value="filename" />
          <el-option label="状态" value="status" />
          <el-option label="分块数" value="chunk_count" />
        </el-select>
        <el-select
          v-model="sortOrder"
          size="default"
          style="width: 100px;"
          @change="reloadList"
        >
          <el-option label="降序" value="desc" />
          <el-option label="升序" value="asc" />
        </el-select>
        <span v-if="total > 0" class="total-hint">共 {{ total }} 个文档</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && list.length === 0" class="empty-state">
      <i class="fas fa-file-alt empty-icon"></i>
      <div class="empty-title">暂无文档</div>
      <div class="empty-desc">系统中还没有任何文档</div>
    </div>

    <!-- 表格 -->
    <el-table
      v-else
      :data="list"
      v-loading="loading"
      style="width: 100%"
      row-key="id"
    >
      <el-table-column prop="id" label="ID" width="60" align="center" />
      <el-table-column prop="filename" label="文件名" min-width="200">
        <template #default="{ row }">
          <div class="filename-cell">
            <span class="doc-filename">{{ row.filename }}</span>
            <span v-if="row.error_message" class="error-hint" :title="row.error_message">
              <i class="fas fa-exclamation-triangle"></i>
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="kb_name" label="所属知识库" min-width="150">
        <template #default="{ row }">
          <div class="kb-cell">
            <span class="kb-link">{{ row.kb_name || `KB #${row.kb_id}` }}</span>
            <span v-if="row.kb_visibility" class="kb-visibility-badge" :class="row.kb_visibility">
              {{ row.kb_visibility === 'public' ? '公开' : '私有' }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="owner_username" label="上传者" width="110" align="center">
        <template #default="{ row }">
          {{ row.owner_username || `用户 #${row.owner_id}` }}
        </template>
      </el-table-column>
      <el-table-column prop="file_type" label="类型" width="70" align="center">
        <template #default="{ row }">
          <span class="file-type-badge">{{ (row.file_type || '').toUpperCase() }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="file_size" label="大小" width="90" align="center">
        <template #default="{ row }">
          {{ formatFileSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80" align="center">
        <template #default="{ row }">
          <span class="doc-status-tag" :class="row.status">
            {{ getStatusLabel(row.status) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="分块数" width="80" align="center">
        <template #default="{ row }">
          {{ isTerminal(row.status) ? (row.chunk_count ?? '--') : '--' }}
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="上传时间" width="160" align="center">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" align="center" fixed="right">
        <template #default="{ row }">
          <button class="action-btn danger" title="删除文档" @click="confirmDelete(row)">
            <i class="fas fa-trash"></i>
          </button>
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
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { getAdminDocuments } from '@/api/admin'
import { deleteDocument } from '@/api/knowledge'

// ==================== 列表数据 ====================
const loading = ref(false)
const list = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const searchFilename = ref('')
const filterStatus = ref('')
const sortBy = ref('created_at')
const sortOrder = ref('desc')

let searchTimer = null

// ==================== 终态常量 ====================
const TERMINAL_STATUSES = new Set([
  'completed', 'success_with_warnings', 'partial_failed', 'failed',
])

function isTerminal(status) {
  return TERMINAL_STATUSES.has(status)
}

// ==================== 数据加载 ====================
async function loadList() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize,
      sort_by: sortBy.value,
      order: sortOrder.value,
    }
    if (searchFilename.value) params.filename = searchFilename.value
    if (filterStatus.value) params.status = filterStatus.value

    const { data } = await getAdminDocuments(params)
    if (data.code === '0') {
      list.value = data.data.items
      total.value = data.data.total
    } else {
      ElMessage.error(data.message || '获取文档列表失败')
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

// ==================== 删除 ====================
async function confirmDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除文档「${row.filename}」（所属知识库：${row.kb_name || '未知'}）？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return // 用户取消
  }

  const loadingInstance = ElLoading.service({
    fullscreen: true,
    text: `正在删除文档「${row.filename}」…`,
    background: 'rgba(0, 0, 0, 0.5)',
  })
  try {
    const { data } = await deleteDocument(row.kb_id, row.id)
    if (data.code === '0') {
      // 本地移除，无需重新请求后端
      list.value = list.value.filter(d => d.id !== row.id)
      total.value--
      ElMessage.success('文档已删除')
    } else {
      ElMessage.error(data.message || '删除失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '网络异常，请稍后重试')
  } finally {
    loadingInstance.close()
  }
}

// ==================== 工具函数 ====================
const STATUS_LABELS = {
  uploaded: '已上传', parsing: '解析中', chunking: '分块中',
  embedding: '向量化中', vector_storing: '写入向量库', completed: '已完成',
  success_with_warnings: '有警告', partial_failed: '部分失败', failed: '失败',
  deleting: '删除中',
}

function getStatusLabel(status) {
  return STATUS_LABELS[status] || status || '--'
}

function formatFileSize(bytes) {
  if (bytes == null) return '--'
  const num = Number(bytes)
  if (num === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(num) / Math.log(1024)), units.length - 1)
  return (num / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

function formatDateTime(isoString) {
  if (!isoString) return '--'
  const d = new Date(isoString)
  if (isNaN(d.getTime())) return '--'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
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

/* 文件名列 */
.filename-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.doc-filename {
  font-weight: var(--dm-weight-medium);
  color: var(--dm-text-primary);
}

.error-hint {
  color: var(--dm-danger);
  cursor: help;
  font-size: var(--dm-text-2xs);
  flex-shrink: 0;
}

/* KB 列 */
.kb-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.kb-link {
  color: var(--dm-text-secondary);
  font-size: var(--dm-text-xs);
}

.kb-visibility-badge {
  display: inline-block;
  padding: 0 6px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-3xs);
  font-weight: var(--dm-weight-medium);
  flex-shrink: 0;
}

.kb-visibility-badge.public {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.kb-visibility-badge.private {
  background: var(--dm-bg-page);
  color: var(--dm-text-tertiary);
}

/* 文件类型 */
.file-type-badge {
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-tertiary);
  background: var(--dm-bg-page);
  padding: 2px 6px;
  border-radius: var(--dm-radius-xs);
}

/* 操作按钮 */
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--dm-text-tertiary);
  font-size: var(--dm-text-xs);
  cursor: pointer;
  border-radius: var(--dm-radius-xs);
  transition: all var(--dm-transition-fast);
}

.action-btn:hover:not(:disabled) {
  background: var(--dm-bg-page);
  color: var(--dm-primary);
}

.action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.action-btn.danger:hover:not(:disabled) {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

/* 文档状态标签 */
.doc-status-tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
}

.doc-status-tag.completed { background: var(--dm-success-light); color: var(--dm-success); }
.doc-status-tag.success_with_warnings { background: var(--dm-success-light); color: var(--dm-success); }
.doc-status-tag.partial_failed { background: var(--dm-warning-light); color: var(--dm-warning); }
.doc-status-tag.failed { background: var(--dm-danger-light); color: var(--dm-danger); }
.doc-status-tag.deleting { background: var(--dm-bg-page); color: var(--dm-text-tertiary); }
.doc-status-tag.uploaded,
.doc-status-tag.parsing,
.doc-status-tag.chunking,
.doc-status-tag.embedding,
.doc-status-tag.vector_storing { background: var(--dm-primary-light); color: var(--dm-primary); }

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
  font-size: 48px;
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
</style>
