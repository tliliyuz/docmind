<template>
  <div class="app-layout">
    <Sidebar />
    <div class="main-area">
      <header class="top-header">
        <h1 class="page-title">{{ pageTitle }}</h1>
      </header>
      <main class="content-scroll" :class="{ 'chat-active': route.name === 'Chat' }">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from './Sidebar.vue'

const route = useRoute()

const pageTitle = computed(() => {
  const titles = {
    Chat: 'DocMind',
    KnowledgeList: '我的知识库',
    KnowledgeDetail: '知识库详情',
    AdminKnowledge: '知识库管理',
    AdminDocuments: '文档管理',
    AdminConversations: '会话管理',
    AdminStats: '系统概览'
  }
  return titles[route.name] || 'DocMind'
})
</script>

<style scoped>
.app-layout {
  width: 100%;
  height: 100vh;
  display: flex;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--dm-bg-page);
  overflow: hidden;
}

.top-header {
  height: var(--dm-header-height);
  background: var(--dm-bg-card);
  border-bottom: 1px solid var(--dm-border);
  display: flex;
  align-items: center;
  padding: 0 var(--dm-space-6);
  z-index: 5;
  flex-shrink: 0;
}

.page-title {
  font-size: var(--dm-text-lg);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  padding: var(--dm-space-6) 28px;
}

/* 聊天页内部自行管理滚动，父容器不产生滚动条 */
.content-scroll.chat-active {
  overflow-y: hidden;
  padding: 0;
}
</style>
