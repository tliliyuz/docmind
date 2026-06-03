<template>
  <aside class="sidebar">
    <!-- 顶部：Logo + 新建对话 -->
    <div class="sidebar-top">
      <div class="sidebar-logo">
        <div class="sidebar-logo-icon">
          <i class="fas fa-brain"></i>
        </div>
        <div class="sidebar-logo-text">
          <span class="logo-title">DocMind</span>
          <span class="logo-subtitle">知识库问答平台</span>
        </div>
      </div>
      <button class="new-chat-btn" :class="{ active: route.path === '/chat' }" @click="handleNewChat">
        <i class="fas fa-plus"></i>
        <span>新建对话</span>
      </button>
    </div>

    <!-- 中间：会话列表区域（Phase 4 实现完整交互） -->
    <div class="sidebar-middle">
      <div class="conv-section">
        <div class="section-label">历史会话</div>
        <div class="conv-list-empty">
          <i class="fas fa-comments empty-icon"></i>
          <span class="empty-text">暂无会话</span>
        </div>
      </div>

      <!-- 知识库导航（所有用户可见） -->
      <nav class="kb-nav">
        <div class="section-label">知识库</div>
        <router-link to="/knowledge-bases" class="nav-item" active-class="active">
          <i class="fas fa-database"></i>
          <span>我的知识库</span>
        </router-link>
        <router-link to="/knowledge-bases/public" class="nav-item" active-class="active">
          <i class="fas fa-globe"></i>
          <span>公共知识库</span>
        </router-link>
      </nav>

      <!-- 管理后台导航（仅 admin 可见） -->
      <nav v-if="authStore.isAdmin" class="admin-nav">
        <div class="section-label">管理后台</div>
        <router-link to="/admin/knowledge" class="nav-item" active-class="active">
          <i class="fas fa-database"></i>
          <span>知识库管理</span>
        </router-link>
        <router-link to="/admin/documents" class="nav-item" active-class="active">
          <i class="fas fa-file-alt"></i>
          <span>文档管理</span>
        </router-link>
        <router-link to="/admin/conversations" class="nav-item" active-class="active">
          <i class="fas fa-comments"></i>
          <span>会话管理</span>
        </router-link>
      </nav>
    </div>

    <!-- 底部：用户信息 -->
    <div class="sidebar-bottom">
      <div class="user-bar">
        <div class="user-avatar">
          {{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}
        </div>
        <div class="user-info">
          <div class="user-name">{{ authStore.user?.username || '用户' }}</div>
          <div class="user-role">{{ authStore.isAdmin ? '管理员' : '用户' }}</div>
        </div>
        <button class="logout-btn" title="退出登录" @click.stop="handleLogout">
          <i class="fas fa-sign-out-alt"></i>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const chatStore = useChatStore()

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
}

/* ===== 顶部区域 ===== */
.sidebar-top {
  padding: var(--dm-space-5) var(--dm-space-4);
  border-bottom: 1px solid var(--dm-border-light);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  margin-bottom: var(--dm-space-4);
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

.logo-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.logo-subtitle {
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-tertiary);
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

/* ===== 中间区域 ===== */
.sidebar-middle {
  flex: 1;
  overflow-y: auto;
  padding: var(--dm-space-3) var(--dm-space-3);
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

/* ===== 底部区域 ===== */
.sidebar-bottom {
  padding: var(--dm-space-3) var(--dm-space-4);
  border-top: 1px solid var(--dm-border);
}

.user-bar {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  padding: var(--dm-space-2);
  border-radius: var(--dm-radius-sm);
  transition: background var(--dm-transition-fast);
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
