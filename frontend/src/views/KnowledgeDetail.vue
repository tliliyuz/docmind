<template>
  <div class="kb-detail-page" v-loading="pageLoading">
    <!-- 页面标题栏 -->
    <div class="detail-header">
      <div class="detail-header-left">
        <button class="back-btn" @click="router.push(backRoute)" title="返回知识库列表">
          <i class="fas fa-arrow-left"></i>
        </button>
        <div class="detail-header-info">
          <h1 class="detail-title">{{ store.currentKb?.name || '加载中...' }}</h1>
          <p class="detail-desc">{{ store.currentKb?.description || '暂无描述' }}</p>
        </div>
      </div>
      <div class="detail-header-actions" v-if="canManage">
        <button v-if="isOwner" class="ghost-btn" @click="openEditDialog">
          <i class="fas fa-pen icon-gap-sm"></i> 编辑
        </button>
        <button class="ghost-btn danger" @click="confirmDeleteKb">
          <i class="fas fa-trash icon-gap-sm"></i> 删除
        </button>
      </div>
      <div class="detail-header-actions" v-else>
        <button class="btn-primary" @click="goToChat">
          <i class="fas fa-comments icon-gap-md"></i> 开始问答
        </button>
      </div>
    </div>

    <!-- KB 统计卡片 -->
    <div class="stat-cards-row">
      <div class="stat-card">
        <div class="stat-icon primary">
          <i class="fas fa-file-alt"></i>
        </div>
        <div>
          <div class="stat-value">{{ store.currentKb?.doc_count ?? '-' }}</div>
          <div class="stat-label">文档总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon success">
          <i class="fas fa-th-large"></i>
        </div>
        <div>
          <div class="stat-value">{{ store.currentKb?.chunk_count ?? '-' }}</div>
          <div class="stat-label">分块总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon warning">
          <i class="fas fa-clock"></i>
        </div>
        <div>
          <div class="stat-value">{{ formatDate(store.currentKb?.created_at) }}</div>
          <div class="stat-label">创建时间</div>
        </div>
      </div>
    </div>

    <!-- 文档上传区域（仅 owner 可见） -->
    <div
      v-if="isOwner"
      class="upload-area"
      :class="{ 'upload-dragover': dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
      @click="triggerFileInput"
    >
      <div class="upload-icon">
        <i class="fas fa-cloud-upload-alt"></i>
      </div>
      <div class="upload-title">拖拽文件到此处，或点击选择文件</div>
      <div class="upload-desc">支持 pdf / docx / md / txt，单文件 ≤ 50MB</div>
      <input
        ref="fileInputRef"
        type="file"
        accept=".pdf,.docx,.md,.txt"
        multiple
        style="display: none"
        @change="onFileChange"
      />
      <!-- 上传进度 -->
      <div v-if="store.uploading" class="upload-progress-bar">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: store.uploadProgress.percent + '%' }"></div>
        </div>
        <div class="progress-info">
          <span>{{ store.uploadProgress.percent }}%</span>
          <span>{{ store.uploadProgress.speed }}</span>
          <span v-if="store.uploadProgress.eta !== '--s'">剩余 {{ store.uploadProgress.eta }}</span>
        </div>
      </div>
    </div>

    <!-- 文档表格区域（owner/admin 可管理；公开 KB 查看者只读） -->
    <div class="doc-table-section" v-if="canManage || isPublicViewer">
      <div class="doc-table-toolbar">
        <h2 class="section-title">文档列表</h2>
        <div class="doc-table-filters">
          <!-- 状态筛选 -->
          <el-select
            v-model="filterStatus"
            placeholder="全部状态"
            clearable
            size="default"
            class="filter-input-180"
            @change="reloadDocList"
          >
            <el-option label="全部状态" value="" />
            <el-option label="已上传" value="uploaded" />
            <el-option label="解析中" value="parsing" />
            <el-option label="分块中" value="chunking" />
            <el-option label="向量化中" value="embedding" />
            <el-option label="写入向量库" value="vector_storing" />
            <el-option label="已完成" value="completed" />
            <el-option label="有警告" value="success_with_warnings" />
            <el-option label="部分失败" value="partial_failed" />
            <el-option label="失败" value="failed" />
            <el-option label="删除中" value="deleting" />
          </el-select>
          <!-- 文件名搜索 -->
          <div class="search-box-container">
            <el-input
              v-model="filterFilename"
              placeholder="搜索文件名..."
              size="default"
              clearable
              @input="reloadDocList"
            >
              <template #prefix>
                <i class="fas fa-search search-icon"></i>
              </template>
            </el-input>
          </div>
          <!-- 排序 -->
          <el-select
            v-model="sortOrder"
            size="default"
            class="filter-input-st"
            @change="reloadDocList"
          >
            <el-option label="最新优先" value="desc" />
            <el-option label="最早优先" value="asc" />
          </el-select>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!store.docLoading && store.docList.length === 0" class="empty-state">
        <i class="fas fa-folder-open empty-icon"></i>
        <div class="empty-title">暂无文档</div>
        <div class="empty-desc">{{ isPublicViewer ? '该知识库暂无文档' : '上传第一个文档开始构建知识库' }}</div>
      </div>

      <!-- 文档表格 -->
      <el-table
        v-else
        :data="store.docList"
        v-loading="store.docLoading"
        class="table-full"
        row-key="uuid"
      >
        <el-table-column prop="filename" label="文件名" min-width="200">
          <template #default="{ row }">
            <span
              class="doc-filename"
              :class="{ clickable: canManage && isTerminal(row.status) && row.chunk_count > 0 }"
              @click.stop="canManage && isTerminal(row.status) && row.chunk_count > 0 && openChunksDialog(row)"
            >
              <i
                v-if="canManage && isTerminal(row.status) && row.chunk_count > 0"
                class="fas doc-filename-icon"
                :class="getFileTypeIcon(row.file_type)"
                @click.stop="openChunksDialog(row)"
              ></i>
              <i v-else class="fas doc-filename-icon" :class="getFileTypeIcon(row.file_type)"></i>
              {{ row.filename }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <span class="file-type-badge">{{ row.file_type?.toUpperCase() }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="100" align="center">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="160" align="center">
          <template #default="{ row }">
            <span class="status-tag" :class="row.status">
              <i :class="'fas ' + getStatusIcon(row.status)"></i>
              {{ getStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="90" align="center">
          <template #default="{ row }">
            {{ isTerminal(row.status) ? (row.chunk_count ?? '-') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="170" align="center">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column v-if="canManage" label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <button
                v-if="isTerminal(row.status) && row.chunk_count > 0"
                class="action-btn"
                title="查看分块"
                @click.stop="openChunksDialog(row)"
              >
                <i class="fas fa-list-ul"></i>
              </button>
              <button
                v-if="row.status === 'partial_failed' || row.status === 'failed'"
                class="action-btn"
                title="重新处理"
                @click.stop="handleReprocess(row)"
              >
                <i class="fas fa-redo-alt"></i>
              </button>
              <button
                class="action-btn danger"
                title="删除"
                :disabled="deletingId === row.uuid"
                @click.stop="confirmDeleteDoc(row)"
              >
                <i :class="deletingId === row.uuid ? 'fas fa-spinner fa-spin' : 'fas fa-trash'"></i>
              </button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div v-if="store.docTotal > pageSize" class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="store.docTotal"
          layout="total, prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <!-- 编辑 KB 弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑知识库"
      width="480px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="editFormRef"
        :model="editFormData"
        :rules="editFormRules"
        label-position="top"
      >
        <el-form-item label="名称" prop="name">
          <el-input
            v-model="editFormData.name"
            placeholder="请输入知识库名称"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="editFormData.description"
            type="textarea"
            placeholder="请输入知识库描述（选填）"
            :rows="3"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="可见性" prop="visibility">
          <el-radio-group v-model="editFormData.visibility">
            <el-radio value="private">
              <i class="fas fa-lock icon-gap-sm text-tertiary"></i>
              私有 — 仅自己和管理员可见
            </el-radio>
            <el-radio value="public">
              <i class="fas fa-globe icon-gap-sm text-tertiary"></i>
              公开 — 所有用户可查看和检索
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="handleEditSubmit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 分块预览弹窗 -->
    <el-dialog
      v-model="chunksDialogVisible"
      :title="`分块预览 — ${chunksDocName}`"
      width="700px"
      destroy-on-close
    >
      <div v-loading="store.chunkLoading">
        <div
          v-for="chunk in store.chunkList"
          :key="chunk.id"
          class="chunk-item"
        >
          <div class="chunk-header">
            <span class="chunk-index">#{{ chunk.chunk_index }}</span>
            <span class="chunk-tokens">{{ chunk.token_count }} tokens</span>
            <span v-if="chunk.metadata?.page" class="chunk-page">第 {{ chunk.metadata.page }} 页</span>
          </div>
          <div class="chunk-content">{{ chunk.preview || chunk.content }}</div>
        </div>
        <!-- 分块分页 -->
        <div v-if="store.chunkTotal > chunkPageSize" class="pagination-wrap section-gap">
          <el-pagination
            v-model:current-page="chunkPage"
            :page-size="chunkPageSize"
            :total="store.chunkTotal"
            layout="prev, pager, next"
            small
            @current-change="onChunkPageChange"
          />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { useKnowledgeStore, TERMINAL_STATUSES, isTerminal } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime, formatFileSize } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = useKnowledgeStore()
const authStore = useAuthStore()

const kbId = computed(() => route.params.uuid)

/** 返回目标路由（根据来源区分公共/私有） */
const backRoute = computed(() => {
  return route.query.from === 'public' ? '/knowledge-bases/public' : '/knowledge-bases'
})

/** 当前用户是否为 KB 所有者 */
const isOwner = computed(() => {
  return store.currentKb?.user_id === authStore.user?.id
})

/** 当前用户是否可管理此 KB（owner 或 admin）
 *  - isOwner: 可上传/编辑/删除 KB + 管理文档
 *  - isAdmin: 可编辑/删除 KB + 查看/删除文档（不可上传）
 *  对齐 PRD.md §5.4 权限分离原则 */
const canManage = computed(() => {
  return isOwner.value || authStore.isAdmin
})

/** 公开 KB 的只读查看者（非 owner 且非 admin，仅可查看文档列表） */
const isPublicViewer = computed(() => {
  return !canManage.value && store.currentKb?.visibility === 'public'
})

// ==================== 页面加载 ====================
const pageLoading = ref(false)

async function loadPage() {
  pageLoading.value = true
  try {
    await store.fetchKbDetail(kbId.value)
    // owner/admin 加载文档列表（含管理操作）；公开 KB 查看者只读文档列表
    if (canManage.value || isPublicViewer.value) {
      await reloadDocList()
      // 仅 owner/admin 对非终态文档启动状态轮询
      if (canManage.value) {
        store.docList.forEach(doc => {
          if (!isTerminal(doc.status)) {
            store.startPolling(kbId.value, doc.uuid)
          }
        })
      }
    }
  } catch (err) {
    // 区分真实权限错误和其他错误（超时/网络/JS异常），避免误导用户
    const status = err?.response?.status
    if (status === 403 || status === 404) {
      ElMessage.error('知识库不存在或无权访问')
      router.push(backRoute.value)
    } else if (err?.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，正在重试...')
      // 超时不跳转，让用户留在当前页重试
    } else {
      console.error('KnowledgeDetail loadPage 失败:', err)
      ElMessage.error(err?.response?.data?.message || '页面加载失败，请刷新重试')
    }
  } finally {
    pageLoading.value = false
  }
}

// ==================== 文档列表 ====================
const filterStatus = ref('')
const filterFilename = ref('')
const sortOrder = ref('desc')
const currentPage = ref(1)
const pageSize = 20
const deletingId = ref(null)  // 正在删除的文档 ID

async function reloadDocList() {
  currentPage.value = 1
  await loadDocPage()
}

async function loadDocPage() {
  const params = { page: currentPage.value, page_size: pageSize, order: sortOrder.value }
  if (filterStatus.value) params.status = filterStatus.value
  if (filterFilename.value) params.filename = filterFilename.value
  await store.fetchDocList(kbId.value, params)
}

function onPageChange(page) {
  currentPage.value = page
  loadDocPage()
}

// ==================== 上传 ====================
const fileInputRef = ref(null)
const dragOver = ref(false)

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onDrop(e) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) uploadFiles(files)
}

function onFileChange(e) {
  const files = e.target.files
  if (files?.length) uploadFiles(files)
  // 重置以允许重复选择同一文件
  e.target.value = ''
}

async function uploadFiles(files) {
  // ── 第一阶段：逐文件校验，分离无冲突文件与需覆盖文件 ──
  const validFiles = []      // 无冲突，可批量上传
  const forceUploadFiles = [] // 有同名冲突且用户确认覆盖，需单文件上传

  for (const file of files) {
    // 校验格式
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'docx', 'md', 'txt'].includes(ext)) {
      if (ext === 'doc') {
        ElMessage.warning(`"${file.name}"：不支持 .doc 格式，请先转换为 .docx`)
      } else {
        ElMessage.warning(`"${file.name}"：格式不支持（仅支持 pdf/docx/md/txt）`)
      }
      continue
    }
    // 校验大小
    if (file.size > 50 * 1024 * 1024) {
      ElMessage.warning(`"${file.name}"：文件超过 50MB 上限`)
      continue
    }

    // 检查同名冲突
    const existing = store.docList.find(d => d.filename === file.name)
    if (existing) {
      if (!isTerminal(existing.status)) {
        ElMessage.warning(`"${file.name}"：同名文档正在处理中，请稍后再试`)
        continue
      }
      try {
        await ElMessageBox.confirm(
          `文档 "${file.name}" 已存在，是否覆盖？`,
          '文件已存在',
          { confirmButtonText: '覆盖', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        continue
      }
      forceUploadFiles.push(file)
    } else {
      validFiles.push(file)
    }
  }

  // ── 第二阶段：有冲突的文件逐个覆盖上传（批量接口不支持 force） ──
  for (const file of forceUploadFiles) {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('force', 'true')
      await store.uploadDoc(kbId.value, formData)
      ElMessage.success(`"${file.name}" 已覆盖上传`)
    } catch (err) {
      const msg = err.response?.data?.message || `"${file.name}" 覆盖上传失败`
      ElMessage.error(msg)
    }
  }

  // ── 第三阶段：无冲突文件批量上传 ──
  if (validFiles.length > 0) {
    const formData = new FormData()
    validFiles.forEach(file => formData.append('files', file))

    try {
      const result = await store.batchUploadDocs(kbId.value, formData)

      // 成功的文件
      if (result.success?.length) {
        const names = result.success.map(d => d.filename).join('、')
        ElMessage.success(`${result.success.length} 个文件上传成功：${names}`)
      }

      // 失败的文件
      if (result.failed?.length) {
        result.failed.forEach(item => {
          ElMessage.error(`"${item.filename}" 上传失败：${item.reason}`)
        })
      }
    } catch (err) {
      const msg = err.response?.data?.message || '批量上传失败'
      ElMessage.error(msg)
    }
  }

  // ── 统一刷新列表并启动轮询 ──
  await reloadDocList()
  store.docList.forEach(doc => {
    if (!isTerminal(doc.status)) {
      store.startPolling(kbId.value, doc.uuid)
    }
  })
}

// ==================== 文档操作 ====================
async function handleReprocess(doc) {
  try {
    await store.reprocessDoc(kbId.value, doc.uuid)
    ElMessage.success('重新处理已提交')
    store.startPolling(kbId.value, doc.uuid)
    await reloadDocList()
  } catch (err) {
    const msg = err.response?.data?.message || '操作失败'
    ElMessage.error(msg)
  }
}

async function confirmDeleteDoc(doc) {
  try {
    await ElMessageBox.confirm(
      `文档 "${doc.filename}" 将被删除，其分块数据不可恢复，是否继续？`,
      '确认删除？',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
  } catch {
    return // 用户取消
  }

  const loadingInstance = ElLoading.service({
    fullscreen: true,
    text: `正在删除「${doc.filename}」…`,
    background: 'rgba(0, 0, 0, 0.5)',
  })
  try {
    await store.removeDoc(kbId.value, doc.uuid)
    store.stopPolling(doc.uuid)
    ElMessage.success('文档已删除')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '删除失败')
  } finally {
    loadingInstance.close()
  }
}

// ==================== KB 编辑 ====================
const editDialogVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref(null)

const editFormData = reactive({ name: '', description: '', visibility: 'private' })
const editFormRules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' },
    { min: 1, max: 50, message: '名称长度 1-50 字符', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (!value || !value.trim()) {
          callback(new Error('知识库名称不能为空'))
        } else if (/^\d+$/.test(value.trim())) {
          callback(new Error('名称不能全为数字，请包含文字或字母'))
        } else if (/^\s+$/.test(value)) {
          callback(new Error('名称不能全为空格'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    }
  ]
}

function openEditDialog() {
  editFormData.name = store.currentKb?.name || ''
  editFormData.description = store.currentKb?.description || ''
  editFormData.visibility = store.currentKb?.visibility || 'private'
  editDialogVisible.value = true
}

async function handleEditSubmit() {
  const valid = await editFormRef.value.validate().catch(() => false)
  if (!valid) return
  editSubmitting.value = true
  try {
    await store.updateKb(kbId.value, { name: editFormData.name, description: editFormData.description, visibility: editFormData.visibility })
    ElMessage.success('知识库已更新')
    editDialogVisible.value = false
  } catch (err) {
    const msg = err.response?.data?.message || '操作失败'
    ElMessage.error(msg)
  } finally {
    editSubmitting.value = false
  }
}

// ==================== KB 删除 ====================
async function confirmDeleteKb() {
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
  } catch {
    return // 用户取消
  }

  const loadingInstance = ElLoading.service({
    fullscreen: true,
    text: `正在删除知识库「${store.currentKb?.name || ''}」…`,
    background: 'rgba(0, 0, 0, 0.5)',
  })
  try {
    await store.deleteKb(kbId.value)
    ElMessage.success('知识库已删除')
    router.push('/knowledge-bases')
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '删除失败')
  } finally {
    loadingInstance.close()
  }
}

// ==================== 分块预览 ====================
const chunksDialogVisible = ref(false)
const chunksDocName = ref('')
let chunksDocId = null
const chunkPage = ref(1)
const chunkPageSize = 20

async function openChunksDialog(doc) {
  chunksDocName.value = doc.filename
  chunksDocId = doc.uuid
  chunkPage.value = 1
  await store.fetchDocChunks(kbId.value, doc.uuid, { page: 1, page_size: chunkPageSize })
  chunksDialogVisible.value = true
}

async function onChunkPageChange(page) {
  chunkPage.value = page
  await store.fetchDocChunks(kbId.value, chunksDocId, {
    page,
    page_size: chunkPageSize
  })
}

// ==================== 导航 ====================
function goToChat() {
  router.push(`/chat?kb_id=${kbId.value}`)
}

// ==================== 文件类型图标 ====================
function getFileTypeIcon(fileType) {
  const iconMap = {
    pdf: 'fa-file-pdf',
    docx: 'fa-file-word',
    doc: 'fa-file-word',
    md: 'fa-file-alt',
    txt: 'fa-file-alt',
  }
  return iconMap[fileType?.toLowerCase()] || 'fa-file'
}

// ==================== 状态标签工具函数 ====================
const STATUS_CONFIG = {
  uploaded:    { label: '已上传',   icon: 'fa-upload' },
  parsing:     { label: '解析中',   icon: 'fa-spinner fa-spin' },
  chunking:    { label: '分块中',   icon: 'fa-spinner fa-spin' },
  embedding:   { label: '向量化中',  icon: 'fa-spinner fa-spin' },
  vector_storing: { label: '写入向量库', icon: 'fa-spinner fa-spin' },
  completed:   { label: '已完成',   icon: 'fa-check-circle' },
  success_with_warnings: { label: '有警告', icon: 'fa-check-circle' },
  partial_failed: { label: '部分失败', icon: 'fa-exclamation-triangle' },
  failed:      { label: '失败',     icon: 'fa-times-circle' },
  deleting:    { label: '删除中',   icon: 'fa-spinner fa-spin' }
}

function getStatusIcon(status) {
  return STATUS_CONFIG[status]?.icon || 'fa-question-circle'
}

function getStatusLabel(status) {
  return STATUS_CONFIG[status]?.label || status
}

// ==================== 格式化工具函数 ====================
function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadPage()
})

onUnmounted(() => {
  store.clearAllPolling()
})
</script>

<style scoped>
.kb-detail-page {
  max-width: var(--dm-content-max-width);
  margin: 0 auto;
}

/* ===== 标题栏 ===== */
.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--dm-space-6);
}

.detail-header-left {
  display: flex;
  align-items: flex-start;
  gap: var(--dm-space-4);
}

.back-btn {
  width: var(--dm-space-9);
  height: var(--dm-space-9);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-xs);
  background: var(--dm-bg-card);
  color: var(--dm-text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--dm-text-body);
  flex-shrink: 0;
  margin-top: 2px;
  transition: all var(--dm-transition-fast);
}

.back-btn:hover {
  border-color: var(--dm-primary);
  color: var(--dm-primary);
  background: var(--dm-primary-light);
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

.detail-header-actions {
  display: flex;
  gap: var(--dm-space-2);
  flex-shrink: 0;
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

/* 幽灵按钮 */
.ghost-btn {
  height: var(--dm-space-8);
  padding: 0 var(--dm-space-3_5);
  background: var(--dm-primary-light);
  color: var(--dm-primary);
  border: none;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-semibold);
  cursor: pointer;
  transition: background var(--dm-transition-fast);
  display: inline-flex;
  align-items: center;
}

.ghost-btn:hover {
  background: var(--dm-primary-hover-light);
}

.ghost-btn.danger {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

.ghost-btn.danger:hover {
  background: var(--dm-danger-light);
}

/* ===== 统计卡片行 ===== */
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
  transition: box-shadow var(--dm-transition-fast);
}

.stat-card:hover {
  box-shadow: var(--dm-shadow-sm);
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

/* ===== 上传区域 ===== */
.upload-area {
  border: 2px dashed var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-10);
  text-align: center;
  cursor: pointer;
  transition: all var(--dm-transition-normal);
  margin-bottom: var(--dm-space-8);
}

.upload-area:hover,
.upload-dragover {
  border-color: var(--dm-primary);
  background: var(--dm-primary-light);
}

.upload-icon {
  width: 56px;
  height: 56px;
  background: var(--dm-primary-light);
  border-radius: var(--dm-radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dm-primary);
  font-size: 22px;
  margin: 0 auto var(--dm-space-4);
}

.upload-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-2);
}

.upload-desc {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-tertiary);
}

/* 上传进度 */
.upload-progress-bar {
  margin-top: var(--dm-space-4);
  max-width: 400px;
  margin-left: auto;
  margin-right: auto;
}

.progress-bar {
  width: 100%;
  height: var(--dm-space-1_5);
  background: var(--dm-border-light);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--dm-primary);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-info {
  display: flex;
  justify-content: center;
  gap: var(--dm-space-4);
  margin-top: var(--dm-space-2);
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-secondary);
}

/* ===== 文档表格区域 ===== */
.doc-table-section {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-5);
}

.doc-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--dm-space-4);
  flex-wrap: wrap;
  gap: var(--dm-space-3);
}

.section-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
}

.doc-table-filters {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
}

.search-box-container {
  width: 200px;
}

/* ===== 表格内样式 ===== */
.doc-filename {
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-2);
  color: var(--dm-text-primary);
  font-weight: var(--dm-weight-medium);
}

.doc-filename-icon {
  color: var(--dm-text-tertiary);
  font-size: 0.9em;
  flex-shrink: 0;
}

.doc-filename.clickable .doc-filename-icon {
  color: var(--dm-primary);
}

.doc-filename.clickable {
  cursor: pointer;
}

.doc-filename.clickable:hover {
  color: var(--dm-primary);
}

.file-type-badge {
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-secondary);
  background: var(--dm-primary-light);
  padding: 2px var(--dm-space-2);
  border-radius: var(--dm-radius-xs);
}

/* 状态标签 — 复用 UIDESIGN §4.8 */
.status-tag {
  padding: var(--dm-space-1) var(--dm-space-2_5);
  border-radius: var(--dm-radius-xs);
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-semibold);
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: var(--dm-space-1);
}

.status-tag.uploaded,
.status-tag.parsing,
.status-tag.chunking,
.status-tag.embedding,
.status-tag.vector_storing {
  background: var(--dm-info-light);
  color: var(--dm-info);
}

.status-tag.completed,
.status-tag.success_with_warnings {
  background: var(--dm-success-light);
  color: var(--dm-success);
}

.status-tag.partial_failed {
  background: var(--dm-warning-light);
  color: var(--dm-warning);
}

.status-tag.failed {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

.status-tag.deleting {
  background: var(--dm-border-light);
  color: var(--dm-text-secondary);
}

/* 操作按钮 */
.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--dm-space-1);
}

.action-btn {
  width: 30px;
  height: 30px;
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

.action-btn:hover {
  background: var(--dm-primary-light);
  color: var(--dm-primary);
}

.action-btn.danger:hover {
  background: var(--dm-danger-light);
  color: var(--dm-danger);
}

/* ===== 分页 ===== */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--dm-space-4);
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

/* ===== 分块预览 ===== */
.chunk-item {
  padding: var(--dm-space-4);
  border: 1px solid var(--dm-border-light);
  border-radius: var(--dm-radius-sm);
  margin-bottom: var(--dm-space-3);
}

.chunk-header {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  margin-bottom: var(--dm-space-2);
}

.chunk-index {
  font-size: var(--dm-text-2xs);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-primary);
  background: var(--dm-primary-light);
  padding: 2px var(--dm-space-2);
  border-radius: var(--dm-radius-xs);
}

.chunk-tokens {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
}

.chunk-page {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-secondary);
  margin-left: auto;
}

.chunk-content {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-secondary);
  line-height: var(--dm-leading-body);
}

/* 工具类 */
.filter-input-180 { width: 180px; }
.filter-input-st  { width: 130px; }
.table-full       { width: 100%; }
.search-icon      { color: var(--dm-text-tertiary); }
.icon-gap-sm      { margin-right: var(--dm-space-1); }
.icon-gap-md      { margin-right: var(--dm-space-1_5); }
.text-tertiary    { color: var(--dm-text-tertiary); }
.section-gap      { margin-top: var(--dm-space-4); }
</style>
