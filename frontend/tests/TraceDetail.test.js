/** TraceDetail 组件测试（C9.8-C9.12） */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGetTraceDetail, mockRouterPush, mockRouteParams, mockMessageSuccess, mockMessageError } = vi.hoisted(() => ({
  mockGetTraceDetail: vi.fn(),
  mockRouterPush: vi.fn(),
  mockRouteParams: { trace_id: 'abc12345-6789-abcd-ef01-234567890abc' },
  mockMessageSuccess: vi.fn(),
  mockMessageError: vi.fn(),
}))

vi.mock('@/api/trace', () => ({
  getTraceDetail: mockGetTraceDetail,
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({ push: mockRouterPush })),
  useRoute: vi.fn(() => ({ params: mockRouteParams })),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMessageSuccess, error: mockMessageError },
  }
})

// Mock highlight.js — 测试不需要真实语法高亮
vi.mock('highlight.js/lib/core', () => ({
  default: {
    registerLanguage: vi.fn(),
    highlight: vi.fn((code) => ({ value: `<span class="hljs-mock">${code}</span>` })),
  },
}))
vi.mock('highlight.js/lib/languages/json', () => ({ default: {} }))

import TraceDetail from '@/views/admin/TraceDetail.vue'

const MOCK_TRACE = {
  trace_id: 'abc12345-6789-abcd-ef01-234567890abc',
  user_id: 10,
  username: 'alice',
  conversation_id: 42,
  kb_id: 1,
  kb_name: 'HR知识库',
  question: '报销流程是什么样的？',
  status: 'success',
  intent_type: 'KNOWLEDGE',
  intent_method: 'llm',
  response_mode: 'RAG',
  total_duration_ms: 3200,
  intent: { label: 'KNOWLEDGE', method: 'llm', duration_ms: 1200, status: 'success' },
  rewrite: { original: '报销流程', rewritten: '报销流程是什么样的', duration_ms: 800, status: 'success' },
  retrieve: {
    vector: { duration_ms: 500, count: 10 },
    bm25: { duration_ms: 200, count: 8 },
    fusion: { method: 'rrf', duration_ms: 10, count: 5 },
    match_sentence: { duration_ms: 50 },
    duration_ms: 760,
    status: 'success',
  },
  rerank: { method: 'noop', duration_ms: 5, metadata: { reranker: 'NoopReranker' }, status: 'success' },
  generate: { model: 'deepseek-v4', ttft_ms: 320, duration_ms: 1800, status: 'success' },
  error_message: null,
  created_at: '2026-06-12T10:30:00+00:00',
}

const MOCK_TRACE_ERROR = {
  ...MOCK_TRACE,
  trace_id: 'err99999-0000-0000-0000-000000000000',
  status: 'error',
  error_message: 'LLM API 返回 500: Internal Server Error',
  generate: { duration_ms: 500, status: 'error' },
}

function mockSuccessResponse(trace = MOCK_TRACE) {
  mockGetTraceDetail.mockResolvedValue({
    data: { code: '0', data: trace },
  })
}

function getComponent() {
  return mount(TraceDetail, {
    global: {
      directives: { loading: vi.fn() },
    },
  })
}

describe('TraceDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
  })

  // C9.8 — TraceDetail 渲染
  describe('C9.8 TraceDetail 渲染', () => {
    it('挂载后调用 getTraceDetail 加载数据', async () => {
      mockSuccessResponse()
      getComponent()
      await flushPromises()
      expect(mockGetTraceDetail).toHaveBeenCalledWith('abc12345-6789-abcd-ef01-234567890abc')
    })

    it('渲染基本信息卡片', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.info-card').exists()).toBe(true)
    })

    it('显示用户名', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const infoItems = wrapper.findAll('.info-item')
      // 找到「用户」标签对应的值
      const userItem = infoItems.find(i => i.find('.info-label').text() === '用户')
      expect(userItem.find('.info-value').text()).toBe('alice')
    })

    it('显示会话 ID', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const infoItems = wrapper.findAll('.info-item')
      const convItem = infoItems.find(i => i.find('.info-label').text() === '会话')
      expect(convItem.find('.info-value').text()).toContain('42')
    })

    it('显示知识库名称', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const infoItems = wrapper.findAll('.info-item')
      const kbItem = infoItems.find(i => i.find('.info-label').text() === '知识库')
      expect(kbItem.find('.info-value').text()).toBe('HR知识库')
    })

    it('显示耗时（格式化为秒）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const infoItems = wrapper.findAll('.info-item')
      const durItem = infoItems.find(i => i.find('.info-label').text() === '耗时')
      expect(durItem.find('.info-value').text()).toBe('3.2s')
    })

    it('显示意图标签（知识问答）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.intent-tag').text()).toContain('知识问答')
    })

    it('显示响应模式标签（RAG）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.response-tag').text()).toContain('RAG')
    })

    it('显示问题文本', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.question-text').text()).toBe('报销流程是什么样的？')
    })

    it('加载失败时显示错误状态', async () => {
      mockGetTraceDetail.mockRejectedValue(new Error('Network Error'))
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-state').exists()).toBe(true)
      expect(wrapper.find('.empty-title').text()).toBe('加载失败')
      expect(wrapper.find('.empty-desc').text()).toBe('网络异常，请稍后重试')
    })
  })

  // C9.9 — TraceDetail 阶段卡片
  describe('C9.9 TraceDetail 阶段卡片', () => {
    it('渲染 5 个阶段卡片（Intent/Rewrite/Retrieve/Rerank/Generate）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const cards = wrapper.findAll('.stage-card')
      expect(cards).toHaveLength(5)
    })

    it('每个阶段卡片显示阶段名称', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const names = wrapper.findAll('.stage-name').map(el => el.text())
      expect(names).toEqual(['Intent', 'Rewrite', 'Retrieve', 'Rerank', 'Generate'])
    })

    it('每个阶段卡片显示耗时', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const durations = wrapper.findAll('.stage-duration').map(el => el.text())
      // Intent: 1200ms=1.2s, Rewrite: 800ms, Retrieve: 760ms, Rerank: 5ms, Generate: 1800ms=1.8s
      expect(durations[0]).toBe('1.2s')
      expect(durations[1]).toBe('800ms')
      expect(durations[2]).toBe('760ms')
      expect(durations[3]).toBe('5ms')
      expect(durations[4]).toBe('1.8s')
    })

    it('Generate 阶段显示模型名称', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const generateCard = wrapper.findAll('.stage-card')[4]
      const metaItems = generateCard.findAll('.stage-meta-item')
      const modelMeta = metaItems.find(el => el.text().includes('deepseek-v4'))
      expect(modelMeta).toBeTruthy()
    })

    it('Generate 阶段显示 TTFT', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const generateCard = wrapper.findAll('.stage-card')[4]
      const metaItems = generateCard.findAll('.stage-meta-item')
      const ttftMeta = metaItems.find(el => el.text().includes('TTFT'))
      expect(ttftMeta).toBeTruthy()
      expect(ttftMeta.text()).toContain('320ms')
    })

    it('阶段有错误时卡片添加 has-error 样式', async () => {
      mockSuccessResponse(MOCK_TRACE_ERROR)
      const wrapper = getComponent()
      await flushPromises()
      const generateCard = wrapper.findAll('.stage-card')[4]
      expect(generateCard.classes()).toContain('has-error')
    })
  })

  // C9.10 — TraceDetail JSON 展开
  describe('C9.10 TraceDetail JSON 展开', () => {
    it('初始状态所有 JSON 面板折叠', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.json-panel').exists()).toBe(false)
    })

    it('点击「查看JSON」按钮展开对应阶段面板', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      // 初始所有按钮显示"查看JSON"
      const buttons = wrapper.findAll('.stage-json-btn')
      expect(buttons[0].text()).toContain('查看JSON')

      // 点击 Intent 的查看JSON
      await buttons[0].trigger('click')
      // 展开后出现 JSON 面板
      const panels = wrapper.findAll('.json-panel')
      expect(panels.length).toBeGreaterThanOrEqual(1)
      // 按钮文本变为"收起JSON"
      expect(wrapper.findAll('.stage-json-btn')[0].text()).toContain('收起JSON')
    })

    it('JSON 面板包含高亮内容', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.findAll('.stage-json-btn')[0].trigger('click')
      const jsonContent = wrapper.find('.json-content')
      expect(jsonContent.exists()).toBe(true)
      // highlight.js mock 会添加 hljs-mock class
      expect(jsonContent.html()).toContain('hljs-mock')
    })
  })

  // C9.11 — TraceDetail JSON 折叠
  describe('C9.11 TraceDetail JSON 折叠', () => {
    it('再次点击按钮折叠 JSON 面板', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const btn = wrapper.findAll('.stage-json-btn')[0]
      // 展开
      await btn.trigger('click')
      expect(wrapper.findAll('.json-panel').length).toBeGreaterThanOrEqual(1)

      // 折叠
      await wrapper.findAll('.stage-json-btn')[0].trigger('click')
      expect(wrapper.find('.json-panel').exists()).toBe(false)
    })

    it('多个阶段可同时展开', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      // 展开 Intent 和 Rewrite
      const buttons = wrapper.findAll('.stage-json-btn')
      await buttons[0].trigger('click')
      await wrapper.findAll('.stage-json-btn')[1].trigger('click')

      expect(wrapper.findAll('.json-panel')).toHaveLength(2)
    })
  })

  // C9.12 — TraceDetail 返回导航
  describe('C9.12 TraceDetail 返回导航', () => {
    it('点击返回按钮跳转到 Trace 列表页', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const backBtn = wrapper.find('.back-btn')
      expect(backBtn.exists()).toBe(true)
      await backBtn.trigger('click')
      expect(mockRouterPush).toHaveBeenCalledWith('/admin/traces')
    })

    it('错误状态下也有返回按钮', async () => {
      mockGetTraceDetail.mockRejectedValue(new Error('Network Error'))
      const wrapper = getComponent()
      await flushPromises()

      const backBtn = wrapper.find('.back-btn')
      expect(backBtn.exists()).toBe(true)
      await backBtn.trigger('click')
      expect(mockRouterPush).toHaveBeenCalledWith('/admin/traces')
    })
  })

  // 补充：错误信息面板
  describe('错误信息面板', () => {
    it('有 error_message 时渲染错误面板', async () => {
      mockSuccessResponse(MOCK_TRACE_ERROR)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.error-panel').exists()).toBe(true)
      expect(wrapper.find('.error-content').text()).toBe('LLM API 返回 500: Internal Server Error')
    })

    it('无 error_message 时不渲染错误面板', async () => {
      mockSuccessResponse(MOCK_TRACE)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.error-panel').exists()).toBe(false)
    })
  })
})
