/** KnowledgeDetail 组件测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockPush, mockFetchKbDetail, mockFetchDocList, mockUploadDoc, mockRemoveDoc, mockReprocessDoc, mockStartPolling, mockStopPolling, mockClearAllPolling, mockUpdateKb, mockDeleteKb, mockFetchDocChunks, mockConfirm, mockMsgSuccess, mockMsgError, mockMsgWarning } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockFetchKbDetail: vi.fn(),
  mockFetchDocList: vi.fn(),
  mockUploadDoc: vi.fn(),
  mockRemoveDoc: vi.fn(),
  mockReprocessDoc: vi.fn(),
  mockStartPolling: vi.fn(),
  mockStopPolling: vi.fn(),
  mockClearAllPolling: vi.fn(),
  mockUpdateKb: vi.fn(),
  mockDeleteKb: vi.fn(),
  mockFetchDocChunks: vi.fn(),
  mockConfirm: vi.fn(),
  mockMsgSuccess: vi.fn(),
  mockMsgError: vi.fn(),
  mockMsgWarning: vi.fn(),
}))

// Mock 路由
const mockRoute = { params: { uuid: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890' }, query: {} }
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => mockRoute,
}))

// Mock ElMessage / ElMessageBox
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMsgSuccess, error: mockMsgError, warning: mockMsgWarning },
    ElMessageBox: { confirm: mockConfirm },
  }
})

// Mock Auth Store
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 1, username: 'testuser', role: 'user' },
    isAdmin: false,
    isLoggedIn: true,
  }),
}))

// Mock Knowledge Store
const mockDocList = []
const mockKbData = { value: null }

vi.mock('@/stores/knowledge', () => ({
  useKnowledgeStore: () => ({
    currentKb: mockKbData.value,
    kbList: [],
    docList: mockDocList,
    docLoading: false,
    docTotal: 0,
    uploading: false,
    uploadProgress: { percent: 0, speed: 0, eta: '' },
    chunkList: [],
    chunkLoading: false,
    chunkTotal: 0,
    fetchKbDetail: mockFetchKbDetail,
    fetchDocList: mockFetchDocList,
    uploadDoc: mockUploadDoc,
    removeDoc: mockRemoveDoc,
    reprocessDoc: mockReprocessDoc,
    startPolling: mockStartPolling,
    stopPolling: mockStopPolling,
    clearAllPolling: mockClearAllPolling,
    updateKb: mockUpdateKb,
    deleteKb: mockDeleteKb,
    fetchDocChunks: mockFetchDocChunks,
    resetDocState: vi.fn(),
  }),
  TERMINAL_STATUSES: ['completed', 'success_with_warnings', 'partial_failed', 'failed'],
  isTerminal: (s) => ['completed', 'success_with_warnings', 'partial_failed', 'failed'].includes(s),
}))

import KnowledgeDetail from '@/views/KnowledgeDetail.vue'

const elStubs = {
  'el-input': true,
  'el-icon': true,
  'el-dialog': true,
  'el-form': true,
  'el-form-item': true,
  'el-button': true,
  'el-dropdown': true,
  'el-dropdown-menu': true,
  'el-dropdown-item': true,
  'el-select': true,
  'el-option': true,
  'el-table': true,
  'el-table-column': true,
  'el-pagination': true,
  'el-loading': true,
  'el-tooltip': true,
  'el-radio-group': true,
  'el-radio': true,
}

const mockKb = {
  uuid: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  user_id: 1,
  name: 'HR制度库',
  description: '人事相关文档',
  doc_count: 15,
  chunk_count: 340,
  created_at: '2026-05-11T10:30:00',
}

function getComponent() {
  mockKbData.value = mockKb
  return mount(KnowledgeDetail, {
    global: { stubs: elStubs },
  })
}

describe('KnowledgeDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDocList.length = 0
    mockKbData.value = mockKb
  })

  // ==================== 渲染测试 ====================

  it('渲染页面完整结构元素', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.detail-title').exists()).toBe(true)
    expect(wrapper.find('.back-btn').exists()).toBe(true)
    expect(wrapper.find('.upload-desc').exists()).toBe(true)
    expect(wrapper.find('.doc-table-filters').exists()).toBe(true)
    expect(wrapper.find('.doc-table-section').exists()).toBe(true)
    expect(wrapper.find('.detail-header-actions').exists()).toBe(true)
  })

  it('渲染统计卡片（文档数、分块数、创建时间）', () => {
    const wrapper = getComponent()
    const statCards = wrapper.findAll('.stat-card')
    expect(statCards.length).toBe(3)
  })

  it('从公共知识库进入时返回按钮跳转公共知识库列表', async () => {
    mockRoute.query = { from: 'public' }
    const wrapper = getComponent()
    await wrapper.find('.back-btn').trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/knowledge-bases/public')
    mockRoute.query = {}
  })

  it('无 from 参数时返回按钮跳转我的知识库列表', async () => {
    mockRoute.query = {}
    const wrapper = getComponent()
    await wrapper.find('.back-btn').trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/knowledge-bases')
  })

  it('渲染文档上传区域', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.upload-area').exists()).toBe(true)
    expect(wrapper.find('.upload-title').text()).toContain('拖拽文件')
  })

  // ==================== 文档表格测试 ====================

  it('无文档时显示空状态', () => {
    mockDocList.length = 0
    const wrapper = getComponent()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.empty-title').text()).toBe('暂无文档')
  })

  it('有文档时渲染表格并隐藏空状态', () => {
    mockDocList.push(
      { uuid: 'd1111111-1111-1111-1111-111111111111', filename: '入职指南.pdf', file_type: 'pdf', file_size: 204800, status: 'completed', chunk_count: 24, created_at: '2026-05-11T10:35:00' },
      { uuid: 'd2222222-2222-2222-2222-222222222222', filename: '报销制度.md', file_type: 'md', file_size: 51200, status: 'parsing', chunk_count: 0, created_at: '2026-05-11T11:00:00' },
    )
    const wrapper = getComponent()
    expect(wrapper.findComponent({ name: 'el-table' }).exists()).toBe(true)
    expect(wrapper.find('.empty-state').exists()).toBe(false)
  })

  // ==================== 生命周期测试 ====================

  it('组件挂载时获取 KB 详情和文档列表', async () => {
    getComponent()
    await flushPromises()
    expect(mockFetchKbDetail).toHaveBeenCalled()
    expect(mockFetchDocList).toHaveBeenCalled()
  })

  it('卸载时清除所有轮询', () => {
    const wrapper = getComponent()
    wrapper.unmount()
    expect(mockClearAllPolling).toHaveBeenCalled()
  })
})
