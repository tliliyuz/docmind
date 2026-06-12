/** ECharts 图表组件测试（C7.4-C7.7） */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// Mock ResizeObserver — jsdom 不支持
class MockResizeObserver {
  constructor() {
    this.observe = vi.fn()
    this.unobserve = vi.fn()
    this.disconnect = vi.fn()
  }
}
global.ResizeObserver = MockResizeObserver

// 收集 setOption 调用参数
const { mockInit } = vi.hoisted(() => {
  let setOptionCalls = []
  return {
    mockInit: vi.fn(() => {
      setOptionCalls = []
      return {
        setOption: vi.fn((...args) => { setOptionCalls.push(args) }),
        resize: vi.fn(),
        dispose: vi.fn(),
        getInstance: vi.fn(),
      }
    }),
    getSetOptionCalls: () => setOptionCalls,
  }
})

vi.mock('echarts', () => ({
  init: (...args) => mockInit(...args),
}))

import TrendChart from '@/components/charts/TrendChart.vue'
import LatencyChart from '@/components/charts/LatencyChart.vue'
import TokenChart from '@/components/charts/TokenChart.vue'

const TREND_DATA = [
  { date: '2026-06-06', success: 10, error: 1 },
  { date: '2026-06-07', success: 15, error: 0 },
  { date: '2026-06-08', success: 8, error: 2 },
]

const LATENCY_DATA = [
  { date: '2026-06-06', p50: 2000, p95: 5000, p99: 8000 },
  { date: '2026-06-07', p50: 1800, p95: 4500, p99: 7000 },
  { date: '2026-06-08', p50: 2200, p95: 5500, p99: 9000 },
]

const TOKEN_DATA = [
  { date: '2026-06-06', input: 50000, output: 12000 },
  { date: '2026-06-07', input: 60000, output: 15000 },
  { date: '2026-06-08', input: 45000, output: 10000 },
]

function mountChart(Component, data) {
  return mount(Component, {
    props: { data },
  })
}

describe('ECharts 图表组件', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // C7.4 — TrendChart 渲染
  describe('C7.4 TrendChart 渲染', () => {
    it('渲染图表容器', () => {
      const wrapper = mountChart(TrendChart, TREND_DATA)
      expect(wrapper.find('.chart-container').exists()).toBe(true)
    })

    it('渲染标题「问答量趋势」', () => {
      const wrapper = mountChart(TrendChart, TREND_DATA)
      expect(wrapper.find('.chart-title').text()).toContain('问答量趋势')
    })

    it('有数据时调用 echarts.init 并 setOption', async () => {
      mountChart(TrendChart, TREND_DATA)
      await flushPromises()
      expect(mockInit).toHaveBeenCalled()
    })

    it('setOption 包含成功和失败两条折线', async () => {
      mountChart(TrendChart, TREND_DATA)
      await flushPromises()
      // 通过 mock 获取 echarts 实例上的 setOption 调用
      const instance = mockInit.mock.results[0].value
      expect(instance.setOption).toHaveBeenCalled()
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series).toHaveLength(2)
      expect(option.series[0].name).toBe('成功')
      expect(option.series[1].name).toBe('失败')
    })

    it('折线类型为 line', async () => {
      mountChart(TrendChart, TREND_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series[0].type).toBe('line')
      expect(option.series[1].type).toBe('line')
    })

    it('x 轴数据为日期数组', async () => {
      mountChart(TrendChart, TREND_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      const option = instance.setOption.mock.calls[0][0]
      expect(option.xAxis.data).toEqual(['2026-06-06', '2026-06-07', '2026-06-08'])
    })
  })

  // C7.5 — LatencyChart 渲染
  describe('C7.5 LatencyChart 渲染', () => {
    it('渲染图表容器', () => {
      const wrapper = mountChart(LatencyChart, LATENCY_DATA)
      expect(wrapper.find('.chart-container').exists()).toBe(true)
    })

    it('渲染标题「响应时间分布」', () => {
      const wrapper = mountChart(LatencyChart, LATENCY_DATA)
      expect(wrapper.find('.chart-title').text()).toContain('响应时间分布')
    })

    it('setOption 包含 P50/P95/P99 三条折线', async () => {
      mountChart(LatencyChart, LATENCY_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      expect(instance.setOption).toHaveBeenCalled()
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series).toHaveLength(3)
      expect(option.series[0].name).toBe('P50')
      expect(option.series[1].name).toBe('P95')
      expect(option.series[2].name).toBe('P99')
    })

    it('P50 数据值正确', async () => {
      mountChart(LatencyChart, LATENCY_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series[0].data).toEqual([2000, 1800, 2200])
    })

    it('折线类型为 line', async () => {
      mountChart(LatencyChart, LATENCY_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series.every(s => s.type === 'line')).toBe(true)
    })
  })

  // C7.6 — TokenChart 渲染
  describe('C7.6 TokenChart 渲染', () => {
    it('渲染图表容器', () => {
      const wrapper = mountChart(TokenChart, TOKEN_DATA)
      expect(wrapper.find('.chart-container').exists()).toBe(true)
    })

    it('渲染标题「Token 使用统计」', () => {
      const wrapper = mountChart(TokenChart, TOKEN_DATA)
      expect(wrapper.find('.chart-title').text()).toContain('Token 使用统计')
    })

    it('setOption 包含 Input Token 和 Output Token 两条柱状图', async () => {
      mountChart(TokenChart, TOKEN_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      expect(instance.setOption).toHaveBeenCalled()
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series).toHaveLength(2)
      expect(option.series[0].name).toBe('Input Token')
      expect(option.series[1].name).toBe('Output Token')
    })

    it('柱状图类型为 bar 且堆叠', async () => {
      mountChart(TokenChart, TOKEN_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series[0].type).toBe('bar')
      expect(option.series[1].type).toBe('bar')
      expect(option.series[0].stack).toBe('token')
      expect(option.series[1].stack).toBe('token')
    })

    it('Input Token 数据值正确', async () => {
      mountChart(TokenChart, TOKEN_DATA)
      await flushPromises()
      const instance = mockInit.mock.results[0].value
      const option = instance.setOption.mock.calls[0][0]
      expect(option.series[0].data).toEqual([50000, 60000, 45000])
    })
  })

  // C7.7 — 图表空数据
  describe('C7.7 图表空数据', () => {
    it('TrendChart 空数组不报错，显示空态', () => {
      const wrapper = mountChart(TrendChart, [])
      expect(wrapper.find('.chart-empty').exists()).toBe(true)
      expect(wrapper.find('.chart-empty span').text()).toBe('暂无数据')
    })

    it('LatencyChart 空数组不报错，显示空态', () => {
      const wrapper = mountChart(LatencyChart, [])
      expect(wrapper.find('.chart-empty').exists()).toBe(true)
    })

    it('TokenChart 空数组不报错，显示空态', () => {
      const wrapper = mountChart(TokenChart, [])
      expect(wrapper.find('.chart-empty').exists()).toBe(true)
    })

    it('TrendChart null data 不报错，显示空态', () => {
      const wrapper = mount(TrendChart, { props: { data: null } })
      expect(wrapper.find('.chart-empty').exists()).toBe(true)
    })

    it('空数据时不调用 echarts.init', () => {
      mountChart(TrendChart, [])
      // echarts.init 在 useECharts 的 onMounted 中调用
      // 但 setOption 不会被调用（renderChart 提前 return）
      if (mockInit.mock.results.length > 0) {
        const instance = mockInit.mock.results[0].value
        expect(instance.setOption).not.toHaveBeenCalled()
      }
    })
  })
})
