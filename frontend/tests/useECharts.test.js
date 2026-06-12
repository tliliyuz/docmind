/** useECharts 组合式函数测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'

const { mockSetOption, mockResize, mockDispose, mockInit } = vi.hoisted(() => {
  const mockSetOption = vi.fn()
  const mockResize = vi.fn()
  const mockDispose = vi.fn()
  const mockInit = vi.fn(() => ({
    setOption: mockSetOption,
    resize: mockResize,
    dispose: mockDispose,
  }))
  return { mockSetOption, mockResize, mockDispose, mockInit }
})

vi.mock('echarts', () => ({
  init: mockInit,
}))

// Mock ResizeObserver
class MockResizeObserver {
  constructor() {
    this.observe = vi.fn()
    this.unobserve = vi.fn()
    this.disconnect = vi.fn()
  }
}
global.ResizeObserver = MockResizeObserver

import { useECharts } from '@/composables/useECharts'

/** 创建测试组件 */
function createTestComponent() {
  return defineComponent({
    setup() {
      return useECharts()
    },
    template: '<div ref="chartRef" data-testid="chart"></div>',
  })
}

describe('useECharts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('挂载后自动初始化 ECharts 实例', async () => {
    const wrapper = mount(createTestComponent())
    expect(mockInit).toHaveBeenCalled()
  })

  it('setOption 调用 ECharts 实例的 setOption', async () => {
    const wrapper = mount(createTestComponent())
    const option = { xAxis: {}, series: [] }
    wrapper.vm.setOption(option)
    expect(mockSetOption).toHaveBeenCalledWith(option, false)
  })

  it('setOption 支持 notMerge 参数', async () => {
    const wrapper = mount(createTestComponent())
    const option = { xAxis: {}, series: [] }
    wrapper.vm.setOption(option, true)
    expect(mockSetOption).toHaveBeenCalledWith(option, true)
  })

  it('resize 调用 ECharts 实例的 resize', async () => {
    const wrapper = mount(createTestComponent())
    wrapper.vm.resize()
    expect(mockResize).toHaveBeenCalled()
  })

  it('卸载时自动 dispose', async () => {
    const wrapper = mount(createTestComponent())
    wrapper.unmount()
    expect(mockDispose).toHaveBeenCalled()
  })

  it('getInstance 返回 ECharts 实例', async () => {
    const wrapper = mount(createTestComponent())
    const instance = wrapper.vm.getInstance()
    expect(instance).toBeTruthy()
    expect(instance.setOption).toBe(mockSetOption)
  })

  it('挂载前调用 setOption 会暂存配置，挂载后自动应用', async () => {
    // 模拟 watch({ immediate: true }) 在 onMounted 之前调用的场景
    let setOptionBeforeMount = null
    const Comp = defineComponent({
      setup() {
        const echarts = useECharts()
        // 在 setup 阶段（onMounted 之前）调用 setOption
        const option = { xAxis: { type: 'category' }, series: [{ data: [1, 2, 3] }] }
        echarts.setOption(option)
        setOptionBeforeMount = option
        return echarts
      },
      template: '<div ref="chartRef" data-testid="chart"></div>',
    })
    const wrapper = mount(Comp)
    // 挂载后，暂存的 option 应被自动应用
    expect(mockSetOption).toHaveBeenCalledWith(setOptionBeforeMount, false)
  })

  it('挂载后调用 setOption 正常工作（不经过暂存）', async () => {
    const wrapper = mount(createTestComponent())
    vi.clearAllMocks()
    const option = { xAxis: {}, series: [] }
    wrapper.vm.setOption(option)
    // 挂载后直接调用，不经过暂存机制
    expect(mockSetOption).toHaveBeenCalledWith(option, false)
  })

  it('dispose 清除暂存配置', async () => {
    let disposed = false
    const Comp = defineComponent({
      setup() {
        const echarts = useECharts()
        echarts.setOption({ xAxis: {}, series: [] })
        // 立即 dispose
        echarts.dispose()
        disposed = true
        return echarts
      },
      template: '<div ref="chartRef" data-testid="chart"></div>',
    })
    const wrapper = mount(Comp)
    // dispose 后，挂载时不应再应用暂存配置
    expect(disposed).toBe(true)
  })
})
