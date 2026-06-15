<template>
  <div class="admin-layout">
    <!-- Admin 专用侧边栏 -->
    <aside class="admin-sidebar">
      <!-- 顶部：Logo + 标题 -->
      <div class="admin-sidebar-top">
        <div class="admin-logo-icon">
          <i class="fas fa-shield-alt"></i>
        </div>
        <div class="admin-logo-text">
          <span class="admin-title">管理后台</span>
          <span class="admin-subtitle">DocMind Admin</span>
        </div>
      </div>

      <!-- 导航菜单 -->
      <nav class="admin-nav">
        <router-link
          to="/admin/stats"
          class="admin-nav-item"
          active-class="active"
        >
          <i class="fas fa-chart-bar"></i>
          <span>系统统计</span>
        </router-link>
        <router-link
          to="/admin/traces"
          class="admin-nav-item"
          :class="{ active: isTraceActive }"
        >
          <i class="fas fa-search"></i>
          <span>链路追踪</span>
        </router-link>
        <router-link
          to="/admin/knowledge"
          class="admin-nav-item"
          active-class="active"
        >
          <i class="fas fa-database"></i>
          <span>知识库管理</span>
        </router-link>
        <router-link
          to="/admin/documents"
          class="admin-nav-item"
          active-class="active"
        >
          <i class="fas fa-file-alt"></i>
          <span>文档管理</span>
        </router-link>
        <router-link
          to="/admin/users"
          class="admin-nav-item"
          :class="{ active: isUsersActive }"
        >
          <i class="fas fa-users"></i>
          <span>用户管理</span>
        </router-link>
      </nav>

      <!-- 底部：返回对话 -->
      <div class="admin-sidebar-bottom">
        <router-link to="/chat" class="back-to-chat-btn">
          <i class="fas fa-arrow-left"></i>
          <span>返回对话</span>
        </router-link>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="admin-main">
      <header class="admin-header">
        <h1 class="admin-page-title">{{ pageTitle }}</h1>
      </header>
      <main class="admin-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const pageTitle = computed(() => {
  const titles = {
    AdminStats: '系统统计',
    AdminTraces: '链路追踪',
    AdminTraceDetail: 'Trace 详情',
    AdminKnowledge: '知识库管理',
    AdminDocuments: '文档管理',
    AdminUsers: '用户管理',
    AdminUserDetail: '用户详情',
  }
  return titles[route.name] || '管理后台'
})

/** Trace 菜单高亮：列表页和详情页都激活 */
const isTraceActive = computed(() => {
  return route.name === 'AdminTraces' || route.name === 'AdminTraceDetail'
})

/** 用户管理菜单高亮：列表页和详情页都激活 */
const isUsersActive = computed(() => {
  return route.name === 'AdminUsers' || route.name === 'AdminUserDetail'
})
</script>

<style scoped>
.admin-layout {
  width: 100%;
  height: 100vh;
  display: flex;
}

/* ===== Admin 侧边栏 ===== */
.admin-sidebar {
  width: var(--dm-sidebar-width-admin);
  background: var(--dm-bg-sidebar);
  border-right: 1px solid var(--dm-border);
  box-shadow: var(--dm-shadow-sidebar);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  z-index: 10;
}

.admin-sidebar-top {
  padding: var(--dm-space-5) var(--dm-space-4);
  border-bottom: 1px solid var(--dm-border-light);
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
}

.admin-logo-icon {
  width: 36px;
  height: 36px;
  background: var(--dm-primary);
  border-radius: var(--dm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: var(--dm-text-sm);
  flex-shrink: 0;
}

.admin-logo-text {
  display: flex;
  flex-direction: column;
  line-height: var(--dm-leading-title);
}

.admin-title {
  font-size: var(--dm-text-body);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.admin-subtitle {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

/* 导航 */
.admin-nav {
  flex: 1;
  padding: var(--dm-space-3) var(--dm-space-3);
  overflow-y: auto;
}

.admin-nav-item {
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
  margin-bottom: 2px;
}

.admin-nav-item:hover {
  background: var(--dm-bg-page);
  color: var(--dm-text-primary);
}

.admin-nav-item.active {
  background: var(--dm-primary-light);
  color: var(--dm-primary);
  font-weight: var(--dm-weight-semibold);
}

.admin-nav-item i {
  width: 20px;
  text-align: center;
  font-size: var(--dm-text-sm);
}

/* 底部返回按钮 */
.admin-sidebar-bottom {
  padding: var(--dm-space-3) var(--dm-space-4);
  border-top: 1px solid var(--dm-border);
}

.back-to-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--dm-space-2);
  padding: 10px 14px;
  border-radius: var(--dm-radius-sm);
  cursor: pointer;
  transition: all var(--dm-transition-fast);
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
  text-decoration: none;
  background: var(--dm-bg-page);
}

.back-to-chat-btn:hover {
  background: var(--dm-bg-chat);
  color: var(--dm-text-primary);
}

.back-to-chat-btn i {
  font-size: var(--dm-text-sm);
}

/* ===== 主内容区 ===== */
.admin-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--dm-bg-page);
  overflow: hidden;
}

.admin-header {
  height: var(--dm-header-height);
  background: var(--dm-bg-card);
  border-bottom: 1px solid var(--dm-border);
  display: flex;
  align-items: center;
  padding: 0 var(--dm-space-6);
  z-index: 5;
  flex-shrink: 0;
}

.admin-page-title {
  font-size: var(--dm-text-lg);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.admin-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--dm-space-6) 28px;
}
</style>
