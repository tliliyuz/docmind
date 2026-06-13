<template>
  <div class="admin-page">
    <!-- 页面描述（标题已在 AdminLayout header 中展示） -->
    <div class="detail-header">
      <p class="detail-desc">查看所有用户的知识库（跨用户管理）</p>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-input
          v-model="searchText"
          placeholder="搜索知识库名称..."
          size="default"
          clearable
          style="width: 240px;"
          @input="onSearchInput"
          @clear="onSearchClear"
        >
          <template #prefix>
            <i class="fas fa-search" style="color: var(--dm-text-tertiary);"></i>
          </template>
        </el-input>
        <el-select
          v-model="filterVisibility"
          placeholder="可见性"
          clearable
          size="default"
          style="width: 130px;"
          @change="reloadList"
        >
          <el-option label="全部" value="" />
          <el-option label="私有" value="private" />
          <el-option label="公开" value="public" />
        </el-select>
        <el-select
          v-model="filterStatus"
          placeholder="状态"
          clearable
          size="default"
          style="width: 130px;"
          @change="reloadList"
        >
          <el-option label="全部" value="" />
          <el-option label="正常" value="active" />
          <el-option label="删除中" value="deleting" />
        </el-select>
        <span v-if="total > 0" class="total-hint">共 {{ total }} 个知识库</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && list.length === 0" class="empty-state">
      <i class="fas fa-database empty-icon"></i>
      <div class="empty-title">暂无知识库</div>
      <div class="empty-desc">系统中还没有任何知识库</div>
    </div>

    <!-- 表格 -->
    <el-table
      v-else
      :data="list"
      v-loading="loading"
      style="width: 100%"
      row-key="id"
    >
      <el-table-column prop="id" label="ID" width="70" align="center" />
      <el-table-column prop="name" label="名称" min-width="180">
        <template #default="{ row }">
          <div class="kb-name-cell">
            <span class="kb-name">{{ row.name }}</span>
            <span
              v-if="row.description"
              class="kb-desc"
              :title="row.description"
            >{{ row.description }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="username" label="所有者" width="120" align="center">
        <template #default="{ row }">
          <span class="owner-name">{{ row.username || `用户 #${row.user_id}` }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="visibility" label="可见性" width="100" align="center">
        <template #default="{ row }">
          <span class="visibility-tag" :class="row.visibility">
            <i :class="row.visibility === 'public' ? 'fas fa-globe' : 'fas fa-lock'"></i>
            {{ row.visibility === 'public' ? '公开' : '私有' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="doc_count" label="文档数" width="90" align="center" />
      <el-table-column prop="chunk_count" label="分块数" width="90" align="center" />
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <span class="status-tag" :class="row.status">
            {{ row.status === 'active' ? '正常' : '删除中' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" align="center">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <button class="action-btn" title="编辑" @click="openEditDialog(row)">
              <i class="fas fa-pen"></i>
            </button>
            <button class="action-btn danger" title="删除" @click="confirmDelete(row)">
              <i class="fas fa-trash"></i>
            </button>
          </div>
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

    <!-- 编辑 KB 弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑知识库"
      width="480px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="editFormRef"
        :model="editFormData"
        :rules="editFormRules"
        label-position="top"
      >
        <el-form-item label="名称" prop="name">
          <el-input
            v-model="editFormData.name"
            placeholder="请输入知识库名称"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="editFormData.description"
            type="textarea"
            placeholder="请输入知识库描述（选填）"
            :rows="3"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="可见性" prop="visibility">
          <el-radio-group v-model="editFormData.visibility">
            <el-radio value="private">
              <i class="fas fa-lock" style="margin-right: 4px; color: var(--dm-text-tertiary);"></i>
              私有
            </el-radio>
            <el-radio value="public">
              <i class="fas fa-globe" style="margin-right: 4px; color: var(--dm-text-tertiary);"></i>
              公开
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="handleEditSubmit">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { getAdminKnowledgeBases } from '@/api/admin'
import { updateKnowledgeBase, deleteKnowledgeBase } from '@/api/knowledge'

// ==================== 列表数据 ====================
const loading = ref(false)
const list = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const searchText = ref('')
const filterVisibility = ref('')
const filterStatus = ref('')

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
    if (filterVisibility.value) params.visibility = filterVisibility.value
    if (filterStatus.value) params.status = filterStatus.value

    const { data } = await getAdminKnowledgeBases(params)
    if (data.code === '0') {
      list.value = data.data.items
      total.value = data.data.total
    } else {
      ElMessage.error(data.message || '获取知识库列表失败')
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

// ==================== 编辑 ====================
const editDialogVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref(null)
const editingRow = ref(null)

const editFormData = reactive({
  name: '',
  description: '',
  visibility: 'private',
})

const editFormRules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' },
    { min: 1, max: 50, message: '名称长度为 1-50 字符', trigger: 'blur' },
  ],
}

function openEditDialog(row) {
  editingRow.value = row
  editFormData.name = row.name
  editFormData.description = row.description || ''
  editFormData.visibility = row.visibility
  editDialogVisible.value = true
}

async function handleEditSubmit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (valid === false) return

  editSubmitting.value = true
  try {
    const { data } = await updateKnowledgeBase(editingRow.value.id, {
      name: editFormData.name,
      description: editFormData.description,
      visibility: editFormData.visibility,
    })
    if (data.code === '0') {
      ElMessage.success('知识库已更新')
      editDialogVisible.value = false
      // 本地 patch：直接更新行数据，避免全量重拉
      const idx = list.value.findIndex(k => k.id === editingRow.value.id)
      if (idx !== -1) {
        list.value[idx] = {
          ...list.value[idx],
          name: editFormData.name,
          description: editFormData.description,
          visibility: editFormData.visibility,
        }
      }
    } else {
      ElMessage.error(data.message || '更新失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '网络异常，请稍后重试')
  } finally {
    editSubmitting.value = false
  }
}

// ==================== 删除 ====================
async function confirmDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除知识库「${row.name}」？此操作不可恢复。`,
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
    text: `正在删除知识库「${row.name}」…`,
    background: 'rgba(0, 0, 0, 0.5)',
  })
  try {
    const { data } = await deleteKnowledgeBase(row.id)
    if (data.code === '0') {
      // 本地移除，无需重新请求后端
      list.value = list.value.filter(k => k.id !== row.id)
      total.value--
      ElMessage.success('知识库已删除')
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

/* 名称列 */
.kb-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kb-name {
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

.kb-desc {
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.owner-name {
  color: var(--dm-text-secondary);
  font-size: var(--dm-text-xs);
}

/* 可见性标签 */
.visibility-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
}

.visibility-tag.private {
  background: var(--dm-bg-page);
  color: var(--dm-text-secondary);
}

.visibility-tag.public {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

/* 状态标签 */
.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
}

.status-tag.active {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.status-tag.deleting {
  background: var(--dm-bg-page);
  color: var(--dm-text-tertiary);
}

/* 操作按钮 */
.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--dm-space-2);
}

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

.action-btn:hover {
  background: var(--dm-bg-page);
  color: var(--dm-primary);
}

.action-btn.danger:hover {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
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
