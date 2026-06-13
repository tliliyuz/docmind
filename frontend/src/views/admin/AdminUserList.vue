<template>
  <div class="admin-page">
    <!-- 页面描述 -->
    <div class="detail-header">
      <p class="detail-desc">查看和管理所有注册用户</p>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-input
          v-model="searchText"
          placeholder="搜索用户名..."
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
          v-model="filterRole"
          placeholder="角色"
          clearable
          size="default"
          style="width: 120px;"
          @change="reloadList"
        >
          <el-option label="全部" value="" />
          <el-option label="管理员" value="admin" />
          <el-option label="普通用户" value="user" />
        </el-select>
        <el-select
          v-model="filterStatus"
          placeholder="状态"
          clearable
          size="default"
          style="width: 120px;"
          @change="reloadList"
        >
          <el-option label="全部" value="" />
          <el-option label="正常" value="active" />
          <el-option label="已禁用" value="disabled" />
        </el-select>
        <span v-if="total > 0" class="total-hint">共 {{ total }} 位用户</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && list.length === 0" class="empty-state">
      <i class="fas fa-users empty-icon"></i>
      <div class="empty-title">暂无用户</div>
      <div class="empty-desc">系统中还没有匹配的用户记录</div>
    </div>

    <!-- 表格 -->
    <el-table
      v-else
      :data="list"
      v-loading="loading"
      style="width: 100%"
      row-key="id"
      highlight-current-row
      @row-click="goToDetail"
    >
      <el-table-column prop="username" label="用户名" min-width="140">
        <template #default="{ row }">
          <span class="username-text">{{ row.username }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="role" label="角色" width="110" align="center">
        <template #default="{ row }">
          <span class="role-tag" :class="row.role">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <span class="status-tag" :class="row.status">
            {{ row.status === 'active' ? '正常' : '已禁用' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="kb_count" label="知识库" width="90" align="center" />
      <el-table-column prop="doc_count" label="文档" width="80" align="center" />
      <el-table-column prop="conversation_count" label="会话" width="80" align="center" />
      <el-table-column prop="last_active_at" label="最后活跃" width="150" align="center">
        <template #default="{ row }">
          <span class="time-text">{{ formatRelativeTime(row.last_active_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" align="center" fixed="right">
        <template #default="{ row }">
          <el-dropdown
            trigger="click"
            @command="(cmd) => handleAction(row, cmd)"
            @click.stop
          >
            <button class="action-menu-btn" @click.stop>
              <i class="fas fa-ellipsis-h"></i>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="detail">
                  <i class="fas fa-eye"></i> 查看详情
                </el-dropdown-item>
                <el-dropdown-item
                  command="toggleStatus"
                  :class="row.status === 'active' ? 'danger-action' : ''"
                >
                  <i :class="row.status === 'active' ? 'fas fa-ban' : 'fas fa-check-circle'"></i>
                  {{ row.status === 'active' ? '禁用用户' : '启用用户' }}
                </el-dropdown-item>
                <el-dropdown-item command="resetPassword">
                  <i class="fas fa-key"></i> 重置密码
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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

    <!-- 重置密码弹窗 -->
    <el-dialog
      v-model="resetDialogVisible"
      title="重置密码"
      width="440px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="resetFormRef"
        :model="resetFormData"
        :rules="resetFormRules"
        label-position="top"
      >
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="resetFormData.newPassword"
            type="password"
            show-password
            placeholder="请输入新密码（至少 6 位）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSubmitting" @click="handleResetSubmit">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminUsers, changeUserStatus, resetUserPassword } from '@/api/admin'

const router = useRouter()

// ==================== 列表数据 ====================
const loading = ref(false)
const list = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const searchText = ref('')
const filterRole = ref('')
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
    if (filterRole.value) params.role = filterRole.value
    if (filterStatus.value) params.status = filterStatus.value

    const { data } = await getAdminUsers(params)
    if (data.code === '0') {
      list.value = data.data.items
      total.value = data.data.total
    } else {
      ElMessage.error(data.message || '获取用户列表失败')
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
  router.push(`/admin/users/${row.id}`)
}

function handleAction(row, command) {
  switch (command) {
    case 'detail':
      goToDetail(row)
      break
    case 'toggleStatus':
      confirmToggleStatus(row)
      break
    case 'resetPassword':
      openResetDialog(row)
      break
  }
}

// ==================== 禁用/启用 ====================
async function confirmToggleStatus(row) {
  const isDisabling = row.status === 'active'
  const action = isDisabling ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确认${action}用户「${row.username}」？${isDisabling ? '禁用后该用户将无法登录和使用 API。' : ''}`,
      `确认${action}`,
      {
        confirmButtonText: `确认${action}`,
        cancelButtonText: '取消',
        type: isDisabling ? 'warning' : 'info',
        confirmButtonClass: isDisabling ? 'el-button--danger' : '',
      }
    )
  } catch {
    return // 用户取消
  }

  const newStatus = isDisabling ? 'disabled' : 'active'
  try {
    const { data } = await changeUserStatus(row.id, newStatus)
    if (data.code === '0') {
      ElMessage.success(data.message || `${action}成功`)
      // 更新当前列表中的行状态
      row.status = newStatus
    } else {
      ElMessage.error(data.message || `${action}失败`)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '网络异常，请稍后重试')
  }
}

// ==================== 重置密码 ====================
const resetDialogVisible = ref(false)
const resetSubmitting = ref(false)
const resetFormRef = ref(null)
const resettingUser = ref(null)

const resetFormData = ref({
  newPassword: '',
})

const resetFormRules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
  ],
}

function openResetDialog(row) {
  resettingUser.value = row
  resetFormData.value.newPassword = ''
  resetDialogVisible.value = true
}

async function handleResetSubmit() {
  const valid = await resetFormRef.value?.validate().catch(() => false)
  if (valid === false) return

  resetSubmitting.value = true
  try {
    const { data } = await resetUserPassword(resettingUser.value.id, resetFormData.value.newPassword)
    if (data.code === '0') {
      ElMessage.success('密码重置成功')
      resetDialogVisible.value = false
    } else {
      ElMessage.error(data.message || '重置密码失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '网络异常，请稍后重试')
  } finally {
    resetSubmitting.value = false
  }
}

// ==================== 工具函数 ====================
function formatRelativeTime(isoString) {
  if (!isoString) return '从未活跃'
  const d = new Date(isoString)
  if (isNaN(d.getTime())) return '--'
  const now = Date.now()
  const diffMs = now - d.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffHour < 24) return `${diffHour} 小时前`
  if (diffDay < 7) return `${diffDay} 天前`
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
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

/* 用户名 */
.username-text {
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

/* 角色标签 */
.role-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
}

.role-tag.admin {
  background: var(--dm-primary-light);
  color: var(--dm-primary);
}

.role-tag.user {
  background: var(--dm-bg-page);
  color: var(--dm-text-secondary);
}

/* 状态标签 */
.status-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
}

.status-tag.active {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.status-tag.disabled {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

/* 时间 */
.time-text {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
}

/* 操作菜单按钮 */
.action-menu-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--dm-text-tertiary);
  font-size: var(--dm-text-sm);
  cursor: pointer;
  border-radius: var(--dm-radius-xs);
  transition: all var(--dm-transition-fast);
}

.action-menu-btn:hover {
  background: var(--dm-bg-page);
  color: var(--dm-primary);
}

/* 下拉菜单危险操作 */
:deep(.danger-action) {
  color: var(--dm-danger) !important;
}

:deep(.danger-action:hover) {
  background: var(--dm-danger-light) !important;
  color: var(--dm-danger) !important;
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
