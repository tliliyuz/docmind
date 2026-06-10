/** AppLayout 组件测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const { mockUseRoute } = vi.hoisted(() => ({
  mockUseRoute: vi.fn(() => ({ name: 'Chat' })),
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({})),
  useRoute: mockUseRoute,
}))

import AppLayout from '@/components/layout/AppLayout.vue'

function getComponent(routeName = 'Chat') {
  mockUseRoute.mockReturnValue({ name: routeName })
  return mount(AppLayout, {
    global: {
      stubs: {
        Sidebar: { template: '<div class="sidebar-stub">Sidebar</div>' },
      },
    },
  })
}

describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染布局容器', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.app-layout').exists()).toBe(true)
  })

  it('包含 Sidebar 区域', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.sidebar-stub').exists()).toBe(true)
  })

  it('包含主内容区域', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.main-area').exists()).toBe(true)
  })

  it('包含顶部标题栏', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.top-header').exists()).toBe(true)
  })

  it('包含内容滚动区', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.content-scroll').exists()).toBe(true)
  })

  it('Chat 路由显示"DocMind"', () => {
    const wrapper = getComponent('Chat')
    expect(wrapper.find('.page-title').text()).toBe('DocMind')
  })

  it('KnowledgeList 路由显示"我的知识库"', () => {
    const wrapper = getComponent('KnowledgeList')
    expect(wrapper.find('.page-title').text()).toBe('我的知识库')
  })

  it('KnowledgeDetail 路由显示"知识库详情"', () => {
    const wrapper = getComponent('KnowledgeDetail')
    expect(wrapper.find('.page-title').text()).toBe('知识库详情')
  })

  it('Admin 路由不再由 AppLayout 渲染，退化为默认标题"DocMind"', () => {
    // Admin 路由现在使用独立的 AdminLayout，AppLayout 不再识别这些路由名称
    const wrapper = getComponent('AdminStats')
    expect(wrapper.find('.page-title').text()).toBe('DocMind')
  })

  it('未知路由显示默认标题"DocMind"', () => {
    const wrapper = getComponent('UnknownPage')
    expect(wrapper.find('.page-title').text()).toBe('DocMind')
  })

  it('slot 内容正确渲染', () => {
    const wrapper = mount(AppLayout, {
      global: {
        stubs: {
          Sidebar: { template: '<div class="sidebar-stub">Sidebar</div>' },
        },
      },
      slots: {
        default: '<div class="child-content">子页面内容</div>',
      },
    })
    expect(wrapper.find('.child-content').text()).toBe('子页面内容')
  })
})
