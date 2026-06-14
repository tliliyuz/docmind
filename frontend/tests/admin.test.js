/** admin API 测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn(),
}))

// Mock axios 实例：仅在边界处截断，验证函数调用的参数传递
vi.mock('@/api/index', () => ({
  default: { get: mockGet },
}))

import { getAdminStats, getAdminKnowledgeBases, getAdminDocuments, getTraceStats } from '@/api/admin'

describe('admin API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getAdminStats', () => {
    it('调用 GET /admin/stats 不传参数', async () => {
      mockGet.mockResolvedValue({ data: { code: '0', data: { user_count: 10 } } })
      await getAdminStats()
      expect(mockGet).toHaveBeenCalledTimes(1)
      expect(mockGet).toHaveBeenCalledWith('/admin/stats')
    })

    it('返回成功响应时透传 axios 结果', async () => {
      const expected = { data: { code: '0', data: { user_count: 5 } } }
      mockGet.mockResolvedValue(expected)
      const result = await getAdminStats()
      expect(result).toBe(expected)
    })

    it('网络错误时不捕获，交由调用方处理', async () => {
      const err = new Error('Network Error')
      mockGet.mockRejectedValue(err)
      await expect(getAdminStats()).rejects.toThrow('Network Error')
    })
  })

  describe('getAdminKnowledgeBases', () => {
    it('调用 GET /admin/knowledge-bases 并透传查询参数', async () => {
      mockGet.mockResolvedValue({ data: { code: '0', data: { items: [], total: 0 } } })
      const params = { page: 1, page_size: 20, search: '测试', visibility: 'public', status: 'active' }
      await getAdminKnowledgeBases(params)
      expect(mockGet).toHaveBeenCalledTimes(1)
      expect(mockGet).toHaveBeenCalledWith('/admin/knowledge-bases', { params })
    })

    it('附加 user_id 参数', async () => {
      mockGet.mockResolvedValue({ data: { code: '0', data: { items: [], total: 0 } } })
      await getAdminKnowledgeBases({ user_id: 42 })
      expect(mockGet).toHaveBeenCalledWith('/admin/knowledge-bases', { params: { user_id: 42 } })
    })
  })

  describe('getAdminDocuments', () => {
    it('调用 GET /admin/documents 并透传查询参数', async () => {
      mockGet.mockResolvedValue({ data: { code: '0', data: { items: [], total: 0 } } })
      const params = { kb_id: 1, page: 1, page_size: 20, status: 'completed', filename: 'test', sort_by: 'created_at', order: 'desc' }
      await getAdminDocuments(params)
      expect(mockGet).toHaveBeenCalledTimes(1)
      expect(mockGet).toHaveBeenCalledWith('/admin/documents', { params })
    })

    it('附加 sort_by 和 order 参数', async () => {
      mockGet.mockResolvedValue({ data: { code: '0', data: { items: [], total: 0 } } })
      await getAdminDocuments({ sort_by: 'file_size', order: 'asc' })
      expect(mockGet).toHaveBeenCalledWith('/admin/documents', { params: { sort_by: 'file_size', order: 'asc' } })
    })
  })

  describe('getTraceStats', () => {
    it('调用 GET /admin/stats/traces 并透传查询参数', async () => {
      mockGet.mockResolvedValue({ data: { code: '0', data: { trend: [], latency: [], tokens: [] } } })
      const params = { days: 7 }
      await getTraceStats(params)
      expect(mockGet).toHaveBeenCalledTimes(1)
      expect(mockGet).toHaveBeenCalledWith('/admin/stats/traces', { params })
    })

    it('网络错误时不捕获，交由调用方处理', async () => {
      const err = new Error('Network Error')
      mockGet.mockRejectedValue(err)
      await expect(getTraceStats()).rejects.toThrow('Network Error')
    })
  })

  describe.each([
    ['getAdminKnowledgeBases', getAdminKnowledgeBases, '/admin/knowledge-bases'],
    ['getAdminDocuments', getAdminDocuments, '/admin/documents'],
    ['getTraceStats', getTraceStats, '/admin/stats/traces'],
  ])('%s', (name, fn, path) => {
    it('不传参数时默认空对象', async () => {
      mockGet.mockResolvedValue({ data: { code: '0', data: {} } })
      await fn()
      expect(mockGet).toHaveBeenCalledWith(path, { params: {} })
    })
  })
})
