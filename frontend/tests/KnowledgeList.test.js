/** KnowledgeList 组件测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

const { mockPush, mockFetchKbList, mockCreateKb, mockUpdateKb, mockDeleteKb, mockConfirm, mockMsgSuccess, mockMsgError, mockMsgWarning } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockFetchKbList: vi.fn(),
  mockCreateKb: vi.fn(),
  mockUpdateKb: vi.fn(),
  mockDeleteKb: vi.fn(),
  mockConfirm: vi.fn(),
  mockMsgSuccess: vi.fn(),
  mockMsgError: vi.fn(),
  mockMsgWarning: vi.fn(),
}))

// Mock 路由
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({}),
}))

// Mock ElMessageBox / ElMessage
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMsgSuccess, error: mockMsgError, warning: mockMsgWarning },
    ElMessageBox: { confirm: mockConfirm },
  }
})

// 知识库列表数据（mock store 中通过闭包访问）
const mockKbList = []

vi.mock('@/stores/knowledge', () => ({
  useKnowledgeStore: () => ({
    kbList: mockKbList,
    kbLoading: false,
    kbTotal: 0,
    fetchKbList: mockFetchKbList,
    createKb: mockCreateKb,
    updateKb: mockUpdateKb,
    deleteKb: mockDeleteKb,
  }),
  getDepartmentStyle: () => ({
    color: 'var(--dm-hr-color)',
    bg: 'var(--dm-hr-bg)',
    icon: 'fa-users',
    dept: 'hr',
  }),
}))

import KnowledgeList from '@/views/KnowledgeList.vue'

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
  'el-radio-group': true,
  'el-radio': true,
}

function getComponent() {
  return mount(KnowledgeList, {
    global: { stubs: elStubs },
  })
}

describe('KnowledgeList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockKbList.length = 0
  })

  // ==================== 渲染测试 ====================

  it('渲染搜索框和新建按钮', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.search-box-container').exists()).toBe(true)
    expect(wrapper.find('.btn-primary').exists()).toBe(true)
    expect(wrapper.find('.btn-primary').text()).toContain('新建知识库')
  })

  it('渲染新建卡片（虚线样式）', () => {
    mockKbList.push({ uuid: 1, name: '测试库', description: '', doc_count: 0, chunk_count: 0 })
    const wrapper = getComponent()
    expect(wrapper.find('.new-card').exists()).toBe(true)
    expect(wrapper.find('.new-card-text').text()).toBe('新建知识库')
  })

  it('无知识库时显示空状态', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.empty-title').text()).toBe('暂无知识库')
  })

  // ==================== 知识库列表渲染 ====================

  it('有知识库时渲染卡片格子并隐藏空状态', () => {
    mockKbList.push(
      { uuid: 1, name: 'HR制度库', description: '人事相关文档', doc_count: 3, chunk_count: 50 },
      { uuid: 2, name: 'IT文档', description: '技术文档', doc_count: 1, chunk_count: 20 },
    )
    const wrapper = getComponent()
    expect(wrapper.find('.empty-state').exists()).toBe(false)
    expect(wrapper.find('.kb-grid').exists()).toBe(true)
    expect(wrapper.findAll('.kb-card')).toHaveLength(2)
  })

  it('卡片显示知识库名称和描述', () => {
    mockKbList.push({ uuid: 1, name: 'HR制度库', description: '人事相关文档', doc_count: 3, chunk_count: 50 })
    const wrapper = getComponent()
    expect(wrapper.find('.kb-card-name').text()).toBe('HR制度库')
    expect(wrapper.find('.kb-card-desc').text()).toBe('人事相关文档')
  })

  it('卡片显示文档数和分块数', () => {
    mockKbList.push({ uuid: 1, name: 'HR制度库', description: '', doc_count: 3, chunk_count: 50 })
    const wrapper = getComponent()
    const metaItems = wrapper.findAll('.card-meta-item')
    expect(metaItems.length).toBeGreaterThanOrEqual(2)
  })

  it('无描述时显示占位文字', () => {
    mockKbList.push({ uuid: 1, name: '测试库', description: '', doc_count: 0, chunk_count: 0 })
    const wrapper = getComponent()
    expect(wrapper.find('.kb-card-desc').text()).toBe('暂无描述')
  })

  // ==================== 交互测试 ====================

  it('点击新建按钮打开弹窗', async () => {
    const wrapper = getComponent()
    await wrapper.find('.btn-primary').trigger('click')
    await nextTick()
    expect(wrapper.findComponent({ name: 'el-dialog' }).exists()).toBe(true)
  })

  it('点击新建卡片也打开弹窗', async () => {
    mockKbList.push({ uuid: 1, name: '测试库', description: '', doc_count: 0, chunk_count: 0 })
    const wrapper = getComponent()
    await wrapper.find('.new-card').trigger('click')
    await nextTick()
    expect(wrapper.findComponent({ name: 'el-dialog' }).exists()).toBe(true)
  })

  it('点击卡片跳转到详情页', async () => {
    mockKbList.push({ uuid: 5, name: 'HR制度库', description: '', doc_count: 0, chunk_count: 0 })
    const wrapper = getComponent()
    await wrapper.find('.kb-card').trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/knowledge-bases/5')
  })

  // ==================== 生命周期 ====================

  it('组件挂载时调用 fetchKbList', () => {
    getComponent()
    expect(mockFetchKbList).toHaveBeenCalledTimes(1)
  })
})
