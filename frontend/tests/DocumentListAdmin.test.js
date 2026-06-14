/** DocumentListAdmin 组件测试（管理后台文档管理页） */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  mockGetAdminDocs, mockDeleteDoc,
  mockMessageSuccess, mockMessageError, mockMessageBoxConfirm,
} = vi.hoisted(() => ({
  mockGetAdminDocs: vi.fn(),
  mockDeleteDoc: vi.fn(),
  mockMessageSuccess: vi.fn(),
  mockMessageError: vi.fn(),
  mockMessageBoxConfirm: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getAdminDocuments: mockGetAdminDocs,
}))

vi.mock('@/api/knowledge', () => ({
  deleteDocument: mockDeleteDoc,
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMessageSuccess, error: mockMessageError },
    ElMessageBox: { confirm: mockMessageBoxConfirm },
  }
})

import DocumentListAdmin from '@/views/admin/DocumentList.vue'

const MOCK_ITEMS = [
  {
    uuid: 'doc-uuid-1', filename: 'report.pdf', file_type: 'pdf', file_size: 1048576,
    kb_uuid: 'kb-uuid-10', kb_name: 'HR制度库', kb_visibility: 'public',
    owner_id: 100, owner_username: 'alice',
    status: 'completed', chunk_count: 50, error_message: null,
    created_at: '2026-06-01T08:00:00+00:00',
  },
  {
    uuid: 'doc-uuid-2', filename: '技术手册.docx', file_type: 'docx', file_size: 524288,
    kb_uuid: 'kb-uuid-20', kb_name: 'IT文档', kb_visibility: 'private',
    owner_id: 200, owner_username: null,
    status: 'failed', chunk_count: 0, error_message: '解析失败: 格式不支持',
    created_at: '2026-06-02T12:30:00+00:00',
  },
  {
    uuid: 'doc-uuid-3', filename: 'notes.txt', file_type: 'txt', file_size: 1024,
    kb_uuid: 'kb-uuid-30', kb_name: null, kb_visibility: null,
    owner_id: 300, owner_username: 'bob',
    status: 'deleting', chunk_count: 0, error_message: null,
    created_at: '2026-06-03T16:45:00+00:00',
  },
]

function mockSuccessResponse(items = MOCK_ITEMS, total = 3) {
  mockGetAdminDocs.mockResolvedValue({
    data: { code: '0', data: { items, total } },
  })
}

function getComponent() {
  return mount(DocumentListAdmin, {
    global: {
      stubs: {
        'router-link': { template: '<a class="router-link-stub"><slot /></a>', props: ['to'] },
        'el-input': { template: '<input class="el-input-stub" />', props: ['modelValue', 'placeholder', 'size', 'clearable', 'style'], emits: ['input', 'clear', 'update:modelValue'] },
        'el-select': { template: '<select class="el-select-stub"><slot /></select>', props: ['modelValue', 'placeholder', 'clearable', 'size', 'style'], emits: ['change', 'update:modelValue'] },
        'el-option': { template: '<option class="el-option-stub"><slot /></option>', props: ['label', 'value'] },
        'el-table': { template: '<div class="el-table-stub"><slot /></div>', props: ['data', 'vLoading', 'style', 'rowKey'] },
        // 不渲染 scoped slot，避免 #default="{ row }" 中 row 未定义崩溃
        'el-table-column': { template: '<div class="el-table-col-stub" />', props: ['prop', 'label', 'width', 'minWidth', 'align', 'fixed'] },
        'el-pagination': { template: '<div class="el-pagination-stub" />', props: ['currentPage', 'pageSize', 'total', 'layout'], emits: ['update:currentPage', 'currentChange'] },
        'el-button': { template: '<button class="el-button-stub" :disabled="loading"><slot /></button>', props: ['type', 'loading'] },
      },
      directives: { loading: vi.fn() },
    },
  })
}

describe('DocumentListAdmin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('初始加载', () => {
    it('挂载后调用 getAdminDocuments（含默认 sort 和 order）', async () => {
      mockSuccessResponse()
      getComponent()
      await flushPromises()
      expect(mockGetAdminDocs).toHaveBeenCalledTimes(1)
      expect(mockGetAdminDocs).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
        sort_by: 'created_at',
        order: 'desc',
      })
    })

    it('列表为空时显示空状态', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-state').exists()).toBe(true)
      expect(wrapper.find('.empty-title').text()).toBe('暂无文档')
    })
  })

  describe('搜索', () => {
    it('文件名搜索 300ms 防抖后重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminDocs.mockClear()

      wrapper.vm.searchFilename = 'report'
      wrapper.vm.onSearchInput()
      await flushPromises()
      expect(mockGetAdminDocs).not.toHaveBeenCalled()

      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(mockGetAdminDocs).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1, page_size: 20,
          sort_by: 'created_at', order: 'desc',
          filename: 'report',
        })
      )
    })

    it('搜索清除后刷新（不带 filename 参数）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminDocs.mockClear()

      wrapper.vm.searchFilename = ''
      wrapper.vm.onSearchClear()
      await flushPromises()

      expect(mockGetAdminDocs).toHaveBeenCalledWith({
        page: 1, page_size: 20, sort_by: 'created_at', order: 'desc',
      })
    })
  })

  describe('筛选与排序', () => {
    it('状态筛选变更后重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminDocs.mockClear()

      wrapper.vm.filterStatus = 'failed'
      wrapper.vm.reloadList()
      await flushPromises()

      expect(mockGetAdminDocs).toHaveBeenCalledWith(
        expect.objectContaining({
          page: 1, page_size: 20,
          sort_by: 'created_at', order: 'desc',
          status: 'failed',
        })
      )
    })

    it('排序字段变更后重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminDocs.mockClear()

      wrapper.vm.sortBy = 'file_size'
      wrapper.vm.reloadList()
      await flushPromises()

      expect(mockGetAdminDocs).toHaveBeenCalledWith(
        expect.objectContaining({
          sort_by: 'file_size', order: 'desc',
          page: 1, page_size: 20,
        })
      )
    })

    it('排序方向变更后重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminDocs.mockClear()

      wrapper.vm.sortOrder = 'asc'
      wrapper.vm.reloadList()
      await flushPromises()

      expect(mockGetAdminDocs).toHaveBeenCalledWith(
        expect.objectContaining({
          sort_by: 'created_at', order: 'asc',
          page: 1, page_size: 20,
        })
      )
    })
  })

  describe('分页', () => {
    it('total > pageSize 时显示分页组件', async () => {
      mockSuccessResponse(MOCK_ITEMS, 100)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.pagination-wrap').exists()).toBe(true)
    })

    it('total <= pageSize 时不显示分页组件', async () => {
      mockSuccessResponse(MOCK_ITEMS, 3)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.pagination-wrap').exists()).toBe(false)
    })
  })

  describe('删除', () => {
    it('确认删除后调用 deleteDocument（传入 kb_id 和 doc_id）', async () => {
      mockSuccessResponse()
      mockMessageBoxConfirm.mockResolvedValue('confirm')
      mockDeleteDoc.mockResolvedValue({ data: { code: '0' } })
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.confirmDelete(MOCK_ITEMS[0])
      await flushPromises()
      await flushPromises()

      expect(mockDeleteDoc).toHaveBeenCalledWith('kb-uuid-10', 'doc-uuid-1')
      expect(mockMessageSuccess).toHaveBeenCalledWith('文档已删除')
    })

    it('确认消息包含所属知识库名称和文件名', async () => {
      mockSuccessResponse()
      mockMessageBoxConfirm.mockResolvedValue('confirm')
      mockDeleteDoc.mockResolvedValue({ data: { code: '0' } })
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.confirmDelete(MOCK_ITEMS[0])
      await flushPromises()

      const confirmMsg = mockMessageBoxConfirm.mock.calls[0][0]
      expect(confirmMsg).toContain('report.pdf')
      expect(confirmMsg).toContain('HR制度库')
    })

    it('kb_name 为 null 时确认消息显示"未知"', async () => {
      mockSuccessResponse()
      mockMessageBoxConfirm.mockResolvedValue('confirm')
      mockDeleteDoc.mockResolvedValue({ data: { code: '0' } })
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.confirmDelete(MOCK_ITEMS[2])
      await flushPromises()

      const confirmMsg = mockMessageBoxConfirm.mock.calls[0][0]
      expect(confirmMsg).toContain('未知')
    })

    it('用户取消删除时不调用 API', async () => {
      mockSuccessResponse()
      mockMessageBoxConfirm.mockRejectedValue('cancel')
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.confirmDelete(MOCK_ITEMS[0])
      await flushPromises()

      expect(mockDeleteDoc).not.toHaveBeenCalled()
    })
  })

  describe('错误处理', () => {
    it('加载列表网络异常显示 error toast', async () => {
      const err = new Error('Network Error')
      err.response = { data: { message: '超时' } }
      mockGetAdminDocs.mockRejectedValue(err)
      getComponent()
      await flushPromises()

      expect(mockMessageError).toHaveBeenCalledWith('超时')
    })

    it('加载列表 API 返回非 0 code', async () => {
      mockGetAdminDocs.mockResolvedValue({
        data: { code: 'E9999', message: '权限不足' },
      })
      getComponent()
      await flushPromises()

      expect(mockMessageError).toHaveBeenCalledWith('权限不足')
    })
  })

  describe('工具函数', () => {
    it('getStatusLabel 返回正确的中文标签', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.vm.getStatusLabel('completed')).toBe('已完成')
      expect(wrapper.vm.getStatusLabel('parsing')).toBe('解析中')
      expect(wrapper.vm.getStatusLabel('failed')).toBe('失败')
      expect(wrapper.vm.getStatusLabel('unknown_xyz')).toBe('unknown_xyz')
    })

    it('isTerminal 正确判断终态', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.vm.isTerminal('completed')).toBe(true)
      expect(wrapper.vm.isTerminal('failed')).toBe(true)
      expect(wrapper.vm.isTerminal('success_with_warnings')).toBe(true)
      expect(wrapper.vm.isTerminal('partial_failed')).toBe(true)
      expect(wrapper.vm.isTerminal('parsing')).toBe(false)
      expect(wrapper.vm.isTerminal('uploaded')).toBe(false)
      expect(wrapper.vm.isTerminal('deleting')).toBe(false)
    })

    it('formatFileSize 正确格式化文件大小', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.vm.formatFileSize(0)).toBe('0 B')
      expect(wrapper.vm.formatFileSize(1024)).toBe('1.0 KB')
      expect(wrapper.vm.formatFileSize(1048576)).toBe('1.0 MB')
      expect(wrapper.vm.formatFileSize(null)).toBe('--')
    })

    it('formatDateTime 正确格式化 ISO 字符串', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const result = wrapper.vm.formatDateTime('2026-06-01T08:00:00+00:00')
      expect(result).toMatch(/2026-06-01 \d{2}:\d{2}/)
    })

    it('formatDateTime 无效输入返回 --', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.vm.formatDateTime('')).toBe('--')
      expect(wrapper.vm.formatDateTime('invalid')).toBe('--')
    })
  })
})
