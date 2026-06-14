/** KnowledgeListAdmin 组件测试（管理后台知识库管理页） */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  mockGetAdminKBs, mockUpdateKB, mockDeleteKB,
  mockMessageSuccess, mockMessageError, mockMessageBoxConfirm,
} = vi.hoisted(() => ({
  mockGetAdminKBs: vi.fn(),
  mockUpdateKB: vi.fn(),
  mockDeleteKB: vi.fn(),
  mockMessageSuccess: vi.fn(),
  mockMessageError: vi.fn(),
  mockMessageBoxConfirm: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getAdminKnowledgeBases: mockGetAdminKBs,
}))

vi.mock('@/api/knowledge', () => ({
  updateKnowledgeBase: mockUpdateKB,
  deleteKnowledgeBase: mockDeleteKB,
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMessageSuccess, error: mockMessageError },
    ElMessageBox: { confirm: mockMessageBoxConfirm },
  }
})

import KnowledgeListAdmin from '@/views/admin/KnowledgeList.vue'

const MOCK_ITEMS = [
  {
    uuid: 'kb-admin-1', name: '测试知识库A', description: '描述A',
    user_id: 10, username: 'alice', visibility: 'public',
    doc_count: 5, chunk_count: 200, status: 'active',
    created_at: '2026-06-01T08:00:00+00:00',
  },
  {
    uuid: 'kb-admin-2', name: '测试知识库B', description: '',
    user_id: 20, username: null, visibility: 'private',
    doc_count: 0, chunk_count: 0, status: 'active',
    created_at: '2026-06-02T12:30:00+00:00',
  },
  {
    uuid: 'kb-admin-3', name: '删除中的知识库', description: null,
    user_id: 30, username: 'bob', visibility: 'private',
    doc_count: 10, chunk_count: 500, status: 'deleting',
    created_at: '2026-06-03T16:45:00+00:00',
  },
]

function mockSuccessResponse(items = MOCK_ITEMS, total = 3) {
  mockGetAdminKBs.mockResolvedValue({
    data: { code: '0', data: { items, total } },
  })
}

// 浅层 stub 不渲染 el-table-column 的 scoped slot，避免 row 未定义崩溃
function getComponent() {
  return mount(KnowledgeListAdmin, {
    global: {
      stubs: {
        'router-link': { template: '<a class="router-link-stub"><slot /></a>', props: ['to'] },
        'el-input': { template: '<input class="el-input-stub" />', props: ['modelValue', 'placeholder', 'size', 'clearable', 'style', 'maxlength', 'showWordLimit', 'type', 'rows'], emits: ['input', 'clear', 'update:modelValue'] },
        'el-select': { template: '<select class="el-select-stub"><slot /></select>', props: ['modelValue', 'placeholder', 'clearable', 'size', 'style'], emits: ['change', 'update:modelValue'] },
        'el-option': { template: '<option class="el-option-stub"><slot /></option>', props: ['label', 'value'] },
        'el-table': { template: '<div class="el-table-stub"><slot /></div>', props: ['data', 'vLoading', 'style', 'rowKey'] },
        // 不渲染默认 slot：避免 scoped slot #default="{ row }" 中 row 未定义导致崩溃
        'el-table-column': { template: '<div class="el-table-col-stub" />', props: ['prop', 'label', 'width', 'minWidth', 'align', 'fixed'] },
        'el-pagination': { template: '<div class="el-pagination-stub" />', props: ['currentPage', 'pageSize', 'total', 'layout'], emits: ['update:currentPage', 'currentChange'] },
        'el-dialog': { template: '<div v-if="modelValue" class="el-dialog-stub"><slot /><slot name="footer" /></div>', props: ['modelValue', 'title', 'width', 'closeOnClickModal', 'destroyOnClose'], emits: ['update:modelValue'] },
        'el-form': { template: '<div class="el-form-stub"><slot /></div>', props: ['ref', 'model', 'rules', 'labelPosition'] },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>', props: ['label', 'prop'] },
        'el-radio-group': { template: '<div class="el-radio-group-stub"><slot /></div>', props: ['modelValue'], emits: ['update:modelValue'] },
        'el-radio': { template: '<div class="el-radio-stub"><slot /></div>', props: ['value'] },
        'el-button': { template: '<button class="el-button-stub" :disabled="loading"><slot /></button>', props: ['type', 'loading'] },
      },
      directives: { loading: vi.fn() },
    },
  })
}

describe('KnowledgeListAdmin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('初始加载', () => {
    it('挂载后调用 getAdminKnowledgeBases（默认参数）', async () => {
      mockSuccessResponse()
      getComponent()
      await flushPromises()
      expect(mockGetAdminKBs).toHaveBeenCalledTimes(1)
      expect(mockGetAdminKBs).toHaveBeenCalledWith({
        page: 1,
        page_size: 20,
      })
    })

    it('列表为空时显示空状态', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.empty-state').exists()).toBe(true)
      expect(wrapper.find('.empty-title').text()).toBe('暂无知识库')
    })
  })

  describe('搜索', () => {
    it('输入搜索文本后 300ms 防抖触发重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminKBs.mockClear()

      // 直接调用 vm 方法模拟搜索
      wrapper.vm.searchText = '测试搜索'
      wrapper.vm.onSearchInput()
      await flushPromises()

      expect(mockGetAdminKBs).not.toHaveBeenCalled()

      vi.advanceTimersByTime(300)
      await flushPromises()
      expect(mockGetAdminKBs).toHaveBeenCalledTimes(1)
      expect(mockGetAdminKBs).toHaveBeenCalledWith(
        expect.objectContaining({ search: '测试搜索' })
      )
    })

    it('搜索清除后刷新列表（不带 search 参数）', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminKBs.mockClear()

      wrapper.vm.searchText = ''
      wrapper.vm.onSearchClear()
      await flushPromises()
      expect(mockGetAdminKBs).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    })
  })

  describe('筛选', () => {
    it('可见性筛选变更后重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminKBs.mockClear()

      wrapper.vm.filterVisibility = 'public'
      // 直接调用 reloadList（由 @change 触发）
      wrapper.vm.reloadList()
      await flushPromises()

      expect(mockGetAdminKBs).toHaveBeenCalledWith(
        expect.objectContaining({ visibility: 'public', page: 1, page_size: 20 })
      )
    })

    it('状态筛选变更后重新加载', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminKBs.mockClear()

      wrapper.vm.filterStatus = 'deleting'
      wrapper.vm.reloadList()
      await flushPromises()

      expect(mockGetAdminKBs).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'deleting', page: 1, page_size: 20 })
      )
    })
  })

  describe('分页', () => {
    it('total > pageSize 时显示分页', async () => {
      mockSuccessResponse(MOCK_ITEMS, 50)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.pagination-wrap').exists()).toBe(true)
    })

    it('total <= pageSize 时不显示分页', async () => {
      mockSuccessResponse(MOCK_ITEMS, 3)
      const wrapper = getComponent()
      await flushPromises()
      expect(wrapper.find('.pagination-wrap').exists()).toBe(false)
    })
  })

  describe('编辑弹窗', () => {
    it('打开弹窗预填当前行数据', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      wrapper.vm.openEditDialog(MOCK_ITEMS[0])
      await flushPromises()

      expect(wrapper.vm.editFormData.name).toBe('测试知识库A')
      expect(wrapper.vm.editFormData.description).toBe('描述A')
      expect(wrapper.vm.editFormData.visibility).toBe('public')
    })

    it('保存成功后关闭弹窗并刷新列表', async () => {
      mockSuccessResponse()
      mockUpdateKB.mockResolvedValue({ data: { code: '0' } })
      const wrapper = getComponent()
      await flushPromises()
      mockGetAdminKBs.mockClear()

      wrapper.vm.openEditDialog(MOCK_ITEMS[0])
      wrapper.vm.editFormRef = { validate: vi.fn(() => Promise.resolve(true)) }
      await wrapper.vm.handleEditSubmit()
      await flushPromises()

      expect(mockUpdateKB).toHaveBeenCalledWith('kb-admin-1', {
        name: '测试知识库A',
        description: '描述A',
        visibility: 'public',
      })
      expect(mockMessageSuccess).toHaveBeenCalledWith('知识库已更新')
      expect(wrapper.vm.editDialogVisible).toBe(false)
    })

    it('表单校验失败时不提交更新', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      wrapper.vm.openEditDialog(MOCK_ITEMS[0])
      wrapper.vm.editFormRef = { validate: vi.fn(() => Promise.resolve(false)) }
      await wrapper.vm.handleEditSubmit()
      await flushPromises()

      expect(mockUpdateKB).not.toHaveBeenCalled()
    })

    it('表单校验异常时不提交更新', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      wrapper.vm.openEditDialog(MOCK_ITEMS[0])
      wrapper.vm.editFormRef = { validate: vi.fn(() => Promise.reject()) }
      await wrapper.vm.handleEditSubmit()
      await flushPromises()

      expect(mockUpdateKB).not.toHaveBeenCalled()
    })
  })

  describe('删除', () => {
    it('确认删除后调用 deleteKnowledgeBase 并刷新', async () => {
      mockSuccessResponse()
      mockMessageBoxConfirm.mockResolvedValue('confirm')
      mockDeleteKB.mockResolvedValue({ data: { code: '0' } })
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.confirmDelete(MOCK_ITEMS[0])
      await flushPromises()
      await flushPromises()

      expect(mockDeleteKB).toHaveBeenCalledWith('kb-admin-1')
      expect(mockMessageSuccess).toHaveBeenCalledWith('知识库已删除')
    })

    it('用户取消删除时不调用 API', async () => {
      mockSuccessResponse()
      mockMessageBoxConfirm.mockRejectedValue('cancel')
      const wrapper = getComponent()
      await flushPromises()

      await wrapper.vm.confirmDelete(MOCK_ITEMS[0])
      await flushPromises()

      expect(mockDeleteKB).not.toHaveBeenCalled()
    })
  })

  describe('错误处理', () => {
    it('加载列表网络异常显示错误 toast', async () => {
      const err = new Error('Network Error')
      err.response = { data: { message: '网络异常信息' } }
      mockGetAdminKBs.mockRejectedValue(err)
      getComponent()
      await flushPromises()

      expect(mockMessageError).toHaveBeenCalledWith('网络异常信息')
    })

    it('加载列表 API 返回非 0 code', async () => {
      mockGetAdminKBs.mockResolvedValue({
        data: { code: 'E9999', message: '服务器错误' },
      })
      getComponent()
      await flushPromises()

      expect(mockMessageError).toHaveBeenCalledWith('服务器错误')
    })
  })

  describe('formatDateTime', () => {
    it('有效 ISO 字符串返回本地化时间', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const result = wrapper.vm.formatDateTime('2026-06-01T08:00:00+00:00')
      expect(result).toMatch(/2026-06-01 \d{2}:\d{2}/)
    })

    it('空字符串返回 --', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.vm.formatDateTime('')).toBe('--')
    })

    it('无效日期字符串返回 --', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.vm.formatDateTime('invalid-date')).toBe('--')
    })
  })
})
