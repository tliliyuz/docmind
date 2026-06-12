/** ECharts 组合式函数 — 响应式 resize + 自动 dispose

用法：
  const { chartRef, setOption } = useECharts()
  // 模板中 <div ref="chartRef" class="chart-container" />
  setOption(option)
*/

import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

export function useECharts() {
  const chartRef = ref(null)
  let chartInstance = null
  let resizeObserver = null
  /** 挂载前暂存的配置项（解决 watch({ immediate: true }) 先于 onMounted 触发的问题） */
  let pendingOption = null

  /** 初始化 ECharts 实例 */
  function init(dom, theme) {
    if (chartInstance) {
      chartInstance.dispose()
    }
    chartInstance = echarts.init(dom, theme)
    return chartInstance
  }

  /** 设置图表配置项 */
  function setOption(option, notMerge = false) {
    if (!chartInstance && chartRef.value) {
      init(chartRef.value)
    }
    if (chartInstance) {
      chartInstance.setOption(option, notMerge)
    } else {
      // 组件挂载前 chartRef.value 为 null，暂存配置项，等 onMounted 后再应用
      pendingOption = { option, notMerge }
    }
  }

  /** 手动 resize */
  function resize() {
    if (chartInstance) {
      chartInstance.resize()
    }
  }

  /** 销毁实例 */
  function dispose() {
    if (resizeObserver && chartRef.value) {
      resizeObserver.unobserve(chartRef.value)
      resizeObserver.disconnect()
      resizeObserver = null
    }
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
    pendingOption = null
  }

  onMounted(() => {
    if (chartRef.value) {
      init(chartRef.value)
      // 应用挂载前暂存的配置项
      if (pendingOption) {
        chartInstance.setOption(pendingOption.option, pendingOption.notMerge)
        pendingOption = null
      }
      // ResizeObserver 监听容器尺寸变化
      resizeObserver = new ResizeObserver(() => {
        resize()
      })
      resizeObserver.observe(chartRef.value)
    }
  })

  onUnmounted(() => {
    dispose()
  })

  return {
    chartRef,
    setOption,
    resize,
    dispose,
    /** 获取 ECharts 实例（高级用法） */
    getInstance: () => chartInstance,
  }
}
