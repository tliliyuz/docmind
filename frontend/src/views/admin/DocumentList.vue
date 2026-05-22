<template>
  <div class="admin-page">
    <!-- 页面标题栏 -->
    <div class="detail-header">
      <div class="detail-header-left">
        <h1 class="detail-title">文档管理</h1>
        <p class="detail-desc">查看所有文档（跨知识库管理）</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-cards-row">
      <div class="stat-card">
        <div class="stat-icon primary">
          <i class="fas fa-file-alt"></i>
        </div>
        <div>
          <div class="stat-value">--</div>
          <div class="stat-label">文档总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon success">
          <i class="fas fa-check-circle"></i>
        </div>
        <div>
          <div class="stat-value">--</div>
          <div class="stat-label">已完成</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon warning">
          <i class="fas fa-exclamation-triangle"></i>
        </div>
        <div>
          <div class="stat-value">--</div>
          <div class="stat-label">异常文档</div>
        </div>
      </div>
    </div>

    <!-- 占位提示 -->
    <div class="empty-state">
      <i class="fas fa-tools empty-icon"></i>
      <div class="empty-title">管理后台 — 文档管理</div>
      <div class="empty-desc">后端接口排期至 Phase 5 实现，当前为前端占位页面</div>
    </div>
  </div>
</template>

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
  grid-template-columns: repeat(3, 1fr);
  gap: var(--dm-space-5);
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
