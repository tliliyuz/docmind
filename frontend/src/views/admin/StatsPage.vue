<template>
  <div class="admin-page">
    <!-- 页面标题栏 -->
    <div class="detail-header">
      <div class="detail-header-left">
        <h1 class="detail-title">系统概览</h1>
        <p class="detail-desc">DocMind 平台运行概览统计</p>
      </div>
    </div>

    <!-- 加载中骨架 -->
    <div v-if="loading" v-loading="loading" style="min-height: 300px;"></div>

    <!-- 统计内容 -->
    <template v-else>
      <!-- 核心统计卡片 -->
      <div class="stat-cards-row">
        <div class="stat-card">
          <div class="stat-icon primary">
            <i class="fas fa-users"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(stats.user_count) }}</div>
            <div class="stat-label">用户总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon success">
            <i class="fas fa-database"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(stats.kb_count) }}</div>
            <div class="stat-label">知识库数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon warning">
            <i class="fas fa-file-alt"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(stats.doc_count) }}</div>
            <div class="stat-label">文档总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon danger">
            <i class="fas fa-comments"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(stats.conversation_count) }}</div>
            <div class="stat-label">总会话数</div>
          </div>
        </div>
      </div>

      <!-- 二级统计卡片 -->
      <div class="stat-cards-row secondary">
        <div class="stat-card">
          <div class="stat-icon info">
            <i class="fas fa-th-large"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(stats.chunk_count) }}</div>
            <div class="stat-label">分块总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon info">
            <i class="fas fa-envelope"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatNumber(stats.message_count) }}</div>
            <div class="stat-label">消息总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon info">
            <i class="fas fa-hdd"></i>
          </div>
          <div>
            <div class="stat-value">{{ formatStorage(stats.storage_bytes) }}</div>
            <div class="stat-label">存储空间</div>
          </div>
        </div>
      </div>

      <!-- 快捷入口 -->
      <div class="quick-links">
        <h3 class="section-title">快捷管理入口</h3>
        <div class="quick-links-row">
          <router-link to="/admin/knowledge" class="quick-link-card">
            <i class="fas fa-database"></i>
            <span>知识库管理</span>
            <span class="quick-link-desc">查看所有用户的知识库</span>
          </router-link>
          <router-link to="/admin/documents" class="quick-link-card">
            <i class="fas fa-file-alt"></i>
            <span>文档管理</span>
            <span class="quick-link-desc">跨库查看全部文档</span>
          </router-link>
        </div>
      </div>
    </template>

    <!-- 错误状态 -->
    <div v-if="error" class="empty-state">
      <i class="fas fa-exclamation-circle empty-icon" style="color: var(--dm-danger);"></i>
      <div class="empty-title">数据加载失败</div>
      <div class="empty-desc">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getAdminStats } from '@/api/admin'

const loading = ref(true)
const error = ref('')
const stats = ref({
  user_count: 0,
  kb_count: 0,
  doc_count: 0,
  chunk_count: 0,
  conversation_count: 0,
  message_count: 0,
  storage_bytes: 0,
})

onMounted(async () => {
  try {
    const { data } = await getAdminStats()
    if (data.code === '0') {
      stats.value = data.data
    } else {
      error.value = data.message || '获取统计数据失败'
    }
  } catch (e) {
    error.value = e.response?.data?.message || '网络异常，请稍后重试'
  } finally {
    loading.value = false
  }
})

/** 格式化数字（千分位） */
function formatNumber(val) {
  if (val == null) return '--'
  return Number(val).toLocaleString()
}

/** 格式化存储空间（字节 → 可读格式） */
function formatStorage(bytes) {
  if (bytes == null) return '--'
  const num = Number(bytes)
  if (num === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(num) / Math.log(1024)), units.length - 1)
  return (num / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}
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

.detail-title {
  font-size: var(--dm-text-xl);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
  line-height: var(--dm-leading-title);
}

.detail-desc {
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
  margin-top: var(--dm-space-1);
}

.stat-cards-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--dm-space-5);
  margin-bottom: var(--dm-space-5);
}

.stat-cards-row.secondary {
  grid-template-columns: repeat(3, 1fr);
  margin-bottom: var(--dm-space-8);
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
  width: 48px;
  height: 48px;
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

/* 快捷入口 */
.quick-links {
  margin-top: var(--dm-space-2);
}

.section-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-4);
}

.quick-links-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--dm-space-4);
}

.quick-link-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--dm-space-2);
  padding: var(--dm-space-6);
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  text-decoration: none;
  color: var(--dm-text-primary);
  transition: all var(--dm-transition-fast);
}

.quick-link-card:hover {
  border-color: var(--dm-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.quick-link-card i {
  font-size: 24px;
  color: var(--dm-primary);
}

.quick-link-card span:first-of-type {
  font-weight: var(--dm-weight-semibold);
  font-size: var(--dm-text-body);
}

.quick-link-desc {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-tertiary);
}

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
