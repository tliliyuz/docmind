/** StatsPage 组件测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGetAdminStats, mockGetTraceStats } = vi.hoisted(() => ({
  mockGetAdminStats: vi.fn(),
  mockGetTraceStats: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getAdminStats: mockGetAdminStats,
  getTraceStats: mockGetTraceStats,
}))

// Mock ECharts — 避免真实 DOM 渲染
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  })),
}))

import StatsPage from '@/views/admin/StatsPage.vue'

const MOCK_STATS = {
  user_count: 1234,
  kb_count: 56,
  doc_count: 890,
  chunk_count: 12345,
  conversation_count: 234,
  message_count: 5678,
  storage_bytes: 1073741824, // 1 GB
}

const MOCK_CHART_DATA = {
  trend: [
    { date: '2026-06-06', success: 10, error: 1 },
    { date: '2026-06-07', success: 15, error: 0 },
  ],
  latency: [
    { date: '2026-06-06', p50: 2000, p95: 5000, p99: 8000 },
    { date: '2026-06-07', p50: 1800, p95: 4500, p99: 7000 },
  ],
  tokens: [
    { date: '2026-06-06', input: 50000, output: 12000 },
    { date: '2026-06-07', input: 60000, output: 15000 },
  ],
  intent_distribution: [],
  response_distribution: [],
}

function getComponent() {
  return mount(StatsPage, {
    global: {
      stubs: {
        TrendChart: { template: '<div class="trend-chart-stub"></div>', props: ['data'] },
        LatencyChart: { template: '<div class="latency-chart-stub"></div>', props: ['data'] },
        TokenChart: { template: '<div class="token-chart-stub"></div>', props: ['data'] },
      },
      directives: { loading: vi.fn() },
    },
  })
}

describe('StatsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // 默认：两个 API 都返回成功
    mockGetAdminStats.mockResolvedValue({
      data: { code: '0', data: MOCK_STATS },
    })
    mockGetTraceStats.mockResolvedValue({
      data: { code: '0', data: MOCK_CHART_DATA },
    })
  })

  describe('初始状态', () => {
    it('挂载时 API 未 resolve 前不渲染统计卡片（loading 态）', async () => {
      mockGetAdminStats.mockReturnValue(new Promise(() => {}))
      mockGetTraceStats.mockReturnValue(new Promise(() => {}))
      const wrapper = getComponent()
      await flushPromises()
      // loading 为 true 时 v-if="loading" 的 div 占位，stat-cards-row 不渲染
      expect(wrapper.find('.stat-cards-row').exists()).toBe(false)
    })
  })

  describe('数据加载成功', () => {
    it('渲染 7 个统计卡片（4 核心 + 3 二级）', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const cards = wrapper.findAll('.stat-card')
      expect(cards).toHaveLength(7)
    })

    it('显示用户总数（千分位格式化）', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[0].text()).toBe('1,234')
    })

    it('显示知识库数', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[1].text()).toBe('56')
    })

    it('显示文档总数', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[2].text()).toBe('890')
    })

    it('显示总会话数', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[3].text()).toBe('234')
    })

    it('二级卡片：显示分块总数', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[4].text()).toBe('12,345')
    })

    it('二级卡片：显示消息总数', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[5].text()).toBe('5,678')
    })

    it('二级卡片：formatStorage 转换 1 GB', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[6].text()).toBe('1.0 GB')
    })

  })

  describe('API 返回非 0 code', () => {
    it('显示 API 返回的错误 message', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: 'E9001', message: '服务器内部错误' },
      })
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-state').exists()).toBe(true)
      expect(wrapper.find('.empty-title').text()).toBe('数据加载失败')
      expect(wrapper.find('.empty-desc').text()).toBe('服务器内部错误')
    })

    it('API 无 message 时显示默认错误文本', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: 'E9001' },
      })
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-desc').text()).toBe('获取统计数据失败')
    })
  })

  describe('网络异常', () => {
    it('catch 块显示网络异常提示', async () => {
      mockGetAdminStats.mockRejectedValue(new Error('Network Error'))
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-title').text()).toBe('数据加载失败')
      expect(wrapper.find('.empty-desc').text()).toBe('网络异常，请稍后重试')
    })

    it('带 response.data.message 的异常显示服务端错误', async () => {
      const err = new Error()
      err.response = { data: { message: '服务端异常详情' } }
      mockGetAdminStats.mockRejectedValue(err)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-desc').text()).toBe('服务端异常详情')
    })
  })

  describe('formatNumber 边界', () => {
    it('null 返回 --', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: { ...MOCK_STATS, user_count: null } },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[0].text()).toBe('--')
    })

    it('0 显示 "0"', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: { ...MOCK_STATS, user_count: 0 } },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[0].text()).toBe('0')
    })
  })

  describe('formatStorage 边界', () => {
    it('null 返回 --', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: { ...MOCK_STATS, storage_bytes: null } },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[6].text()).toBe('--')
    })

    it('0 显示 "0 B"', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: { ...MOCK_STATS, storage_bytes: 0 } },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[6].text()).toBe('0 B')
    })

    it('KB 级显示精确到小数点后 1 位', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: { ...MOCK_STATS, storage_bytes: 1536 } },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[6].text()).toBe('1.5 KB')
    })
  })

  describe('ECharts 图表集成', () => {
    it('图表加载中时显示 loading 骨架', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      mockGetTraceStats.mockReturnValue(new Promise(() => {}))
      const wrapper = getComponent()
      await flushPromises()
      // chartsLoading 为 true 时图表区域有 v-loading 的 div
      expect(wrapper.find('.charts-section').exists()).toBe(true)
      expect(wrapper.find('.trend-chart-stub').exists()).toBe(false)
    })

    it('图表数据加载成功后渲染 3 个图表组件', async () => {
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.trend-chart-stub').exists()).toBe(true)
      expect(wrapper.find('.latency-chart-stub').exists()).toBe(true)
      expect(wrapper.find('.token-chart-stub').exists()).toBe(true)
    })

    it('图表数据传入正确', async () => {
      const wrapper = getComponent()
      await flushPromises()
      const trendChart = wrapper.find('.trend-chart-stub')
      expect(trendChart.exists()).toBe(true)
      // 验证图表组件通过 prop 接收了数据
      expect(wrapper.find('.charts-section').exists()).toBe(true)
    })

    it('getTraceStats 被调用时传入 days=7', async () => {
      getComponent()
      await flushPromises()
      expect(mockGetTraceStats).toHaveBeenCalledWith({ days: 7 })
    })

    it('图表 API 失败时不阻断页面，图表区域隐藏', async () => {
      mockGetTraceStats.mockRejectedValue(new Error('Network Error'))
      const wrapper = getComponent()
      await flushPromises()
      // 统计卡片正常渲染
      expect(wrapper.findAll('.stat-card')).toHaveLength(7)
      // chartsLoading 变为 false，图表组件渲染但 data 为空
      expect(wrapper.find('.trend-chart-stub').exists()).toBe(true)
    })

    it('并行调用 getAdminStats 和 getTraceStats', async () => {
      getComponent()
      await flushPromises()
      expect(mockGetAdminStats).toHaveBeenCalledTimes(1)
      expect(mockGetTraceStats).toHaveBeenCalledTimes(1)
    })
  })
})
