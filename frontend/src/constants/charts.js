/** ECharts 图表配置常量

颜色方案对齐 UIDESIGN.md Design Token，通过 CSS 自定义属性运行时同步。
使用 `getChartColors()` 获取当前主题下的颜色值，保持与 Design Token 一致。
*/

/**
 * 从 CSS 自定义属性（Design Token）读取图表颜色
 * 运行时同步，支持暗色模式切换
 * @returns {{ success, danger, info, warning, primary, inputToken, outputToken, p50, p95, p99, textSecondary, textTertiary, border, bgPage }}
 */
export function getChartColors() {
  const style = getComputedStyle(document.documentElement)
  const get = (name) => style.getPropertyValue(name).trim() || null

  return {
    // 系列色（对齐语义色 Design Token，回退值匹配 UIDESIGN.md 默认值）
    success: get('--dm-success') || '#10B981',
    danger: get('--dm-danger') || '#EF4444',
    info: get('--dm-info') || '#3B82F6',
    warning: get('--dm-warning') || '#F59E0B',
    primary: get('--dm-primary') || '#1A1A1A',

    // Token 图表用色
    inputToken: get('--dm-info') || '#3B82F6',
    outputToken: get('--dm-success') || '#10B981',

    // 延迟图表用色
    p50: get('--dm-info') || '#3B82F6',
    p95: get('--dm-warning') || '#F59E0B',
    p99: get('--dm-danger') || '#EF4444',

    // 中性色（回退值匹配 Design Token 默认值）
    textSecondary: get('--dm-text-secondary') || '#737373',
    textTertiary: get('--dm-text-tertiary') || '#A3A3A3',
    border: get('--dm-border') || '#E0E0E0',
    bgPage: get('--dm-bg-page') || '#F2F2F2',
  }
}

/** 通用 tooltip 配置（颜色从 CSS Token 读取） */
export function getTooltipConfig() {
  const c = getChartColors()
  return {
    trigger: 'axis',
    backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--dm-bg-card').trim() || '#FFFFFF',
    borderColor: c.border,
    borderWidth: 1,
    textStyle: {
      color: c.primary,
      fontSize: 13,
    },
    axisPointer: {
      type: 'cross',
      crossStyle: {
        color: c.textTertiary,
      },
    },
  }
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
export function getLegendConfig() {
  const c = getChartColors()
  return {
    top: 0,
    right: 0,
    textStyle: {
      color: c.textSecondary,
      fontSize: 13,
    },
    itemWidth: 16,
    itemHeight: 2,
  }
}

/** 通用 X 轴配置 */
export function getXAxisConfig() {
  const c = getChartColors()
  return {
    type: 'category',
    boundaryGap: false,
    axisLine: {
      lineStyle: { color: c.border },
    },
    axisTick: { show: false },
    axisLabel: {
      color: c.textTertiary,
      fontSize: 12,
    },
  }
}

/** 通用 Y 轴配置 */
export function getYAxisConfig() {
  const c = getChartColors()
  return {
    type: 'value',
    splitLine: {
      lineStyle: { color: c.bgPage, type: 'dashed' },
    },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: c.textTertiary,
      fontSize: 12,
    },
  }
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

/**
 * 将 hex 颜色转换为 rgba 字符串
 * 用于 ECharts 渐变 areaStyle，从 Design Token 颜色派生
 * @param {string} hex - hex 颜色值（如 '#10B981'）
 * @param {number} alpha - 透明度（0-1）
 * @returns {string} rgba 字符串
 */
export function hexToRgba(hex, alpha) {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
