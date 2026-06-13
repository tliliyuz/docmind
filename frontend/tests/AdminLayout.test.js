/** AdminLayout 组件测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const { mockUseRoute } = vi.hoisted(() => ({
  mockUseRoute: vi.fn(() => ({ name: 'AdminStats' })),
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({})),
  useRoute: mockUseRoute,
}))

import AdminLayout from '@/components/layout/AdminLayout.vue'

function getComponent(routeName = 'AdminStats') {
  mockUseRoute.mockReturnValue({ name: routeName })
  return mount(AdminLayout, {
    global: {
      stubs: {
        'router-link': {
          template: '<a class="router-link-stub"><slot /></a>',
          props: ['to'],
        },
        'router-view': { template: '<div class="router-view-stub"><slot /></div>' },
      },
    },
  })
}

describe('AdminLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染 Admin 布局容器', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.admin-layout').exists()).toBe(true)
  })

  it('包含 Admin 侧边栏', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.admin-sidebar').exists()).toBe(true)
  })

  it('包含主内容区域', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.admin-main').exists()).toBe(true)
  })

  it('包含顶部标题栏', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.admin-header').exists()).toBe(true)
  })

  it('包含内容区', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.admin-content').exists()).toBe(true)
  })

  it('侧边栏显示"管理后台"标题', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.admin-title').text()).toBe('管理后台')
  })

  it('侧边栏显示副标题', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.admin-subtitle').text()).toBe('DocMind Admin')
  })

  it('AdminStats 路由显示"系统统计"', () => {
    const wrapper = getComponent('AdminStats')
    expect(wrapper.find('.admin-page-title').text()).toBe('系统统计')
  })

  it('AdminKnowledge 路由显示"知识库管理"', () => {
    const wrapper = getComponent('AdminKnowledge')
    expect(wrapper.find('.admin-page-title').text()).toBe('知识库管理')
  })

  it('AdminDocuments 路由显示"文档管理"', () => {
    const wrapper = getComponent('AdminDocuments')
    expect(wrapper.find('.admin-page-title').text()).toBe('文档管理')
  })

  it('AdminActivity 路由已移除，不存在对应标题', () => {
    const wrapper = getComponent('AdminActivity')
    // AdminActivity 已从 pageTitle 映射移除，降级为默认标题
    expect(wrapper.find('.admin-page-title').text()).toBe('管理后台')
  })

  it('未知路由显示默认标题"管理后台"', () => {
    const wrapper = getComponent('UnknownPage')
    expect(wrapper.find('.admin-page-title').text()).toBe('管理后台')
  })

  it('侧边栏包含系统统计导航项', () => {
    const wrapper = getComponent()
    const links = wrapper.findAll('.admin-nav-item')
    const texts = links.map(l => l.text())
    expect(texts).toContain('系统统计')
  })

  it('侧边栏包含知识库管理导航项', () => {
    const wrapper = getComponent()
    const links = wrapper.findAll('.admin-nav-item')
    const texts = links.map(l => l.text())
    expect(texts).toContain('知识库管理')
  })

  it('侧边栏包含文档管理导航项', () => {
    const wrapper = getComponent()
    const links = wrapper.findAll('.admin-nav-item')
    const texts = links.map(l => l.text())
    expect(texts).toContain('文档管理')
  })

  it('侧边栏已移除活跃统计导航项', () => {
    const wrapper = getComponent()
    const links = wrapper.findAll('.admin-nav-item')
    const texts = links.map(l => l.text())
    expect(texts).not.toContain('活跃统计')
    expect(texts).toHaveLength(5)  // 系统统计 + 链路追踪 + 知识库管理 + 文档管理 + 用户管理 + 文档管理
  })

  it('侧边栏包含返回对话按钮', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.back-to-chat-btn').exists()).toBe(true)
  })

  it('返回对话按钮文字正确', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.back-to-chat-btn').text()).toBe('返回对话')
  })

  it('内容区包含 router-view 用于渲染子路由', () => {
    const wrapper = mount(AdminLayout, {
      global: {
        stubs: {
          'router-link': {
            template: '<a class="router-link-stub"><slot /></a>',
            props: ['to'],
          },
          'router-view': {
            template: '<div class="router-view-stub"><slot /></div>',
          },
        },
      },
    })
    expect(wrapper.find('.admin-content .router-view-stub').exists()).toBe(true)
  })
})
