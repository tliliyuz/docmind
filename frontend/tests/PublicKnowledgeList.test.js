/** PublicKnowledgeList 组件测试 — ROADMAP §4.4 C5.1-C5.4 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockPush, mockFetchPublicKbList } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockFetchPublicKbList: vi.fn(),
}))

// Mock 路由
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({}),
}))

// 公开知识库列表数据（mock store 中通过闭包访问）
const mockPublicKbList = []

vi.mock('@/stores/knowledge', () => ({
  useKnowledgeStore: () => ({
    publicKbList: mockPublicKbList,
    publicKbLoading: false,
    publicKbTotal: 0,
    fetchPublicKbList: mockFetchPublicKbList,
  }),
  getDepartmentStyle: () => ({
    color: 'var(--dm-hr-color)',
    bg: 'var(--dm-hr-bg)',
    icon: 'fa-users',
    dept: 'hr',
  }),
}))

import PublicKnowledgeList from '@/views/PublicKnowledgeList.vue'

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
  return mount(PublicKnowledgeList, {
    global: { stubs: elStubs },
  })
}

describe('PublicKnowledgeList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPublicKbList.length = 0
  })

  // ==================== 渲染测试 ====================

  it('C5.1 渲染页面标题和搜索框', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.page-title').text()).toBe('公共知识库')
    expect(wrapper.find('.search-box-container').exists()).toBe(true)
  })

  it('C5.1 不包含新建知识库按钮', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.btn-primary').exists()).toBe(false)
  })

  it('C5.1 不包含新建卡片（虚线）', () => {
    mockPublicKbList.push({
      id: 1, name: '公开库', description: '', username: 'zhangsan',
      doc_count: 3, chunk_count: 50, visibility: 'public'
    })
    const wrapper = getComponent()
    expect(wrapper.find('.new-card').exists()).toBe(false)
  })

  it('C5.2 无公开知识库时显示空状态', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.empty-title').text()).toBe('暂无公开知识库')
  })

  // ==================== 列表渲染测试 ====================

  it('C5.3 有公开知识库时渲染卡片网格', () => {
    mockPublicKbList.push(
      { id: 1, name: 'HR制度库', description: '人事文档', username: 'zhangsan', doc_count: 3, chunk_count: 50, visibility: 'public' },
      { id: 2, name: 'IT文档', description: '技术文档', username: 'lisi', doc_count: 1, chunk_count: 20, visibility: 'public' },
    )
    const wrapper = getComponent()
    expect(wrapper.find('.empty-state').exists()).toBe(false)
    expect(wrapper.find('.kb-grid').exists()).toBe(true)
    expect(wrapper.findAll('.kb-card')).toHaveLength(2)
  })

  it('C5.3 卡片显示知识库名称和 owner 用户名', () => {
    mockPublicKbList.push({
      id: 1, name: 'HR制度库', description: '人事相关文档',
      username: 'zhangsan', doc_count: 3, chunk_count: 50, visibility: 'public'
    })
    const wrapper = getComponent()
    expect(wrapper.find('.kb-card-name').text()).toBe('HR制度库')
    expect(wrapper.find('.owner-tag').text()).toContain('zhangsan')
  })

  it('C5.3 卡片显示公开标识', () => {
    mockPublicKbList.push({
      id: 1, name: '测试库', description: '', username: 'zhangsan',
      doc_count: 0, chunk_count: 0, visibility: 'public'
    })
    const wrapper = getComponent()
    expect(wrapper.find('.visibility-tag.public').text()).toContain('公开')
  })

  it('C5.3 卡片无操作菜单（无编辑/删除按钮）', () => {
    mockPublicKbList.push({
      id: 1, name: '测试库', description: '', username: 'zhangsan',
      doc_count: 0, chunk_count: 0, visibility: 'public'
    })
    const wrapper = getComponent()
    // 没有 el-dropdown 组件（操作菜单）
    expect(wrapper.findComponent({ name: 'el-dropdown' }).exists()).toBe(false)
  })

  it('C5.4 点击卡片跳转到详情页', async () => {
    mockPublicKbList.push({
      id: 8, name: '公开库', description: '', username: 'zhangsan',
      doc_count: 1, chunk_count: 10, visibility: 'public'
    })
    const wrapper = getComponent()
    await wrapper.find('.kb-card').trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/knowledge-bases/8')
  })

  // ==================== 生命周期测试 ====================

  it('组件挂载时调用 fetchPublicKbList', () => {
    getComponent()
    expect(mockFetchPublicKbList).toHaveBeenCalledTimes(1)
  })
})
