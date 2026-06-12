<template>
  <div class="chart-wrapper">
    <h3 class="chart-title">
      <i class="fas fa-coins"></i>
      Token 使用统计（过去 7 天）
    </h3>
    <div ref="chartRef" class="chart-container"></div>
    <div v-if="!data || data.length === 0" class="chart-empty">
      <i class="fas fa-coins"></i>
      <span>暂无数据</span>
    </div>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { useECharts } from '@/composables/useECharts'
import {
  CHART_COLORS,
  TOOLTIP_CONFIG,
  GRID_CONFIG,
  LEGEND_CONFIG,
  X_AXIS_CONFIG,
  Y_AXIS_CONFIG,
  formatTokens,
} from '@/constants/charts'

const props = defineProps({
  data: {
    type: Array,
    default: () => [],
  },
})

const { chartRef, setOption } = useECharts()

function renderChart() {
  if (!props.data || props.data.length === 0) return

  const dates = props.data.map((item) => item.date)
  const inputData = props.data.map((item) => item.input)
  const outputData = props.data.map((item) => item.output)

  setOption({
    tooltip: {
      ...TOOLTIP_CONFIG,
      formatter(params) {
        const lines = params.map(
          (p) => `${p.marker} ${p.seriesName}: <b>${formatTokens(p.value)}</b>`
        )
        return `<div style="font-size:13px">${params[0].axisValue}</div>` + lines.join('<br/>')
      },
    },
    legend: {
      ...LEGEND_CONFIG,
      data: ['Input Token', 'Output Token'],
    },
    grid: GRID_CONFIG,
    xAxis: {
      ...X_AXIS_CONFIG,
      boundaryGap: true,
      data: dates,
    },
    yAxis: {
      ...Y_AXIS_CONFIG,
      axisLabel: {
        ...Y_AXIS_CONFIG.axisLabel,
        formatter: (val) => formatTokens(val),
      },
    },
    series: [
      {
        name: 'Input Token',
        type: 'bar',
        stack: 'token',
        barWidth: '40%',
        itemStyle: {
          color: CHART_COLORS.inputToken,
          borderRadius: [0, 0, 0, 0],
        },
        data: inputData,
      },
      {
        name: 'Output Token',
        type: 'bar',
        stack: 'token',
        barWidth: '40%',
        itemStyle: {
          color: CHART_COLORS.outputToken,
          borderRadius: [4, 4, 0, 0],
        },
        data: outputData,
      },
    ],
  })
}

watch(() => props.data, renderChart, { immediate: true })
</script>

<style scoped>
.chart-wrapper {
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  padding: var(--dm-space-5);
}

.chart-title {
  font-size: var(--dm-text-base);
  font-weight: var(--dm-weight-semibold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-4);
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
}

.chart-title i {
  color: var(--dm-warning);
  font-size: var(--dm-text-sm);
}

.chart-container {
  width: 100%;
  height: 300px;
}

.chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--dm-text-tertiary);
  gap: var(--dm-space-2);
}

.chart-empty i {
  font-size: 32px;
  opacity: 0.4;
}
</style>
