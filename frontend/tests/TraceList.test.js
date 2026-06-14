/** TraceList 组件测试（C9.1-C9.7） */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGetTraceList, mockRouterPush, mockMessageSuccess, mockMessageError } = vi.hoisted(() => ({
  mockGetTraceList: vi.fn(),
  mockRouterPush: vi.fn(),
  mockMessageSuccess: vi.fn(),
  mockMessageError: vi.fn(),
}))

vi.mock('@/api/trace', () => ({
  getTraceList: mockGetTraceList,
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({ push: mockRouterPush })),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMessageSuccess, error: mockMessageError },
  }
})

import TraceList from '@/views/admin/TraceList.vue'

const MOCK_TRACES = [
  {
    trace_id: 'abc12345-6789-abcd-ef01-234567890abc',
    user_id: 10, username: 'alice',
    kb_id: 'kb111111-1111-1111-1111-111111111111', kb_name: 'HR知识库',
    question: '报销流程是什么样的？需要提交哪些材料？',
    status: 'success', intent_type: 'KNOWLEDGE', response_mode: 'RAG',
    total_duration_ms: 3200, created_at: '2026-06-12T10:30:00+00:00',
  },
  {
    trace_id: 'def98765-4321-fedc-ba09-876543210fed',
    user_id: 20, username: 'bob',
    kb_id: 'kb222222-2222-2222-2222-222222222222', kb_name: 'IT知识库',
    question: '你好',
    status: 'success', intent_type: 'CASUAL', response_mode: 'CASUAL',
    total_duration_ms: 150, created_at: '2026-06-12T11:00:00+00:00',
  },
  {
    trace_id: 'ghi55555-1111-2222-3333-444444444444',
    user_id: 10, username: 'alice',
    kb_id: 'kb111111-1111-1111-1111-111111111111', kb_name: 'HR知识库',
    question: 'VPN配置方法',
    status: 'error', intent_type: 'KNOWLEDGE', response_mode: 'RAG',
    total_duration_ms: 8500, created_at: '2026-06-12T09:15:00+00:00',
  },
]

function mockSuccessResponse(items = MOCK_TRACES, total = 3) {
  mockGetTraceList.mockResolvedValue({
    data: { code: '0', data: { items, total } },
  })
}

function getComponent() {
  return mount(TraceList, {
    global: {
      stubs: {
        'el-input': {
          template: '<input class="el-input-stub" />',
          props: ['modelValue', 'placeholder', 'size', 'clearable', 'style'],
          emits: ['input', 'clear', 'update:modelValue'],
        },
        'el-select': {
          template: '<select class="el-select-stub"><slot /></select>',
          props: ['modelValue', 'placeholder', 'clearable', 'size', 'style'],
          emits: ['change', 'update:modelValue'],
        },
        'el-option': {
          template: '<option class="el-option-stub"><slot /></option>',
          props: ['label', 'value'],
        },
        'el-date-picker': {
          template: '<div class="el-date-picker-stub" />',
          props: ['modelValue', 'type', 'rangeSeparator', 'startPlaceholder', 'endPlaceholder', 'size', 'style', 'clearable'],
          emits: ['change', 'update:modelValue'],
        },
        'el-table': {
          template: '<div class="el-table-stub"><slot /></div>',
          props: ['data', 'vLoading', 'style', 'rowKey', 'highlightCurrentRow'],
          emits: ['row-click'],
        },
        'el-table-column': {
          template: '<div class="el-table-col-stub" />',
          props: ['prop', 'label', 'width', 'minWidth', 'align', 'fixed'],
        },
        'el-pagination': {
          template: '<div class="el-pagination-stub" />',
          props: ['currentPage', 'pageSize', 'total', 'layout'],
          emits: ['update:currentPage', 'currentChange'],
        },
      },
      directives: { loading: vi.fn() },
    },
  })
}

describe('TraceList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    // Mock clipboard
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // C9.1 — TraceList 渲染
  describe('C9.1 TraceList 渲染', () => {
    it('挂载后调用 getTraceList 加载数据', async () => {
      mockSuccessResponse()
      getComponent()
      await flushPromises()
      expect(mockGetTraceList).toHaveBeenCalledTimes(1)
      expect(mockGetTraceList).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    })

    it('渲染 el-table 表格组件', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.el-table-stub').exists()).toBe(true)
    })

    it('渲染 9 列表格列（Trace ID/用户/知识库/问题/耗时/意图/响应/状态/时间）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const cols = wrapper.findAll('.el-table-col-stub')
      expect(cols).toHaveLength(9)
    })

    it('渲染 4 个概览统计卡片（成功失败运行中/成功率/平均耗时/P95 耗时）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const cards = wrapper.findAll('.stat-card')
      expect(cards).toHaveLength(4)
    })

    it('概览卡片显示正确统计值（2 成功 / 1 失败 / 0 运行中）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      // 第一个卡片：成功 / 失败 / 运行中
      expect(values[0].text()).toContain('2')
      expect(values[0].text()).toContain('1')
      expect(values[0].text()).toContain('0')
    })

    it('概览卡片显示成功率百分比', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[1].text()).toBe('66.7%')
    })

    it('渲染筛选栏（搜索框 + 3 个下拉 + 日期选择器）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.el-input-stub').exists()).toBe(true)
      expect(wrapper.findAll('.el-select-stub')).toHaveLength(3)
      expect(wrapper.find('.el-date-picker-stub').exists()).toBe(true)
    })

    it('有数据时显示总记录数提示', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.total-hint').text()).toBe('共 3 条记录')
    })
  })

  // C9.2 — TraceList 空状态
  describe('C9.2 TraceList 空状态', () => {
    it('无 Trace 数据时显示空状态', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-state').exists()).toBe(true)
      expect(wrapper.find('.empty-title').text()).toBe('暂无 Trace 记录')
    })

    it('空状态时不渲染表格', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.el-table-stub').exists()).toBe(false)
    })

    it('空状态描述文案正确', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-desc').text()).toBe('系统中还没有任何链路追踪数据')
    })
  })

  // C9.3 — TraceList 搜索
  describe('C9.3 TraceList 搜索', () => {
    it('输入搜索文本后 300ms 防抖触发重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetTraceList.mockClear()

      wrapper.vm.searchText = '报销'
      wrapper.vm.onSearchInput()
      await flushPromises()

      // 300ms 前不应触发
      expect(mockGetTraceList).not.toHaveBeenCalled()

      vi.advanceTimersByTime(300)
      await flushPromises()
      expect(mockGetTraceList).toHaveBeenCalledTimes(1)
      expect(mockGetTraceList).toHaveBeenCalledWith(
        expect.objectContaining({ search: '报销' })
      )
    })

    it('搜索清除后立即刷新列表', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetTraceList.mockClear()

      wrapper.vm.searchText = ''
      wrapper.vm.onSearchClear()
      await flushPromises()
      expect(mockGetTraceList).toHaveBeenCalledTimes(1)
      // 不带 search 参数
      expect(mockGetTraceList).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    })
  })

  // C9.4 — TraceList 筛选
  describe('C9.4 TraceList 筛选', () => {
    it('切换状态筛选后重新加载（status 参数传递）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetTraceList.mockClear()

      wrapper.vm.filterStatus = 'error'
      wrapper.vm.reloadList()
      await flushPromises()
      expect(mockGetTraceList).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'error' })
      )
    })

    it('切换意图筛选后重新加载（intent_type 参数传递）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetTraceList.mockClear()

      wrapper.vm.filterIntent = 'KNOWLEDGE'
      wrapper.vm.reloadList()
      await flushPromises()
      expect(mockGetTraceList).toHaveBeenCalledWith(
        expect.objectContaining({ intent_type: 'KNOWLEDGE' })
      )
    })

    it('切换响应模式筛选后重新加载（response_mode 参数传递）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetTraceList.mockClear()

      wrapper.vm.filterResponse = 'RAG'
      wrapper.vm.reloadList()
      await flushPromises()
      expect(mockGetTraceList).toHaveBeenCalledWith(
        expect.objectContaining({ response_mode: 'RAG' })
      )
    })

    it('筛选后页码重置为 1', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      wrapper.vm.currentPage = 3

      wrapper.vm.filterStatus = 'success'
      wrapper.vm.reloadList()
      await flushPromises()
      expect(wrapper.vm.currentPage).toBe(1)
    })
  })

  // C9.5 — TraceList 分页
  describe('C9.5 TraceList 分页', () => {
    it('翻页后重新加载对应页', async () => {
      mockSuccessResponse(MOCK_TRACES, 50) // total > pageSize 才显示分页
      const wrapper = getComponent()
      await flushPromises()
      mockGetTraceList.mockClear()

      wrapper.vm.onPageChange(3)
      await flushPromises()
      expect(mockGetTraceList).toHaveBeenCalledWith(
        expect.objectContaining({ page: 3 })
      )
    })

    it('total 超过 pageSize 时显示分页组件', async () => {
      mockSuccessResponse(MOCK_TRACES, 50)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.el-pagination-stub').exists()).toBe(true)
    })

    it('total 不超过 pageSize 时不显示分页', async () => {
      mockSuccessResponse(MOCK_TRACES, 3)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.el-pagination-stub').exists()).toBe(false)
    })
  })

  // C9.6 — TraceList 点击行跳转
  describe('C9.6 TraceList 点击行跳转', () => {
    it('点击行跳转到 Trace 详情页', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      wrapper.vm.goToDetail(MOCK_TRACES[0])
      expect(mockRouterPush).toHaveBeenCalledWith('/admin/traces/abc12345-6789-abcd-ef01-234567890abc')
    })
  })

  // C9.7 — TraceList Trace ID 复制
  describe('C9.7 TraceList Trace ID 复制', () => {
    it('点击 Trace ID 复制到剪贴板', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.copyTraceId('abc12345-6789-abcd-ef01-234567890abc')
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('abc12345-6789-abcd-ef01-234567890abc')
      expect(mockMessageSuccess).toHaveBeenCalledWith('Trace ID 已复制')
    })

    it('复制失败时显示错误提示', async () => {
      mockSuccessResponse()
      navigator.clipboard.writeText.mockRejectedValue(new Error('denied'))
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.copyTraceId('some-trace-id')
      expect(mockMessageError).toHaveBeenCalledWith('复制失败')
    })
  })
})
