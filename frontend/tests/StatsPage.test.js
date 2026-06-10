/** StatsPage 组件测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGetAdminStats } = vi.hoisted(() => ({
  mockGetAdminStats: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getAdminStats: mockGetAdminStats,
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

function getComponent() {
  return mount(StatsPage, {
    global: {
      stubs: {
        'router-link': { template: '<a class="router-link-stub"><slot /></a>', props: ['to'] },
      },
      directives: { loading: vi.fn() },
    },
  })
}

describe('StatsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('初始状态', () => {
    it('挂载时 API 未 resolve 前不渲染统计卡片（loading 态）', async () => {
      mockGetAdminStats.mockReturnValue(new Promise(() => {}))
      const wrapper = getComponent()
      await flushPromises()
      // loading 为 true 时 v-if="loading" 的 div 占位，stat-cards-row 不渲染
      expect(wrapper.find('.stat-cards-row').exists()).toBe(false)
    })
  })

  describe('数据加载成功', () => {
    it('渲染 7 个统计卡片（4 核心 + 3 二级）', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const cards = wrapper.findAll('.stat-card')
      expect(cards).toHaveLength(7)
    })

    it('显示用户总数（千分位格式化）', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[0].text()).toBe('1,234')
    })

    it('显示知识库数', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[1].text()).toBe('56')
    })

    it('显示文档总数', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[2].text()).toBe('890')
    })

    it('显示总会话数', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[3].text()).toBe('234')
    })

    it('二级卡片：显示分块总数', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[4].text()).toBe('12,345')
    })

    it('二级卡片：显示消息总数', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[5].text()).toBe('5,678')
    })

    it('二级卡片：formatStorage 转换 1 GB', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const values = wrapper.findAll('.stat-value')
      expect(values[6].text()).toBe('1.0 GB')
    })

    it('渲染快捷入口（2 个快速链接）', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      const links = wrapper.findAll('.quick-link-card')
      expect(links).toHaveLength(2)
    })

    it('快捷入口包含"知识库管理"', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.text()).toContain('知识库管理')
    })

    it('快捷入口包含"文档管理"', async () => {
      mockGetAdminStats.mockResolvedValue({
        data: { code: '0', data: MOCK_STATS },
      })
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.text()).toContain('文档管理')
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
})
