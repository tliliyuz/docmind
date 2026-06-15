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
    <template v-else-if="user">
      <!-- 顶部导航 -->
      <div class="detail-nav">
        <button class="back-btn" @click="goBack">
          <i class="fas fa-arrow-left"></i> 返回列表
        </button>
        <span class="user-title">用户: {{ user.username }}</span>
      </div>

      <!-- 用户信息卡片 -->
      <div class="info-card">
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">用户名</span>
            <span class="info-value">{{ user.username }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">角色</span>
            <span class="role-tag" :class="user.role">
              {{ user.role === 'admin' ? '管理员' : '普通用户' }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">状态</span>
            <span class="status-tag" :class="user.status">
              {{ user.status === 'active' ? '正常' : '已禁用' }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">注册时间</span>
            <span class="info-value">{{ formatDateTime(user.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">最后活跃</span>
            <span class="info-value">{{ formatRelativeTime(user.last_active_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 统计卡片 -->
      <h3 class="section-title">数据统计</h3>
      <div class="stat-cards-row">
        <div class="stat-card">
          <div class="stat-icon primary">
            <i class="fas fa-database"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(user.kb_count) }}</div>
            <div class="stat-label">知识库</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon success">
            <i class="fas fa-file-alt"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(user.doc_count) }}</div>
            <div class="stat-label">文档</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon warning">
            <i class="fas fa-comments"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(user.conversation_count) }}</div>
            <div class="stat-label">会话</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon info">
            <i class="fas fa-envelope"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(user.message_count) }}</div>
            <div class="stat-label">消息</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon info">
            <i class="fas fa-arrow-down"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatToken(user.total_input_tokens) }}</div>
            <div class="stat-label">Input Token</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon info">
            <i class="fas fa-arrow-up"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatToken(user.total_output_tokens) }}</div>
            <div class="stat-label">Output Token</div>
          </div>
        </div>
      </div>

      <!-- 快捷操作 -->
      <h3 class="section-title">快捷操作</h3>
      <div class="actions-row">
        <button
          class="action-card"
          :class="[user.status === 'active' ? 'danger' : '', toggleLoading ? 'loading' : '']"
          :disabled="toggleLoading"
          @click="confirmToggleStatus"
        >
          <i :class="toggleLoading ? 'fas fa-spinner fa-spin' : (user.status === 'active' ? 'fas fa-ban' : 'fas fa-check-circle')"></i>
          <span>{{ toggleLoading ? '处理中…' : (user.status === 'active' ? '禁用用户' : '启用用户') }}</span>
        </button>
        <button class="action-card" @click="openResetDialog">
          <i class="fas fa-key"></i>
          <span>重置密码</span>
        </button>
      </div>
    </template>

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
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminUserDetail, changeUserStatus, resetUserPassword } from '@/api/admin'
import { formatDateTime } from '@/utils/format'

const router = useRouter()
const route = useRoute()

// ==================== 数据 ====================
const loading = ref(true)
const error = ref('')
const user = ref(null)

// ==================== 数据加载 ====================
async function loadDetail() {
  const userId = route.params.user_id
  if (!userId) {
    error.value = '缺少 user_id 参数'
    loading.value = false
    return
  }

  try {
    const { data } = await getAdminUserDetail(Number(userId))
    if (data.code === '0') {
      user.value = data.data
    } else {
      error.value = data.message || '获取用户详情失败'
    }
  } catch (e) {
    error.value = e.response?.data?.message || '网络异常，请稍后重试'
  } finally {
    loading.value = false
  }
}

// ==================== 交互 ====================
function goBack() {
  router.push('/admin/users')
}

// ==================== 禁用/启用 ====================
const toggleLoading = ref(false)

async function confirmToggleStatus() {
  const isDisabling = user.value.status === 'active'
  const action = isDisabling ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确认${action}用户「${user.value.username}」？${isDisabling ? '禁用后该用户将无法登录和使用 API。' : ''}`,
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
  toggleLoading.value = true
  try {
    const { data } = await changeUserStatus(user.value.id, newStatus)
    if (data.code === '0') {
      ElMessage.success(data.message || `${action}成功`)
      user.value.status = newStatus
    } else {
      ElMessage.error(data.message || `${action}失败`)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '网络异常，请稍后重试')
  } finally {
    toggleLoading.value = false
  }
}

// ==================== 重置密码 ====================
const resetDialogVisible = ref(false)
const resetSubmitting = ref(false)
const resetFormRef = ref(null)

const resetFormData = ref({
  newPassword: '',
})

const resetFormRules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
  ],
}

function openResetDialog() {
  resetFormData.value.newPassword = ''
  resetDialogVisible.value = true
}

async function handleResetSubmit() {
  const valid = await resetFormRef.value?.validate().catch(() => false)
  if (valid === false) return

  resetSubmitting.value = true
  try {
    const { data } = await resetUserPassword(user.value.id, resetFormData.value.newPassword)
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

function formatNumber(val) {
  if (val == null) return '--'
  return Number(val).toLocaleString()
}

function formatToken(val) {
  if (val == null) return '--'
  const num = Number(val)
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return String(num)
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

.user-title {
  font-size: var(--dm-text-lg);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

/* 用户信息卡片 */
.info-card {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-5);
  margin-bottom: var(--dm-space-6);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--dm-space-4);
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

/* 角色标签 */
.role-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-medium);
  width: fit-content;
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
  width: fit-content;
}

.status-tag.active {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.status-tag.disabled {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

/* 章节标题 */
.section-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-4);
}

/* 统计卡片 */
.stat-cards-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--dm-space-4);
  margin-bottom: var(--dm-space-6);
}

.stat-card {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-4);
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  transition: box-shadow var(--dm-transition-fast);
}

.stat-card:hover {
  box-shadow: var(--dm-shadow-card);
}

.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: var(--dm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--dm-text-base);
  flex-shrink: 0;
}

.stat-icon.primary { background: var(--dm-primary-light); color: var(--dm-primary); }
.stat-icon.success { background: var(--dm-success-light); color: var(--dm-success); }
.stat-icon.warning { background: var(--dm-warning-light); color: var(--dm-warning); }
.stat-icon.info    { background: var(--dm-bg-page);       color: var(--dm-text-secondary); }

.stat-value {
  font-size: var(--dm-text-xl);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.stat-label {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  margin-top: var(--dm-space-1);
}

/* 快捷操作 */
.actions-row {
  display: flex;
  gap: var(--dm-space-4);
  margin-bottom: var(--dm-space-6);
}

.action-card {
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-3);
  padding: 14px 24px;
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  background: var(--dm-bg-card);
  color: var(--dm-text-primary);
  font-size: var(--dm-text-body);
  font-weight: var(--dm-weight-medium);
  cursor: pointer;
  transition: all var(--dm-transition-fast);
}

.action-card:hover {
  border-color: var(--dm-primary);
  color: var(--dm-primary);
  background: var(--dm-primary-light);
}

.action-card.danger:hover {
  border-color: var(--dm-danger);
  color: var(--dm-danger);
  background: var(--dm-danger-light);
}

.action-card:disabled,
.action-card.loading {
  opacity: 0.6;
  cursor: not-allowed;
  pointer-events: none;
}

.action-card i {
  font-size: var(--dm-text-base);
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
  margin-bottom: var(--dm-space-4);
}
</style>
