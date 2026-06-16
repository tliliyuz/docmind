<template>
  <div class="pub-kb-page">
    <!-- 页面标题 -->
    <div class="page-toolbar">
      <h1 class="page-title">公共知识库</h1>
      <div class="search-box-container">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索知识库..."
          size="default"
          clearable
          @input="onSearch"
        >
          <template #prefix>
            <i class="fas fa-search" style="color: var(--dm-text-tertiary);"></i>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="store.publicKbLoading" class="loading-wrap">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p class="loading-text">加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="filteredList.length === 0 && !searchKeyword" class="empty-state">
      <i class="fas fa-globe empty-icon"></i>
      <div class="empty-title">暂无公开知识库</div>
      <div class="empty-desc">还没有用户分享公开知识库</div>
    </div>

    <!-- 搜索无结果 -->
    <div v-else-if="filteredList.length === 0" class="empty-state">
      <i class="fas fa-search empty-icon"></i>
      <div class="empty-title">未找到匹配的知识库</div>
      <div class="empty-desc">请尝试其他关键词</div>
    </div>

    <!-- 知识库卡片网格 -->
    <div v-else class="kb-grid">
      <div
        v-for="kb in filteredList"
        :key="kb.uuid"
        class="card card-clickable kb-card"
        @click="goDetail(kb.uuid)"
      >
        <div class="kb-card-header">
          <div
            class="kb-icon"
            :class="getDepartmentStyle(kb.name).dept"
          >
            <i :class="'fas ' + getDepartmentStyle(kb.name).icon"></i>
          </div>
        </div>

        <h3 class="kb-card-name">{{ kb.name }}</h3>
        <p class="kb-card-desc">{{ kb.description || '暂无描述' }}</p>

        <div class="kb-card-tags">
          <span class="visibility-tag public">
            <i class="fas fa-globe"></i> 公开
          </span>
          <span class="owner-tag">
            <i class="fas fa-user"></i> {{ kb.username || '未知用户' }}
          </span>
        </div>

        <div class="card-meta">
          <div class="card-meta-item">
            <i class="fas fa-file-alt"></i>
            <span>{{ kb.doc_count }} 个文档</span>
          </div>
          <div class="card-meta-item">
            <i class="fas fa-th-large"></i>
            <span>{{ kb.chunk_count }} 个分块</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import { useKnowledgeStore, getDepartmentStyle } from '@/stores/knowledge'

const router = useRouter()
const store = useKnowledgeStore()

// ==================== 搜索 ====================
const searchKeyword = ref('')

const filteredList = computed(() => {
  if (!searchKeyword.value) return store.publicKbList
  const kw = searchKeyword.value.toLowerCase()
  return store.publicKbList.filter(kb => kb.name.toLowerCase().includes(kw))
})

function onSearch() {
  // 本地过滤
}

// ==================== 导航 ====================
function goDetail(id) {
  router.push(`/knowledge-bases/${id}?from=public`)
}

// ==================== 初始化 ====================
onMounted(() => {
  store.fetchPublicKbList()
})
</script>

<style scoped>
.pub-kb-page {
  max-width: var(--dm-content-max-width);
  margin: 0 auto;
}

/* ===== 工具栏 ===== */
.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--dm-space-6);
}

.page-title {
  font-size: var(--dm-text-lg);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.search-box-container {
  width: 280px;
}

/* ===== 加载状态 ===== */
.loading-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--dm-space-12) 0;
  color: var(--dm-text-tertiary);
}

.loading-text {
  margin-top: var(--dm-space-3);
  font-size: var(--dm-text-body);
}

/* ===== 空状态 ===== */
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

/* ===== 卡片网格 ===== */
.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--dm-space-5);
}

/* 知识库卡片 */
.kb-card {
  padding: var(--dm-space-5);
  display: flex;
  flex-direction: column;
  min-height: 190px;
}

.kb-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--dm-space-3);
}

.kb-card-name {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-card-desc {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  line-height: var(--dm-leading-body);
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 卡片标签行 */
.kb-card-tags {
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
  margin-top: var(--dm-space-2);
  margin-bottom: var(--dm-space-2);
}

.visibility-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-1);
  padding: 2px var(--dm-space-2);
  border-radius: var(--dm-radius-xs);
  font-size: var(--dm-text-3xs);
  font-weight: var(--dm-weight-semibold);
}

.visibility-tag.public {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.owner-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-1);
  padding: 2px var(--dm-space-2);
  border-radius: var(--dm-radius-xs);
  font-size: var(--dm-text-3xs);
  font-weight: var(--dm-weight-medium);
  background: var(--dm-primary-light);
  color: var(--dm-text-secondary);
}

/* 部门图标 */
.kb-icon {
  width: var(--dm-space-11);
  height: var(--dm-space-11);
  border-radius: var(--dm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--dm-text-lg);
  flex-shrink: 0;
}

.kb-icon.hr      { background: var(--dm-hr-bg);      color: var(--dm-hr-color); }
.kb-icon.it      { background: var(--dm-it-bg);      color: var(--dm-it-color); }
.kb-icon.admin   { background: var(--dm-admin-bg);   color: var(--dm-admin-color); }
.kb-icon.biz     { background: var(--dm-biz-bg);     color: var(--dm-biz-color); }
.kb-icon.finance { background: var(--dm-finance-bg); color: var(--dm-finance-color); }
.kb-icon.default { background: var(--dm-primary-light); color: var(--dm-primary); }

/* 卡片元信息行 */
.card {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  transition: all var(--dm-transition-normal);
}

.card:hover {
  border-color: var(--dm-primary);
  box-shadow: var(--dm-shadow-md);
  transform: translateY(-2px);
}

.card-clickable { cursor: pointer; }
.card-clickable:active { transform: translateY(0); }

.card-meta {
  display: flex;
  align-items: center;
  gap: var(--dm-space-4);
  padding-top: var(--dm-space-3_5);
  margin-top: auto;
  border-top: 1px solid var(--dm-border-light);
}

.card-meta-item {
  display: flex;
  align-items: center;
  gap: var(--dm-space-1_5);
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-tertiary);
}

.card-meta-item i {
  font-size: var(--dm-text-xs);
}
</style>
