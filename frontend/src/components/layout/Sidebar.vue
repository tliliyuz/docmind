<template>
  <aside class="sidebar" :class="{ collapsed }">
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
        :class="{ active: route.path === '/chat' }"
        @click="handleNewChat"
        v-show="!collapsed"
      >
        <i class="fas fa-plus"></i>
        <span>新建对话</span>
      </button>
      <!-- 收起态：仅图标按钮 -->
      <button
        class="new-chat-btn new-chat-btn-icon"
        :class="{ active: route.path === '/chat' }"
        @click="handleNewChat"
        v-show="collapsed"
        title="新建对话"
      >
        <i class="fas fa-plus"></i>
      </button>
    </div>

    <!-- 中间：会话列表区域（Phase 4 实现完整交互） -->
    <div class="sidebar-middle">
      <div class="conv-section">
        <div class="section-label" v-show="!collapsed">历史会话</div>
        <div class="conv-list-empty">
          <i class="fas fa-comments empty-icon"></i>
          <span class="empty-text" v-show="!collapsed">暂无会话</span>
        </div>
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

      <!-- 管理后台导航（仅 admin 可见） -->
      <nav v-if="authStore.isAdmin" class="admin-nav">
        <div class="section-label" v-show="!collapsed">管理后台</div>
        <router-link
          to="/admin/knowledge"
          class="nav-item"
          active-class="active"
          :title="collapsed ? '知识库管理' : ''"
        >
          <i class="fas fa-database"></i>
          <span v-show="!collapsed">知识库管理</span>
        </router-link>
        <router-link
          to="/admin/documents"
          class="nav-item"
          active-class="active"
          :title="collapsed ? '文档管理' : ''"
        >
          <i class="fas fa-file-alt"></i>
          <span v-show="!collapsed">文档管理</span>
        </router-link>
        <router-link
          to="/admin/conversations"
          class="nav-item"
          active-class="active"
          :title="collapsed ? '会话管理' : ''"
        >
          <i class="fas fa-comments"></i>
          <span v-show="!collapsed">会话管理</span>
        </router-link>
      </nav>
    </div>

    <!-- 底部：用户信息 -->
    <div class="sidebar-bottom">
      <div class="user-bar">
        <div class="user-avatar" :title="collapsed ? (authStore.user?.username || '用户') : ''">
          {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
        </div>
        <div class="user-info" v-show="!collapsed">
          <div class="user-name">{{ authStore.user?.username || '用户' }}</div>
          <div class="user-role">{{ authStore.isAdmin ? '管理员' : '用户' }}</div>
        </div>
        <button
          class="logout-btn"
          title="退出登录"
          @click.stop="handleLogout"
          v-show="!collapsed"
        >
          <i class="fas fa-sign-out-alt"></i>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()

/** 侧边栏折叠状态 */
const collapsed = ref(false)

function toggleCollapse() {
  collapsed.value = !collapsed.value
}

function handleNewChat() {
  if (route.path === '/chat') {
    chatStore.clearMessages()
  } else {
    router.push('/chat')
  }
}

function handleLogout() {
  chatStore.reset()
  authStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
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
  width: 40px;
  height: 40px;
  padding: 0;
  margin: 0 auto;
  border-radius: var(--dm-radius-sm);
}

/* ===== 中间区域 ===== */
.sidebar-middle {
  flex: 1;
  overflow-y: auto;
  padding: var(--dm-space-3) var(--dm-space-3);
}

/* 收起态 */
.collapsed .sidebar-middle {
  padding: var(--dm-space-2);
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

/* ===== 知识库导航 ===== */
.kb-nav {
  border-top: 1px solid var(--dm-border-light);
  margin-top: var(--dm-space-3);
  padding-top: var(--dm-space-1);
}

/* ===== 管理导航 ===== */
.admin-nav {
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
}

.user-info {
  flex: 1;
  min-width: 0;
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

.logout-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--dm-text-tertiary);
  cursor: pointer;
  border-radius: var(--dm-radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--dm-transition-fast);
}

.logout-btn:hover {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}
</style>
