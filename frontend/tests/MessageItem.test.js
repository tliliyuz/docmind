/** MessageItem 组件测试 — ROADMAP §5.5 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// Mock markdown 工具
const mockRenderMarkdown = vi.fn((text) => {
  if (!text) return ''
  return `<p>${text}</p>`
})
const mockWrapCodeBlocks = vi.fn((html) => html)

vi.mock('@/utils/markdown', () => ({
  renderMarkdown: (text) => mockRenderMarkdown(text),
  wrapCodeBlocks: (html) => mockWrapCodeBlocks(html),
}))

// Mock chatStore（MessageItem 引用 isKbOrphaned 控制重新生成按钮）
const { mockStore } = vi.hoisted(() => {
  const mockStore = { isKbOrphaned: false }
  return { mockStore }
})
vi.mock('@/stores/chat', () => ({
  useChatStore: () => mockStore,
}))

import MessageItem from '@/components/chat/MessageItem.vue'

function getComponent(msg = {}) {
  return mount(MessageItem, {
    props: {
      msg: {
        id: '1',
        role: 'assistant',
        content: '',
        thinking: null,
        sources: null,
        status: 'complete',
        error: null,
        ...msg,
      },
    },
    global: {
      stubs: { 'i': { template: '<span class="icon" />', props: ['class'] } },
    },
  })
}

describe('MessageItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRenderMarkdown.mockImplementation((text) => {
      if (!text) return ''
      return `<p>${text}</p>`
    })
    mockWrapCodeBlocks.mockImplementation((html) => html)
  })

  // ==================== 角色与布局 ====================

  it('用户消息添加 .user class', () => {
    const wrapper = getComponent({ role: 'user', content: '你好' })
    expect(wrapper.find('.message-item').classes()).toContain('user')
  })

  it('assistant 消息添加 .assistant class', () => {
    const wrapper = getComponent({ role: 'assistant', content: '回复' })
    expect(wrapper.find('.message-item').classes()).toContain('assistant')
  })

  it('用户消息显示「你」，assistant 显示「DocMind」', () => {
    const userWrapper = getComponent({ role: 'user', content: 'x' })
    expect(userWrapper.find('.message-name').text()).toBe('你')

    const aiWrapper = getComponent({ role: 'assistant', content: 'x' })
    expect(aiWrapper.find('.message-name').text()).toBe('DocMind')
  })

  // ==================== Markdown 渲染 ====================

  it('使用 renderMarkdown + wrapCodeBlocks 渲染内容', () => {
    getComponent({ role: 'assistant', content: '**粗体**' })
    expect(mockRenderMarkdown).toHaveBeenCalledWith('**粗体**')
    expect(mockWrapCodeBlocks).toHaveBeenCalled()
  })

  it('空内容时不调用 renderMarkdown', () => {
    mockRenderMarkdown.mockClear()
    getComponent({ role: 'assistant', content: '' })
    // content 为空，renderedContent 返回 ''
    expect(mockRenderMarkdown).not.toHaveBeenCalled()
  })

  // ==================== 思考过程 ====================

  it('assistant 含 thinking 内容时显示思考面板', () => {
    const wrapper = getComponent({
      role: 'assistant',
      thinking: '让我分析一下…',
      content: '回答',
    })
    expect(wrapper.find('.thinking-box').exists()).toBe(true)
    expect(wrapper.find('.thinking-content').text()).toContain('让我分析一下…')
  })

  it('无 thinking 内容时不显示思考面板', () => {
    const wrapper = getComponent({ role: 'assistant', thinking: null, content: '回答' })
    expect(wrapper.find('.thinking-box').exists()).toBe(false)
  })

  it('用户消息不显示思考面板', () => {
    const wrapper = getComponent({ role: 'user', thinking: '不应该显示', content: '' })
    expect(wrapper.find('.thinking-box').exists()).toBe(false)
  })

  it('思考面板默认展开，点击标题收起/展开', async () => {
    const wrapper = getComponent({
      role: 'assistant',
      thinking: '思考内容',
      content: '回答',
    })
    // 默认展开：v-show 为 true，不应有 display:none
    const thinkingContent = wrapper.find('.thinking-content').element
    expect(thinkingContent.style.display).not.toBe('none')

    // 点击标题收起
    await wrapper.find('.thinking-title').trigger('click')
    await nextTick()
    expect(thinkingContent.style.display).toBe('none')

    // 再次点击展开
    await wrapper.find('.thinking-title').trigger('click')
    await nextTick()
    expect(thinkingContent.style.display).not.toBe('none')
  })

  // ==================== 引用来源 ====================

  it('assistant 含 sources 时显示引用面板', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      sources: [
        { doc_id: 1, doc_name: '手册A.pdf', content: '相关内容', page: 3 },
        { doc_id: 2, doc_name: '手册B.pdf', content: '另一内容', page: 5 },
      ],
    })
    expect(wrapper.find('.sources-box').exists()).toBe(true)
    expect(wrapper.find('.sources-title').text()).toContain('引用 2 个文档')
    expect(wrapper.find('.sources-title').text()).toContain('共 2 个片段')
  })

  it('同一文档多个片段去重计数', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      sources: [
        { doc_id: 1, doc_name: '手册A.pdf', content: '片段1', page: 1 },
        { doc_id: 1, doc_name: '手册A.pdf', content: '片段2', page: 2 },
        { doc_id: 2, doc_name: '手册B.pdf', content: '片段3', page: 1 },
      ],
    })
    // 3 个片段，但只有 2 个不同文档
    expect(wrapper.find('.sources-title').text()).toContain('引用 2 个文档')
    expect(wrapper.find('.sources-title').text()).toContain('共 3 个片段')
  })

  it('sources 面板默认展开，点击标题收起', async () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      sources: [{ doc_id: 1, doc_name: '手册.pdf', content: '内容' }],
    })
    const sourcesList = wrapper.find('.sources-list').element
    // 默认展开
    expect(sourcesList.style.display).not.toBe('none')

    await wrapper.find('.sources-title').trigger('click')
    await nextTick()
    expect(sourcesList.style.display).toBe('none')
  })

  it('source 内容为空时显示占位文字', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      sources: [{ doc_id: 1, doc_name: '空手册.pdf', content: '' }],
    })
    expect(wrapper.find('.source-content.placeholder').exists()).toBe(true)
    expect(wrapper.find('.source-content.placeholder').text()).toContain('无法获取片段内容')
  })

  it('source 显示文档名和页码', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      sources: [{ doc_id: 1, doc_name: '员工手册.pdf', content: '内容', page: 12 }],
    })
    expect(wrapper.find('.source-doc').text()).toContain('员工手册.pdf')
    expect(wrapper.find('.source-page').text()).toBe('第12页')
  })

  it('source 无 page 时不显示页码', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      sources: [{ doc_id: 1, doc_name: '手册.pdf', content: '内容' }],
    })
    expect(wrapper.find('.source-page').exists()).toBe(false)
  })

  it('source 无 doc_name 时显示「未知文档」', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      sources: [{ doc_id: 1, content: '内容' }],
    })
    expect(wrapper.find('.source-doc').text()).toContain('未知文档')
  })

  // ==================== 状态展示 ====================

  it('streaming 且无内容时显示 typing 动画', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '',
      status: 'streaming',
    })
    expect(wrapper.find('.typing-indicator').exists()).toBe(true)
  })

  it('streaming 且有内容时显示 Markdown 而非 typing 动画', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '部分内容',
      status: 'streaming',
    })
    expect(wrapper.find('.typing-indicator').exists()).toBe(false)
    expect(wrapper.find('.markdown-body').exists()).toBe(true)
  })

  it('error 状态时显示错误信息', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '',
      status: 'error',
      error: '检索服务异常',
    })
    expect(wrapper.find('.error-content').exists()).toBe(true)
    expect(wrapper.find('.error-content').text()).toContain('检索服务异常')
  })

  // ==================== 操作按钮 ====================

  it('assistant 完成状态时显示「重新生成」按钮', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      status: 'complete',
    })
    expect(wrapper.find('.action-btn').exists()).toBe(true)
    expect(wrapper.find('.action-btn').text()).toContain('重新生成')
  })

  it('点击重新生成 emit regenerate 事件', async () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '回答',
      status: 'complete',
    })
    await wrapper.find('.action-btn').trigger('click')
    expect(wrapper.emitted('regenerate')).toBeTruthy()
  })

  it('用户消息不显示重新生成按钮', () => {
    const wrapper = getComponent({
      role: 'user',
      content: '问题',
      status: 'complete',
    })
    expect(wrapper.find('.action-btn').exists()).toBe(false)
  })

  it('streaming 状态不显示重新生成按钮', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '部分',
      status: 'streaming',
    })
    expect(wrapper.find('.action-btn').exists()).toBe(false)
  })

  it('streaming 状态添加 .streaming class', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '',
      status: 'streaming',
    })
    expect(wrapper.find('.message-item').classes()).toContain('streaming')
  })

  // ==================== 来源面板抑制（"未找到相关信息"） ====================

  it('回答含"未找到相关信息"时隐藏来源面板', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '知识库中未找到相关信息。当前文档库覆盖了企业知识库系统的技术架构。',
      sources: [
        { doc_id: 1, doc_name: '手册.pdf', content: '不相关内容', page: 1 },
      ],
      status: 'complete',
    })
    expect(wrapper.find('.sources-box').exists()).toBe(false)
  })

  it('回答不含"未找到"时正常显示来源面板', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '广告投放的主要平台是抖音。',
      sources: [
        { doc_id: 1, doc_name: '手册.pdf', content: '相关内容', page: 1 },
      ],
      status: 'complete',
    })
    expect(wrapper.find('.sources-box').exists()).toBe(true)
    expect(wrapper.find('.sources-title').text()).toContain('引用 1 个文档')
  })

  // ==================== U11.6 getSourcePreviewHtml <mark> 高亮 ====================

  it('highlight_start/end 存在时渲染 <mark> 高亮', () => {
    const previewText = '根据公司政策，广告投放的主要平台是抖音。建议优先选择该渠道进行推广。'
    const wrapper = getComponent({
      role: 'assistant',
      content: '根据文档记载，广告投放的主要平台是抖音。',
      sources: [
        {
          doc_id: 1,
          doc_name: '手册.pdf',
          chunk_index: 1,
          preview_text: previewText,
          highlight_start: 7,  // "广告投放的主要平台是抖音" 在 preview_text 中的起始
          highlight_end: 20,
          content: '完整内容……',
          page: 5,
        },
      ],
      status: 'complete',
    })
    expect(wrapper.find('.sources-box').exists()).toBe(true)
    const sourceContent = wrapper.find('.source-content')
    expect(sourceContent.exists()).toBe(true)
    // 渲染的 HTML 含 <mark> 标签
    expect(sourceContent.html()).toContain('<mark')
    // 高亮内容精确匹配
    const highlighted = previewText.slice(7, 20)
    expect(sourceContent.html()).toContain(highlighted)
  })

  it('无 highlight_start/end 时纯文本展示（无 <mark>）', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '根据文档记载的内容。',
      sources: [
        {
          doc_id: 1,
          doc_name: '手册.pdf',
          chunk_index: 1,
          preview_text: '广告投放的主要平台是抖音，这是公司政策的明确规定。',
          // 无 highlight_start / highlight_end
          content: '完整内容……',
          page: 5,
        },
      ],
      status: 'complete',
    })
    expect(wrapper.find('.sources-box').exists()).toBe(true)
    const sourceContent = wrapper.find('.source-content')
    expect(sourceContent.exists()).toBe(true)
    expect(sourceContent.html()).not.toContain('<mark')
    expect(sourceContent.text()).toContain('广告投放的主要平台是抖音')
  })

  it('无 preview_text 时降级使用 content 前 200 字符', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '根据文档记载的内容。',
      sources: [
        {
          doc_id: 1,
          doc_name: '手册.pdf',
          chunk_index: 1,
          // 无 preview_text
          content: '这是一段很长的内容文本作为来源展示。'.repeat(20),
          page: 3,
        },
      ],
      status: 'complete',
    })
    expect(wrapper.find('.sources-box').exists()).toBe(true)
    const sourceContent = wrapper.find('.source-content')
    expect(sourceContent.exists()).toBe(true)
    const text = sourceContent.text()
    expect(text.length).toBeLessThanOrEqual(220)
  })

  it('preview_text HTML 特殊字符被转义', () => {
    const wrapper = getComponent({
      role: 'assistant',
      content: '根据文档记载的内容。',
      sources: [
        {
          doc_id: 1,
          doc_name: '手册.pdf',
          chunk_index: 1,
          preview_text: '文本含 <script>alert("xss")</script> 特殊字符需要转义处理。',
          content: '完整内容……',
          page: 1,
        },
      ],
      status: 'complete',
    })
    expect(wrapper.find('.sources-box').exists()).toBe(true)
    const html = wrapper.find('.source-content').html()
    expect(html).toContain('&lt;script&gt;')
    expect(html).not.toContain('<script>')
  })
})
