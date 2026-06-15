/**
 * 通用格式化工具函数
 *
 * 统一管理项目中重复定义的格式化逻辑，避免多文件复制粘贴。
 */

/**
 * 格式化 ISO 日期字符串为 `YYYY-MM-DD HH:mm`
 * @param {string|null|undefined} isoString
 * @returns {string}
 */
export function formatDateTime(isoString) {
  if (!isoString) return '--'
  const d = new Date(isoString)
  if (isNaN(d.getTime())) return '--'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * 格式化文件大小为可读字符串（B / KB / MB / GB）
 * @param {number|null|undefined} bytes
 * @returns {string}
 */
export function formatFileSize(bytes) {
  if (bytes == null) return '--'
  const num = Number(bytes)
  if (num === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(num) / Math.log(1024)), units.length - 1)
  return (num / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}
