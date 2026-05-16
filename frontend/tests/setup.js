/** vitest 全局 setup — Mock 浏览器 API 与第三方库 */
import { vi } from 'vitest'

// Mock Element Plus — 避免引入完整组件库
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElNotification: vi.fn(),
  ElMessageBox: { confirm: vi.fn() },
}))

// Mock Font Awesome — 图标渲染为 span（测试不需要真实图标）
vi.mock('@fortawesome/fontawesome-free/css/all.css', () => ({}))
