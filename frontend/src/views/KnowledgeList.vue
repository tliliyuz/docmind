<template>
  <div class="kb-list-page">
    <!-- 顶部操作栏 -->
    <div class="page-toolbar">
      <div class="search-box-container">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索知识库..."
          size="default"
          clearable
          @input="onSearch"
        >
          <template #prefix>
            <i class="fas fa-search" style="color: var(--dm-text-tertiary)"></i>
          </template>
        </el-input>
      </div>
      <button class="btn-primary" @click="openCreateDialog">
        <i class="fas fa-plus"></i>
        <span>新建知识库</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="store.kbLoading" class="loading-wrap">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p class="loading-text">加载中...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="filteredList.length === 0 && !searchKeyword" class="empty-state">
      <i class="fas fa-database empty-icon"></i>
      <div class="empty-title">暂无知识库</div>
      <div class="empty-desc">点击「新建知识库」开始上传文档</div>
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
        :key="kb.id"
        class="card card-clickable kb-card"
        @click="goDetail(kb.id)"
      >
        <div class="kb-card-header">
          <div
            class="kb-icon"
            :class="getDepartmentStyle(kb.name).dept"
          >
            <i :class="'fas ' + getDepartmentStyle(kb.name).icon"></i>
          </div>
          <el-dropdown trigger="click" @command="(cmd) => onCommand(cmd, kb)">
            <button class="kb-more-btn" @click.stop>
              <i class="fas fa-ellipsis-v"></i>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">
                  <i class="fas fa-pen" style="margin-right: 8px; width: 14px;"></i>
                  编辑
                </el-dropdown-item>
                <el-dropdown-item command="delete" divided>
                  <i class="fas fa-trash" style="margin-right: 8px; width: 14px; color: var(--dm-danger);"></i>
                  <span style="color: var(--dm-danger);">删除</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <h3 class="kb-card-name">{{ kb.name }}</h3>
        <p class="kb-card-desc">{{ kb.description || '暂无描述' }}</p>

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

      <!-- 新建卡片（虚线） -->
      <div class="new-card" @click="openCreateDialog">
        <div class="new-card-icon">
          <i class="fas fa-plus"></i>
        </div>
        <span class="new-card-text">新建知识库</span>
      </div>
    </div>

    <!-- 创建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑知识库' : '新建知识库'"
      width="480px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-position="top"
        @submit.prevent="handleSubmit"
      >
        <el-form-item label="名称" prop="name">
          <el-input
            v-model="formData.name"
            placeholder="请输入知识库名称"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            placeholder="请输入知识库描述（选填）"
            :rows="3"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useKnowledgeStore, getDepartmentStyle } from '@/stores/knowledge'

const router = useRouter()
const store = useKnowledgeStore()

// ==================== 搜索 ====================
const searchKeyword = ref('')

const filteredList = computed(() => {
  if (!searchKeyword.value) return store.kbList
  const kw = searchKeyword.value.toLowerCase()
  return store.kbList.filter(kb => kb.name.toLowerCase().includes(kw))
})

function onSearch() {
  // 本地过滤，无需请求后端
}

// ==================== 弹窗 ====================
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const submitting = ref(false)
const formRef = ref(null)

const formData = ref({
  name: '',
  description: ''
})

const formRules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' },
    { min: 1, max: 50, message: '名称长度 1-50 字符', trigger: 'blur' }
  ]
}

function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  formData.value = { name: '', description: '' }
  dialogVisible.value = true
}

function openEditDialog(kb) {
  isEditing.value = true
  editingId.value = kb.id
  formData.value = { name: kb.name, description: kb.description || '' }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEditing.value) {
      await store.updateKb(editingId.value, { ...formData.value })
      ElMessage.success('知识库已更新')
    } else {
      await store.createKb({ ...formData.value })
      ElMessage.success('知识库创建成功')
    }
    dialogVisible.value = false
  } catch (err) {
    const msg = err.response?.data?.message || '操作失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

// ==================== 操作菜单 ====================
function onCommand(cmd, kb) {
  if (cmd === 'edit') {
    openEditDialog(kb)
  } else if (cmd === 'delete') {
    confirmDelete(kb)
  }
}

async function confirmDelete(kb) {
  try {
    await ElMessageBox.confirm(
      `删除后该知识库下的所有文档和分块数据将不可恢复，是否继续？`,
      '确认删除？',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    await store.deleteKb(kb.id)
    ElMessage.success('知识库已删除')
  } catch {
    // 取消操作
  }
}

// ==================== 导航 ====================
function goDetail(id) {
  router.push(`/knowledge-bases/${id}`)
}

// ==================== 初始化 ====================
onMounted(() => {
  store.fetchKbList()
})
</script>

<style scoped>
.kb-list-page {
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

.search-box-container {
  width: 280px;
}

/* 主按钮 */
.btn-primary {
  height: 38px;
  padding: 0 18px;
  background: var(--dm-primary);
  color: white;
  border: none;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-body);
  font-weight: var(--dm-weight-semibold);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-2);
  transition: all var(--dm-transition-normal);
}

.btn-primary:hover {
  background: var(--dm-primary-hover);
  box-shadow: var(--dm-shadow-sm);
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

/* 部门图标 */
.kb-icon {
  width: 44px;
  height: 44px;
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

/* 更多按钮 */
.kb-more-btn {
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
  font-size: var(--dm-text-body);
  transition: all var(--dm-transition-fast);
}

.kb-more-btn:hover {
  background: var(--dm-border-light);
  color: var(--dm-text-primary);
}

/* 卡片元信息行 — 复用 UIDESIGN §4.3 */
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
  padding-top: 14px;
  margin-top: auto;
  border-top: 1px solid var(--dm-border-light);
}

.card-meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-tertiary);
}

.card-meta-item i {
  font-size: var(--dm-text-xs);
}

/* 新建卡片 — 虚线 */
.new-card {
  border: 2px dashed var(--dm-border);
  border-radius: var(--dm-radius-md);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 190px;
  cursor: pointer;
  transition: all var(--dm-transition-normal);
}

.new-card:hover {
  border-color: var(--dm-primary);
  background: var(--dm-primary-light);
}

.new-card-icon {
  width: 48px;
  height: 48px;
  background: var(--dm-primary-light);
  border-radius: var(--dm-radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dm-primary);
  font-size: 22px;
  margin-bottom: var(--dm-space-4);
}

.new-card-text {
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
}
</style>
