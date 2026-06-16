<template>
  <div class="admin-page">
    <!-- 页面描述 -->
    <div class="detail-header">
      <p class="detail-desc">DocMind 平台运行数据总览</p>
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

      <!-- ECharts 图表区域 -->
      <div class="charts-section">
        <!-- 图表加载中 -->
        <div v-if="chartsLoading" v-loading="chartsLoading" style="min-height: 200px;"></div>

        <!-- 图表内容 -->
        <template v-else>
          <TrendChart :data="chartData.trend" />
          <div class="charts-row">
            <LatencyChart :data="chartData.latency" />
            <TokenChart :data="chartData.tokens" />
          </div>
        </template>
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
import { getAdminStats, getTraceStats } from '@/api/admin'
import TrendChart from '@/components/charts/TrendChart.vue'
import LatencyChart from '@/components/charts/LatencyChart.vue'
import TokenChart from '@/components/charts/TokenChart.vue'

const loading = ref(true)
const chartsLoading = ref(true)
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

const chartData = ref({
  trend: [],
  latency: [],
  tokens: [],
})

onMounted(async () => {
  // 并行加载统计数据和图表数据
  await Promise.all([loadStats(), loadChartData()])
})

async function loadStats() {
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
}

async function loadChartData() {
  try {
    // 传递浏览器时区偏移，确保日期分组与用户本地时区对齐
    const tzOffset = -new Date().getTimezoneOffset() // 分钟，UTC+8 → 480
    const { data } = await getTraceStats({ days: 7, tz_offset_minutes: tzOffset })
    if (data.code === '0') {
      chartData.value = {
        trend: data.data.trend || [],
        latency: data.data.latency || [],
        tokens: data.data.tokens || [],
      }
    }
  } catch {
    // 图表加载失败不阻断页面，静默处理
  } finally {
    chartsLoading.value = false
  }
}

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
  width: var(--dm-space-12);
  height: var(--dm-space-12);
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

/* ECharts 图表区域 */
.charts-section {
  margin-bottom: var(--dm-space-8);
}

.charts-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--dm-space-5);
  margin-top: var(--dm-space-5);
}

.empty-state {
  text-align: center;
  padding: var(--dm-space-12) var(--dm-space-5);
  color: var(--dm-text-tertiary);
}

.empty-icon {
  font-size: var(--dm-empty-icon-size);
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
