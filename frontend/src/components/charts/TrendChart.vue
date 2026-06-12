<template>
  <div class="chart-wrapper">
    <h3 class="chart-title">
      <i class="fas fa-chart-line"></i>
      问答量趋势（过去 7 天）
    </h3>
    <div ref="chartRef" class="chart-container"></div>
    <div v-if="!data || data.length === 0" class="chart-empty">
      <i class="fas fa-chart-line"></i>
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
  const successData = props.data.map((item) => item.success)
  const errorData = props.data.map((item) => item.error)

  setOption({
    tooltip: {
      ...TOOLTIP_CONFIG,
      formatter(params) {
        const lines = params.map(
          (p) => `${p.marker} ${p.seriesName}: <b>${p.value}</b> 次`
        )
        return `<div style="font-size:13px">${params[0].axisValue}</div>` + lines.join('<br/>')
      },
    },
    legend: {
      ...LEGEND_CONFIG,
      data: ['成功', '失败'],
    },
    grid: GRID_CONFIG,
    xAxis: {
      ...X_AXIS_CONFIG,
      data: dates,
    },
    yAxis: {
      ...Y_AXIS_CONFIG,
      minInterval: 1,
    },
    series: [
      {
        name: '成功',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: CHART_COLORS.success },
        itemStyle: { color: CHART_COLORS.success },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16, 185, 129, 0.15)' },
              { offset: 1, color: 'rgba(16, 185, 129, 0)' },
            ],
          },
        },
        data: successData,
      },
      {
        name: '失败',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: CHART_COLORS.danger },
        itemStyle: { color: CHART_COLORS.danger },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239, 68, 68, 0.15)' },
              { offset: 1, color: 'rgba(239, 68, 68, 0)' },
            ],
          },
        },
        data: errorData,
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
  color: var(--dm-info);
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
