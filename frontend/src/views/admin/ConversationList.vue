<template>
  <div class="admin-page">
    <!-- 页面描述（标题已在 AdminLayout header 中展示） -->
    <div class="detail-header">
      <p class="detail-desc">查看用户活跃度和使用情况（按用户维度统计）</p>
    </div>

    <!-- 占位提示 -->
    <div class="empty-state">
      <i class="fas fa-chart-line empty-icon"></i>
      <div class="empty-title">用户活跃统计</div>
      <div class="empty-desc">后端接口排期至后续 Phase 实现，届时将展示以下维度的用户活跃数据：</div>
    </div>

    <!-- 统计维度预览 -->
    <div class="preview-section">
      <h3 class="preview-title">计划展示的统计维度</h3>
      <div class="dimension-grid">
        <div class="dimension-card">
          <i class="fas fa-user"></i>
          <span>用户</span>
          <small>按用户展示活跃度</small>
        </div>
        <div class="dimension-card">
          <i class="fas fa-comments"></i>
          <span>会话数</span>
          <small>每个用户创建的会话</small>
        </div>
        <div class="dimension-card">
          <i class="fas fa-question-circle"></i>
          <span>提问数</span>
          <small>累计问答次数</small>
        </div>
        <div class="dimension-card">
          <i class="fas fa-coins"></i>
          <span>Token 消耗</span>
          <small>LLM Token 用量统计</small>
        </div>
        <div class="dimension-card">
          <i class="fas fa-clock"></i>
          <span>最近访问</span>
          <small>最后活跃时间</small>
        </div>
        <div class="dimension-card">
          <i class="fas fa-exclamation-circle"></i>
          <span>错误率</span>
          <small>问答失败/超时占比</small>
        </div>
        <div class="dimension-card">
          <i class="fas fa-database"></i>
          <span>KB 使用</span>
          <small>各知识库被检索次数</small>
        </div>
      </div>
    </div>

    <!-- 预期表格预览 -->
    <div class="preview-section">
      <h3 class="preview-title">数据表格预览</h3>
      <div class="table-preview">
        <table class="preview-table">
          <thead>
            <tr>
              <th>用户</th>
              <th>会话数</th>
              <th>提问数</th>
              <th>Token 消耗</th>
              <th>最近访问</th>
              <th>错误率</th>
              <th>主要使用的 KB</th>
            </tr>
          </thead>
          <tbody>
            <tr class="placeholder-row">
              <td colspan="7">
                <i class="fas fa-ellipsis-h"></i>
                数据加载后将在此显示用户活跃排行
              </td>
            </tr>
          </tbody>
        </table>
      </div>
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

.detail-desc {
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
  margin-top: var(--dm-space-1);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: var(--dm-space-8) var(--dm-space-5);
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
  max-width: 420px;
  margin: 0 auto;
}

/* 统计维度预览 */
.preview-section {
  margin-top: var(--dm-space-8);
}

.preview-title {
  font-size: var(--dm-text-body);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-4);
  text-align: center;
}

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--dm-space-4);
}

.dimension-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--dm-space-1);
  padding: var(--dm-space-4);
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  text-align: center;
}

.dimension-card i {
  font-size: 20px;
  color: var(--dm-primary);
  margin-bottom: var(--dm-space-1);
}

.dimension-card span {
  font-size: var(--dm-text-body);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
}

.dimension-card small {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

/* 表格预览 */
.table-preview {
  overflow-x: auto;
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--dm-text-xs);
}

.preview-table th {
  background: var(--dm-bg-page);
  padding: 10px 14px;
  text-align: left;
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-secondary);
  border-bottom: 2px solid var(--dm-border);
  white-space: nowrap;
}

.preview-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--dm-border-light);
}

.placeholder-row td {
  text-align: center;
  padding: var(--dm-space-8);
  color: var(--dm-text-tertiary);
}

.placeholder-row i {
  margin-right: var(--dm-space-2);
}
</style>
