/** ECharts 图表配置常量

颜色方案对齐 UIDESIGN.md Design Token，保持视觉一致性。
*/

/** 颜色方案 — 基于 Design Token 语义色 */
export const CHART_COLORS = {
  // 系列色
  success: '#10B981',   // --dm-success
  danger: '#EF4444',    // --dm-danger
  info: '#3B82F6',      // --dm-info
  warning: '#F59E0B',   // --dm-warning
  primary: '#1A1A1A',   // --dm-primary

  // Token 图表用色
  inputToken: '#3B82F6',   // 蓝色（输入）
  outputToken: '#10B981',  // 绿色（输出）

  // 延迟图表用色
  p50: '#3B82F6',    // 蓝色
  p95: '#F59E0B',    // 橙色
  p99: '#EF4444',    // 红色

  // 中性色
  textSecondary: '#737373',
  textTertiary: '#A3A3A3',
  border: '#E0E0E0',
  bgPage: '#F2F2F2',
}

/** 通用 tooltip 配置 */
export const TOOLTIP_CONFIG = {
  trigger: 'axis',
  backgroundColor: '#FFFFFF',
  borderColor: '#E0E0E0',
  borderWidth: 1,
  textStyle: {
    color: '#1A1A1A',
    fontSize: 13,
  },
  axisPointer: {
    type: 'cross',
    crossStyle: {
      color: '#A3A3A3',
    },
  },
}

/** 通用 grid 配置 */
export const GRID_CONFIG = {
  left: '3%',
  right: '4%',
  bottom: '3%',
  top: '15%',
  containLabel: true,
}

/** 通用 legend 配置 */
export const LEGEND_CONFIG = {
  top: 0,
  right: 0,
  textStyle: {
    color: '#737373',
    fontSize: 13,
  },
  itemWidth: 16,
  itemHeight: 2,
}

/** 通用 X 轴配置 */
export const X_AXIS_CONFIG = {
  type: 'category',
  boundaryGap: false,
  axisLine: {
    lineStyle: { color: '#E0E0E0' },
  },
  axisTick: { show: false },
  axisLabel: {
    color: '#A3A3A3',
    fontSize: 12,
  },
}

/** 通用 Y 轴配置 */
export const Y_AXIS_CONFIG = {
  type: 'value',
  splitLine: {
    lineStyle: { color: '#EBEBEB', type: 'dashed' },
  },
  axisLine: { show: false },
  axisTick: { show: false },
  axisLabel: {
    color: '#A3A3A3',
    fontSize: 12,
  },
}

/** 毫秒格式化（tooltip/axisLabel 共用） */
export function formatMs(ms) {
  if (ms == null) return '--'
  if (ms < 1000) return ms + 'ms'
  return (ms / 1000).toFixed(1) + 's'
}

/** Token 数格式化（大数简化） */
export function formatTokens(val) {
  if (val == null) return '--'
  if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M'
  if (val >= 1000) return (val / 1000).toFixed(1) + 'K'
  return String(val)
}
