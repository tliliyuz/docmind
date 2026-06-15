<template>
  <aside class="sidebar" :class="{ collapsed, 'menu-open': showUserMenu }">
    <!-- 顶部：折叠按钮 + Logo + 新建对话 -->
    <div class="sidebar-top">
      <!-- 收起按钮（仅展开态显示） -->
      <button
        v-show="!collapsed"
        class="collapse-toggle-btn"
        @click="toggleCollapse"
        title="收起侧边栏"
      >
        <i class="fas fa-bars"></i>
      </button>

      <!-- Logo：收起态点击可展开侧边栏 -->
      <div
        class="sidebar-logo"
        :class="{ 'logo-clickable': collapsed }"
        @click="collapsed && toggleCollapse()"
        :title="collapsed ? '展开侧边栏' : ''"
      >
        <div class="sidebar-logo-icon">
          <i class="fas fa-brain"></i>
        </div>
        <div class="sidebar-logo-text" v-show="!collapsed">
          <span class="logo-subtitle">知识库问答平台</span>
        </div>
      </div>

      <!-- 展开态：含文字按钮 -->
      <button
        class="new-chat-btn"
        :class="{ active: route.path === '/chat' && !route.query.conversation_id }"
        @click="handleNewChat"
        v-show="!collapsed"
      >
        <i class="fas fa-plus"></i>
        <span>新建对话</span>
      </button>
      <!-- 收起态：仅图标按钮 -->
      <button
        class="new-chat-btn new-chat-btn-icon"
        :class="{ active: route.path === '/chat' && !route.query.conversation_id }"
        @click="handleNewChat"
        v-show="collapsed"
        title="新建对话"
      >
        <i class="fas fa-plus"></i>
      </button>
    </div>

    <!-- 中间：会话列表（可滚动） + 知识库导航（固定） + 管理后台（固定） -->
    <div class="sidebar-middle">
      <!-- 会话列表区域（可滚动） -->
      <div class="conv-section">
        <div class="section-label" v-show="!collapsed">历史会话</div>

        <!-- 加载中 -->
        <div v-if="convStore.loading" class="conv-loading">
          <i class="fas fa-spinner fa-spin"></i>
          <span v-show="!collapsed">加载中...</span>
        </div>

        <!-- 空态 -->
        <div v-else-if="convStore.conversations.length === 0" class="conv-list-empty">
          <i class="fas fa-comments empty-icon"></i>
          <span class="empty-text" v-show="!collapsed">暂无会话</span>
        </div>

        <!-- 会话列表（展开态：分组显示） -->
        <template v-else-if="!collapsed">
          <!-- 今天 -->
          <div v-if="convStore.groupedConversations.today.length" class="conv-group">
            <div class="conv-group-label">今天</div>
            <div
              v-for="conv in convStore.groupedConversations.today"
              :key="conv.uuid"
              class="conv-item"
              :class="{ active: isActive(conv.uuid) }"
              @click="handleSelectConversation(conv)"
            >
              <div class="conv-icon" :class="{ 'conv-icon-orphan': conv.kb_status === 'deleted' || conv.kb_status === 'unavailable' }" :title="conv.kb_status === 'deleted' ? '知识库已删除' : conv.kb_status === 'unavailable' ? '知识库不可访问' : undefined">
                <i v-if="conv.kb_status === 'deleted'" class="fas fa-exclamation-triangle"></i>
                <i v-else-if="conv.kb_status === 'unavailable'" class="fas fa-lock"></i>
                <i v-else class="fas fa-message"></i>
              </div>
              <div class="conv-info">
                <div v-if="editingId === conv.uuid" class="conv-edit-wrap">
                  <input
                    ref="editInputRef"
                    v-model="editingTitle"
                    class="conv-edit-input"
                    @keydown.enter="handleSaveRename(conv.uuid)"
                    @keydown.escape="cancelRename"
                    @blur="handleSaveRename(conv.uuid)"
                  />
                </div>
                <template v-else>
                  <div class="conv-title">
                    {{ conv.title || '新对话' }}
                  </div>
                  <div class="conv-meta">{{ formatTime(conv.last_message_at || conv.updated_at) }}</div>
                </template>
              </div>
              <div class="conv-actions" v-if="editingId !== conv.uuid">
                <button title="重命名" @click.stop="startRename(conv)">
                  <i class="fas fa-pen"></i>
                </button>
                <button title="删除" @click.stop="handleDelete(conv)">
                  <i class="fas fa-trash"></i>
                </button>
              </div>
            </div>
          </div>

          <!-- 昨天 -->
          <div v-if="convStore.groupedConversations.yesterday.length" class="conv-group">
            <div class="conv-group-label">昨天</div>
            <div
              v-for="conv in convStore.groupedConversations.yesterday"
              :key="conv.uuid"
              class="conv-item"
              :class="{ active: isActive(conv.uuid) }"
              @click="handleSelectConversation(conv)"
            >
              <div class="conv-icon" :class="{ 'conv-icon-orphan': conv.kb_status === 'deleted' || conv.kb_status === 'unavailable' }" :title="conv.kb_status === 'deleted' ? '知识库已删除' : conv.kb_status === 'unavailable' ? '知识库不可访问' : undefined">
                <i v-if="conv.kb_status === 'deleted'" class="fas fa-exclamation-triangle"></i>
                <i v-else-if="conv.kb_status === 'unavailable'" class="fas fa-lock"></i>
                <i v-else class="fas fa-message"></i>
              </div>
              <div class="conv-info">
                <div v-if="editingId === conv.uuid" class="conv-edit-wrap">
                  <input
                    ref="editInputRef"
                    v-model="editingTitle"
                    class="conv-edit-input"
                    @keydown.enter="handleSaveRename(conv.uuid)"
                    @keydown.escape="cancelRename"
                    @blur="handleSaveRename(conv.uuid)"
                  />
                </div>
                <template v-else>
                  <div class="conv-title">
                    {{ conv.title || '新对话' }}
                  </div>
                  <div class="conv-meta">{{ formatTime(conv.last_message_at || conv.updated_at) }}</div>
                </template>
              </div>
              <div class="conv-actions" v-if="editingId !== conv.uuid">
                <button title="重命名" @click.stop="startRename(conv)">
                  <i class="fas fa-pen"></i>
                </button>
                <button title="删除" @click.stop="handleDelete(conv)">
                  <i class="fas fa-trash"></i>
                </button>
              </div>
            </div>
          </div>

          <!-- 近 7 天 -->
          <div v-if="convStore.groupedConversations.recent.length" class="conv-group">
            <div class="conv-group-label">近 7 天</div>
            <div
              v-for="conv in convStore.groupedConversations.recent"
              :key="conv.uuid"
              class="conv-item"
              :class="{ active: isActive(conv.uuid) }"
              @click="handleSelectConversation(conv)"
            >
              <div class="conv-icon" :class="{ 'conv-icon-orphan': conv.kb_status === 'deleted' || conv.kb_status === 'unavailable' }" :title="conv.kb_status === 'deleted' ? '知识库已删除' : conv.kb_status === 'unavailable' ? '知识库不可访问' : undefined">
                <i v-if="conv.kb_status === 'deleted'" class="fas fa-exclamation-triangle"></i>
                <i v-else-if="conv.kb_status === 'unavailable'" class="fas fa-lock"></i>
                <i v-else class="fas fa-message"></i>
              </div>
              <div class="conv-info">
                <div v-if="editingId === conv.uuid" class="conv-edit-wrap">
                  <input
                    ref="editInputRef"
                    v-model="editingTitle"
                    class="conv-edit-input"
                    @keydown.enter="handleSaveRename(conv.uuid)"
                    @keydown.escape="cancelRename"
                    @blur="handleSaveRename(conv.uuid)"
                  />
                </div>
                <template v-else>
                  <div class="conv-title">
                    {{ conv.title || '新对话' }}
                  </div>
                  <div class="conv-meta">{{ formatTime(conv.last_message_at || conv.updated_at) }}</div>
                </template>
              </div>
              <div class="conv-actions" v-if="editingId !== conv.uuid">
                <button title="重命名" @click.stop="startRename(conv)">
                  <i class="fas fa-pen"></i>
                </button>
                <button title="删除" @click.stop="handleDelete(conv)">
                  <i class="fas fa-trash"></i>
                </button>
              </div>
            </div>
          </div>

          <!-- 更早 -->
          <div v-if="convStore.groupedConversations.older.length" class="conv-group">
            <div class="conv-group-label">更早</div>
            <div
              v-for="conv in convStore.groupedConversations.older"
              :key="conv.uuid"
              class="conv-item"
              :class="{ active: isActive(conv.uuid) }"
              @click="handleSelectConversation(conv)"
            >
              <div class="conv-icon" :class="{ 'conv-icon-orphan': conv.kb_status === 'deleted' || conv.kb_status === 'unavailable' }" :title="conv.kb_status === 'deleted' ? '知识库已删除' : conv.kb_status === 'unavailable' ? '知识库不可访问' : undefined">
                <i v-if="conv.kb_status === 'deleted'" class="fas fa-exclamation-triangle"></i>
                <i v-else-if="conv.kb_status === 'unavailable'" class="fas fa-lock"></i>
                <i v-else class="fas fa-message"></i>
              </div>
              <div class="conv-info">
                <div v-if="editingId === conv.uuid" class="conv-edit-wrap">
                  <input
                    ref="editInputRef"
                    v-model="editingTitle"
                    class="conv-edit-input"
                    @keydown.enter="handleSaveRename(conv.uuid)"
                    @keydown.escape="cancelRename"
                    @blur="handleSaveRename(conv.uuid)"
                  />
                </div>
                <template v-else>
                  <div class="conv-title">
                    {{ conv.title || '新对话' }}
                  </div>
                  <div class="conv-meta">{{ formatTime(conv.last_message_at || conv.updated_at) }}</div>
                </template>
              </div>
              <div class="conv-actions" v-if="editingId !== conv.uuid">
                <button title="重命名" @click.stop="startRename(conv)">
                  <i class="fas fa-pen"></i>
                </button>
                <button title="删除" @click.stop="handleDelete(conv)">
                  <i class="fas fa-trash"></i>
                </button>
              </div>
            </div>
          </div>
        </template>

        <!-- 会话列表（收起态：仅展示单个历史对话 icon，不可点击，不随会话数量变化） -->
        <template v-else>
          <div class="conv-item conv-item-collapsed conv-item-static" title="历史会话">
            <div class="conv-icon">
              <i class="fas fa-message"></i>
            </div>
          </div>
        </template>
      </div>

      <!-- 知识库导航（所有用户可见） -->
      <nav class="kb-nav">
        <div class="section-label" v-show="!collapsed">知识库</div>
        <router-link
          to="/knowledge-bases"
          class="nav-item"
          active-class="active"
          :title="collapsed ? '我的知识库' : ''"
        >
          <i class="fas fa-database"></i>
          <span v-show="!collapsed">我的知识库</span>
        </router-link>
        <router-link
          to="/knowledge-bases/public"
          class="nav-item"
          active-class="active"
          :title="collapsed ? '公共知识库' : ''"
        >
          <i class="fas fa-globe"></i>
          <span v-show="!collapsed">公共知识库</span>
        </router-link>
      </nav>

    </div>

    <!-- 底部：用户信息 -->
    <div class="sidebar-bottom">
      <div class="user-bar" ref="userBarRef">
        <div
          class="user-avatar"
          :title="collapsed ? '用户菜单' : ''"
          @click.stop="toggleUserMenu"
        >
          {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
        </div>
        <div class="user-info" v-show="!collapsed" @click.stop="toggleUserMenu">
          <div class="user-name">{{ authStore.user?.username || '用户' }}</div>
          <div class="user-role">{{ authStore.isAdmin ? '管理员' : '用户' }}</div>
        </div>

        <!-- 用户菜单卡片 -->
        <div class="user-menu-card" v-show="showUserMenu" @click.stop>
          <!-- 用户信息头部 -->
          <div class="user-menu-header">
            <div class="user-avatar">
              {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
            </div>
            <div class="user-menu-header-info">
              <div class="user-name">{{ authStore.user?.username || '用户' }}</div>
              <div class="user-role">{{ authStore.isAdmin ? '管理员' : '用户' }}</div>
            </div>
          </div>
          <!-- 菜单选项 -->
          <button class="user-menu-item" @click="handleMenuChangePassword">
            <i class="fas fa-lock"></i>
            <span>修改密码</span>
          </button>
          <button
            v-if="authStore.isAdmin"
            class="user-menu-item"
            @click="handleMenuAdmin"
          >
            <i class="fas fa-shield-alt"></i>
            <span>管理后台</span>
          </button>
          <button class="user-menu-item danger" @click="handleMenuLogout">
            <i class="fas fa-sign-out-alt"></i>
            <span>退出登录</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 修改密码弹窗 -->
    <el-dialog
      v-model="changePasswordDialogVisible"
      title="修改密码"
      width="420px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordFormRules"
        label-position="top"
        @submit.prevent="handleChangePassword"
      >
        <el-form-item label="当前密码" prop="oldPassword">
          <el-input
            v-model="passwordForm.oldPassword"
            type="password"
            show-password
            placeholder="请输入当前密码"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="passwordForm.newPassword"
            type="password"
            show-password
            placeholder="请输入新密码，至少 6 位"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            autocomplete="new-password"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="changePasswordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingPassword" @click="handleChangePassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </aside>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useConversationStore } from '@/stores/conversation'
import { changePassword } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()
const convStore = useConversationStore()

/** 侧边栏折叠状态 */
const collapsed = ref(false)

// ===== 用户菜单卡片 =====
const showUserMenu = ref(false)
const userBarRef = ref(null)

/** 切换用户菜单卡片可见性 */
function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}

/** 关闭用户菜单卡片 */
function closeUserMenu() {
  showUserMenu.value = false
}

/** 点击菜单「修改密码」→ 关闭卡片 → 打开改密弹窗 */
function handleMenuChangePassword() {
  closeUserMenu()
  openChangePasswordDialog()
}

/** 点击菜单「管理后台」→ 关闭卡片 → 跳转管理后台 */
function handleMenuAdmin() {
  closeUserMenu()
  router.push('/admin')
}

/** 点击菜单「退出登录」→ 关闭卡片 → 执行退出 */
function handleMenuLogout() {
  closeUserMenu()
  handleLogout()
}

/** 点击文档任意位置关闭用户菜单（排除菜单内部和触发区域） */
function onDocumentClick(e) {
  const userBar = userBarRef.value
  if (userBar && !userBar.contains(e.target)) {
    closeUserMenu()
  }
}

// 菜单打开时注册 document click 监听（setTimeout 推迟避免与打开菜单的同一 click 事件冲突）
watch(showUserMenu, (val) => {
  if (val) {
    setTimeout(() => {
      document.addEventListener('click', onDocumentClick)
    }, 0)
  } else {
    document.removeEventListener('click', onDocumentClick)
  }
})

onMounted(() => {
  // 加载会话列表
  if (authStore.isLoggedIn) {
    convStore.loadConversations()
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
})

// ===== 修改密码弹窗 =====
const changePasswordDialogVisible = ref(false)
const passwordFormRef = ref(null)
const submittingPassword = ref(false)
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

/** 确认密码一致性校验 */
function validateConfirmPassword(rule, value, callback) {
  if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的新密码不一致'))
  } else {
    callback()
  }
}

const passwordFormRules = {
  oldPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

// ===== 重命名相关 =====
const editingId = ref(null)
const editingTitle = ref('')
const editInputRef = ref(null)

function toggleCollapse() {
  collapsed.value = !collapsed.value
}

/** 判断会话是否为当前活跃会话 */
function isActive(convId) {
  return chatStore.conversationId === convId
}

/** 格式化时间（仅显示时:分） */
function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** 新建对话 */
function handleNewChat() {
  chatStore.clearMessages()
  router.push('/chat')
}

/** 选择历史会话（即使已选中也执行导航，解决从其他页面返回时无法点击的问题） */
function handleSelectConversation(conv) {
  router.push(`/chat?conversation_id=${conv.uuid}`)
}

/** 开始重命名 */
async function startRename(conv) {
  editingId.value = conv.uuid
  editingTitle.value = conv.title || ''
  await nextTick()
  // 聚焦输入框
  if (editInputRef.value && editInputRef.value.length > 0) {
    editInputRef.value[0].focus()
    editInputRef.value[0].select()
  }
}

/** 取消重命名 */
function cancelRename() {
  editingId.value = null
  editingTitle.value = ''
}

/** 保存重命名 */
async function handleSaveRename(id) {
  const newTitle = editingTitle.value.trim()
  if (!newTitle) {
    cancelRename()
    return
  }
  try {
    await convStore.renameConversation(id, newTitle)
    ElMessage.success('重命名成功')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '重命名失败')
  } finally {
    cancelRename()
  }
}

/** 删除会话 */
async function handleDelete(conv) {
  try {
    await ElMessageBox.confirm(
      `删除会话「${conv.title || '新对话'}」后不可恢复，是否继续？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await convStore.deleteConversation(conv.uuid)
    // 如果删除的是当前会话，清空并跳转到 /chat
    if (isActive(conv.uuid)) {
      chatStore.clearMessages()
      router.push('/chat')
    }
    ElMessage.success('会话已删除')
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '删除失败')
    }
  }
}

/** 退出登录 */
async function handleLogout() {
  try {
    await ElMessageBox.confirm(
      '退出后需重新登录，是否继续？',
      '确认退出',
      {
        confirmButtonText: '退出',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return // 用户取消，不执行退出
  }
  chatStore.reset()
  await authStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

/** 打开修改密码弹窗（清空表单 + 重置校验） */
function openChangePasswordDialog() {
  passwordForm.oldPassword = ''
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
  if (passwordFormRef.value) {
    passwordFormRef.value.resetFields()
  }
  changePasswordDialogVisible.value = true
}

/** 提交修改密码 */
async function handleChangePassword() {
  if (!passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
  } catch {
    return // 校验失败不提交
  }
  submittingPassword.value = true
  try {
    await changePassword(passwordForm.oldPassword, passwordForm.newPassword)
    ElMessage.success('密码修改成功，请重新登录')
    changePasswordDialogVisible.value = false
    // 改密后吊销全部 refresh_token，清空本地状态并跳转登录
    chatStore.reset()
    await authStore.logout()
    router.push('/login')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '修改失败，请检查当前密码是否正确')
  } finally {
    submittingPassword.value = false
  }
}

</script>

<style scoped>
.sidebar {
  width: var(--dm-sidebar-width-chat);
  background: var(--dm-bg-sidebar);
  border-right: 1px solid var(--dm-border);
  box-shadow: var(--dm-shadow-sidebar);
  display: flex;
  flex-direction: column;
  z-index: 10;
  flex-shrink: 0;
  transition: width var(--dm-transition-normal);
  overflow-x: hidden;
}

/* 用户菜单打开时解除 overflow 裁剪，确保收起态卡片不被截断 */
.sidebar.menu-open {
  overflow-x: visible;
}

/* 收起状态 */
.sidebar.collapsed {
  width: var(--dm-sidebar-width-collapsed);
}

/* ===== 顶部区域 ===== */
.sidebar-top {
  padding: var(--dm-space-5) var(--dm-space-4);
  border-bottom: 1px solid var(--dm-border-light);
  position: relative;
}

/* 折叠切换按钮 */
.collapse-toggle-btn {
  position: absolute;
  top: 14px;
  right: 12px;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--dm-text-tertiary);
  cursor: pointer;
  border-radius: var(--dm-radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--dm-text-xs);
  transition: all var(--dm-transition-fast);
  z-index: 1;
}

.collapse-toggle-btn:hover {
  background: var(--dm-bg-page);
  color: var(--dm-text-primary);
}

/* Logo 区域 */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  margin-bottom: var(--dm-space-4);
}

/* 收起态：Logo 居中且可点击展开 */
.collapsed .sidebar-logo {
  justify-content: center;
  margin-bottom: var(--dm-space-3);
}

.logo-clickable {
  cursor: pointer;
}

.sidebar-logo-icon {
  width: var(--dm-sidebar-logo-size);
  height: var(--dm-sidebar-logo-size);
  background: var(--dm-primary);
  border-radius: var(--dm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: var(--dm-text-sm);
  flex-shrink: 0;
}

.sidebar-logo-text {
  display: flex;
  flex-direction: column;
  line-height: var(--dm-leading-title);
}

.logo-subtitle {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  font-weight: var(--dm-weight-medium);
}

/* 新建对话按钮 */
.new-chat-btn {
  width: 100%;
  height: 38px;
  padding: 0 14px;
  background: var(--dm-bg-card);
  color: var(--dm-text-primary);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-body);
  font-weight: var(--dm-weight-medium);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--dm-space-2);
  transition: all var(--dm-transition-normal);
}

.new-chat-btn:hover {
  background: var(--dm-bg-page);
  border-color: var(--dm-text-primary);
}

.new-chat-btn.active {
  background: var(--dm-primary-light);
  color: var(--dm-primary);
  border-color: var(--dm-primary);
  font-weight: var(--dm-weight-semibold);
}

/* 收起态：仅图标的按钮 */
.new-chat-btn-icon {
  width: var(--dm-sidebar-logo-size);
  height: var(--dm-sidebar-logo-size);
  padding: 0;
  margin: 0 auto;
  border-radius: var(--dm-radius-sm);
}

/* ===== 中间区域 ===== */
.sidebar-middle {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: var(--dm-space-3) var(--dm-space-3);
  min-height: 0;
}

/* 收起态 */
.collapsed .sidebar-middle {
  padding: var(--dm-space-2);
}

/* 会话列表：可滚动区域 */
.conv-section {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.section-label {
  font-size: var(--dm-text-3xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: var(--dm-space-2) var(--dm-space-3);
  margin-top: var(--dm-space-2);
}

/* ===== 会话列表 ===== */
.conv-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--dm-space-2);
  padding: var(--dm-space-6) 0;
  color: var(--dm-text-tertiary);
  font-size: var(--dm-text-xs);
}

.conv-list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--dm-space-2);
  padding: var(--dm-space-8) 0;
  color: var(--dm-text-tertiary);
}

.conv-list-empty .empty-icon {
  font-size: 24px;
  opacity: 0.4;
}

.conv-list-empty .empty-text {
  font-size: var(--dm-text-xs);
}

.conv-group {
  margin-bottom: var(--dm-space-2);
}

.conv-group-label {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
  padding: var(--dm-space-1) var(--dm-space-3);
  font-weight: var(--dm-weight-medium);
}

.conv-item {
  padding: 10px 12px;
  border-radius: var(--dm-radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 2px;
  transition: background var(--dm-transition-fast);
  position: relative;
}

.conv-item:hover {
  background: var(--dm-bg-chat);
}

.conv-item.active {
  background: var(--dm-primary-light);
}

.conv-item.active .conv-title {
  color: var(--dm-primary);
  font-weight: var(--dm-weight-semibold);
}

/* 收起态：居中仅图标，不可点击，仅展示用途 */
.conv-item-collapsed {
  justify-content: center;
  padding: 10px 0;
  cursor: default;
}

.conv-item-collapsed:hover {
  background: transparent;
}

.conv-icon {
  width: 28px;
  height: 28px;
  background: var(--dm-bg-chat);
  border-radius: var(--dm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dm-text-tertiary);
  font-size: var(--dm-text-2xs);
  flex-shrink: 0;
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-meta {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
  margin-top: var(--dm-space-1);
}

/* 孤儿会话图标（替换左侧会话图标） */
.conv-icon-orphan {
  color: var(--dm-orphan-hover-accent);
}

.conv-icon-orphan .fa-lock {
  color: var(--dm-orphan-lock);
}

/* 重命名输入框 */
.conv-edit-wrap {
  display: flex;
}

.conv-edit-input {
  width: 100%;
  height: 24px;
  padding: 0 6px;
  border: 1px solid var(--dm-primary);
  border-radius: var(--dm-radius-xs);
  font-size: var(--dm-text-xs);
  color: var(--dm-text-primary);
  background: var(--dm-bg-card);
  outline: none;
}

.conv-actions {
  opacity: 0;
  transition: opacity var(--dm-transition-fast);
  display: flex;
  gap: var(--dm-space-1);
}

.conv-item:hover .conv-actions {
  opacity: 1;
}

.conv-actions button {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--dm-text-tertiary);
  cursor: pointer;
  border-radius: var(--dm-radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--dm-text-3xs);
}

.conv-actions button:hover {
  background: var(--dm-border);
  color: var(--dm-text-primary);
}

/* ===== 知识库导航 ===== */
.kb-nav {
  flex-shrink: 0;
  border-top: 1px solid var(--dm-border-light);
  margin-top: var(--dm-space-3);
  padding-top: var(--dm-space-1);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  padding: 12px 14px;
  border-radius: var(--dm-radius-sm);
  cursor: pointer;
  transition: all var(--dm-transition-fast);
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
  text-decoration: none;
}

.nav-item:hover {
  background: var(--dm-bg-page);
  color: var(--dm-text-primary);
}

.nav-item.active {
  background: var(--dm-primary-light);
  color: var(--dm-primary);
  font-weight: var(--dm-weight-semibold);
}

.nav-item i {
  width: 20px;
  text-align: center;
  font-size: var(--dm-text-sm);
}

/* 收起态：导航项仅图标居中 */
.collapsed .nav-item {
  justify-content: center;
  padding: 12px 0;
}

.collapsed .nav-item i {
  width: auto;
}

/* ===== 底部区域 ===== */
.sidebar-bottom {
  padding: var(--dm-space-3) var(--dm-space-4);
  border-top: 1px solid var(--dm-border);
}

/* 收起态 */
.collapsed .sidebar-bottom {
  padding: var(--dm-space-3);
}

.user-bar {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  padding: var(--dm-space-2);
  border-radius: var(--dm-radius-sm);
  transition: background var(--dm-transition-fast);
  position: relative;
}

/* 收起态：用户栏居中 */
.collapsed .user-bar {
  justify-content: center;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--dm-radius-full);
  background: var(--dm-text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-semibold);
  flex-shrink: 0;
  cursor: pointer;
  transition: opacity var(--dm-transition-fast);
}

.user-avatar:hover {
  opacity: 0.85;
}

.user-info {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.user-name {
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

/* ===== 用户菜单卡片 ===== */
.user-menu-card {
  position: absolute;
  bottom: 100%;
  right: 0;
  margin-bottom: var(--dm-space-2);
  min-width: 200px;
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  box-shadow: var(--dm-shadow-lg);
  overflow: hidden;
  z-index: 100;
  animation: menuSlideUp var(--dm-transition-normal) ease;
}

/* 收起态：卡片从用户栏右侧弹出，底部对齐用户栏、向上展开 */
.collapsed .user-menu-card {
  left: 100%;
  right: auto;
  bottom: 0;
  top: auto;
  margin-bottom: 0;
  margin-left: var(--dm-space-2);
}

@keyframes menuSlideUp {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

.user-menu-header {
  padding: var(--dm-space-4);
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  border-bottom: 1px solid var(--dm-border-light);
}

.user-menu-header-info {
  flex: 1;
  min-width: 0;
}

.user-menu-item {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  padding: 12px var(--dm-space-4);
  cursor: pointer;
  transition: background var(--dm-transition-fast);
  font-size: var(--dm-text-body);
  color: var(--dm-text-primary);
  border: none;
  background: transparent;
  width: 100%;
  font-family: inherit;
}

.user-menu-item:hover {
  background: var(--dm-bg-page);
}

/* 危险操作项 */
.user-menu-item.danger {
  color: var(--dm-danger);
}

.user-menu-item.danger:hover {
  background: var(--dm-danger-light);
}

.user-menu-item i {
  width: 18px;
  text-align: center;
  font-size: var(--dm-text-sm);
}
</style>
