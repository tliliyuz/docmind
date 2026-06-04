/** MessageList 组件测试 — ROADMAP §5.5 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Mock MessageItem 子组件
vi.mock('@/components/chat/MessageItem.vue', () => ({
  default: {
    name: 'MessageItem',
    props: { msg: Object },
    emits: ['regenerate'],
    template: '<div class="mock-message-item" :data-role="msg.role">{{ msg.content }}</div>',
  },
}))

import MessageList from '@/components/chat/MessageList.vue'

let mockScrollTo

function getComponent(props = {}) {
  return mount(MessageList, {
    props: { messages: [], ...props },
    global: {
      stubs: { 'i': { template: '<span class="icon" />', props: ['class'] } },
    },
  })
}

describe('MessageList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockScrollTo = vi.fn()
    HTMLElement.prototype.scrollTo = mockScrollTo
  })

  afterEach(() => {
    delete HTMLElement.prototype.scrollTo
  })

  // ==================== 渲染测试 ====================

  it('空消息列表时不渲染任何 MessageItem', () => {
    const wrapper = getComponent({ messages: [] })
    expect(wrapper.findAll('.mock-message-item')).toHaveLength(0)
  })

  it('根据消息数组渲染对应数量的 MessageItem', () => {
    const messages = [
      { id: '1', role: 'user', content: '你好', status: 'complete' },
      { id: '2', role: 'assistant', content: '你好！', status: 'complete' },
    ]
    const wrapper = getComponent({ messages })
    const items = wrapper.findAll('.mock-message-item')
    expect(items).toHaveLength(2)
    expect(items[0].attributes('data-role')).toBe('user')
    expect(items[1].attributes('data-role')).toBe('assistant')
  })

  it('渲染消息内容', () => {
    const messages = [
      { id: '1', role: 'user', content: '报销流程', status: 'complete' },
    ]
    const wrapper = getComponent({ messages })
    expect(wrapper.text()).toContain('报销流程')
  })

  // ==================== 自动滚动测试 ====================

  it('组件挂载时自动滚动到底部', () => {
    getComponent({ messages: [{ id: '1', role: 'user', content: 'hi', status: 'complete' }] })
    // onMounted 调用 scrollToBottom → el.scrollTo(...)
    expect(mockScrollTo).toHaveBeenCalled()
  })

  it('消息数量变化时，在底部附近自动滚动', async () => {
    const messages = [{ id: '1', role: 'user', content: 'hi', status: 'complete' }]
    const wrapper = getComponent({ messages })

    // 初始化时会调用一次 scrollTo
    mockScrollTo.mockClear()

    // jsdom 默认 scrollHeight/clientHeight 为 0 → isNearBottom 返回 true
    // 所以新增消息时应自动触发滚动
    await wrapper.setProps({
      messages: [...messages, { id: '2', role: 'assistant', content: '回复', status: 'complete' }],
    })
    // watcher 内部使用 nextTick，需等待异步任务执行
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))

    expect(mockScrollTo).toHaveBeenCalled()
  })

  it('流式内容变化时在底部则持续滚动', async () => {
    const messages = [{ id: '1', role: 'assistant', content: '逐', status: 'streaming' }]
    const wrapper = getComponent({ messages })

    mockScrollTo.mockClear()

    await wrapper.setProps({
      messages: [{ id: '1', role: 'assistant', content: '逐步输出中', status: 'streaming' }],
    })
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))

    // jsdom 默认值为 0 → isNearBottom 返回 true → 自动滚动
    expect(mockScrollTo).toHaveBeenCalled()
  })

  it('expose scrollToBottom 方法可被父组件调用', () => {
    const wrapper = getComponent({ messages: [{ id: '1', role: 'user', content: 'hi', status: 'complete' }] })
    expect(wrapper.vm.scrollToBottom).toBeDefined()
    expect(typeof wrapper.vm.scrollToBottom).toBe('function')

    // 调用 scrollToBottom → 内部调用 scrollTo
    mockScrollTo.mockClear()
    wrapper.vm.scrollToBottom()
    expect(mockScrollTo).toHaveBeenCalled()
  })

  // ==================== 新消息按钮测试 ====================

  it('「新消息」按钮在初始时不显示（在底部）', () => {
    const messages = [{ id: '1', role: 'user', content: 'hi', status: 'complete' }]
    const wrapper = getComponent({ messages })
    // onMounted 后 scrollToBottom 定位到底部，按钮应隐藏
    expect(wrapper.find('.scroll-bottom-btn').exists()).toBe(false)
  })

  it('渲染 Transition 包裹的「新消息」按钮结构', () => {
    const messages = [{ id: '1', role: 'user', content: 'hi', status: 'complete' }]
    const wrapper = getComponent({ messages })
    // Transition 存在（即使内部按钮不显示）
    expect(wrapper.findComponent({ name: 'Transition' }).exists()).toBe(true)
  })

  it('消息列表容器有正确的 class', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.message-list').exists()).toBe(true)
  })
})
