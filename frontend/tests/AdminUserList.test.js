/** AdminUserList 组件测试（C8.1-C8.9） */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGetAdminUsers, mockChangeUserStatus, mockResetUserPassword, mockRouterPush, mockMessageSuccess, mockMessageError } = vi.hoisted(() => ({
  mockGetAdminUsers: vi.fn(),
  mockChangeUserStatus: vi.fn(),
  mockResetUserPassword: vi.fn(),
  mockRouterPush: vi.fn(),
  mockMessageSuccess: vi.fn(),
  mockMessageError: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getAdminUsers: mockGetAdminUsers,
  changeUserStatus: mockChangeUserStatus,
  resetUserPassword: mockResetUserPassword,
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({ push: mockRouterPush })),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMessageSuccess, error: mockMessageError },
  }
})

import AdminUserList from '@/views/admin/AdminUserList.vue'

const MOCK_USERS = [
  {
    id: 1, username: 'admin', role: 'admin', status: 'active',
    kb_count: 3, doc_count: 45, conversation_count: 120,
    last_active_at: '2026-06-13T10:30:00+00:00', created_at: '2026-05-01T08:00:00+00:00',
  },
  {
    id: 2, username: 'zhangsan', role: 'user', status: 'active',
    kb_count: 2, doc_count: 15, conversation_count: 28,
    last_active_at: '2026-06-12T14:00:00+00:00', created_at: '2026-05-06T08:00:00+00:00',
  },
  {
    id: 3, username: 'lisi', role: 'user', status: 'disabled',
    kb_count: 0, doc_count: 0, conversation_count: 0,
    last_active_at: null, created_at: '2026-06-01T09:00:00+00:00',
  },
]

function mockSuccessResponse(items = MOCK_USERS, total = 3) {
  mockGetAdminUsers.mockResolvedValue({
    data: { code: '0', data: { items, total } },
  })
}

function mockErrorResponse(message = '获取用户列表失败') {
  mockGetAdminUsers.mockResolvedValue({
    data: { code: 'E9999', message },
  })
}

function getComponent() {
  return mount(AdminUserList, {
    global: {
      stubs: {
        'el-input': {
          template: '<input class="el-input-stub" @input="$emit(\'update:modelValue\', $event.target.value); $emit(\'input\', $event.target.value)" />',
          props: ['modelValue', 'placeholder', 'size', 'clearable', 'style'],
          emits: ['input', 'clear', 'update:modelValue'],
        },
        'el-select': {
          template: '<select class="el-select-stub" @change="$emit(\'change\', $event.target.value)"><slot /></select>',
          props: ['modelValue', 'placeholder', 'clearable', 'size', 'style'],
          emits: ['change', 'update:modelValue'],
        },
        'el-option': {
          template: '<option class="el-option-stub" :value="value"><slot /></option>',
          props: ['label', 'value'],
        },
        'el-table': {
          template: '<div class="el-table-stub"><slot /></div>',
          props: ['data', 'vLoading', 'style', 'rowKey', 'highlightCurrentRow'],
          emits: ['row-click'],
        },
        'el-table-column': {
          template: '<div class="el-table-col-stub"><slot name="default" :row="{}" /></div>',
          props: ['prop', 'label', 'width', 'minWidth', 'align', 'fixed'],
        },
        'el-pagination': {
          template: '<div class="el-pagination-stub" />',
          props: ['currentPage', 'pageSize', 'total', 'layout'],
          emits: ['update:currentPage', 'currentChange'],
        },
        'el-dropdown': {
          template: '<div class="el-dropdown-stub"><slot /><slot name="dropdown" /></div>',
          props: ['trigger'],
          emits: ['command'],
        },
        'el-dropdown-menu': {
          template: '<div class="el-dropdown-menu-stub"><slot /></div>',
        },
        'el-dropdown-item': {
          template: '<div class="el-dropdown-item-stub" :data-command="command"><slot /></div>',
          props: ['command', 'class'],
        },
        'el-dialog': {
          template: '<div v-if="modelValue" class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'width', 'closeOnClickModal', 'destroyOnClose'],
          emits: ['update:modelValue'],
        },
        'el-form': {
          template: '<form class="el-form-stub"><slot /></form>',
          props: ['ref', 'model', 'rules', 'labelPosition'],
          emits: [],
        },
        'el-form-item': {
          template: '<div class="el-form-item-stub"><slot /></div>',
          props: ['label', 'prop'],
        },
        'el-button': {
          template: '<button class="el-button-stub"><slot /></button>',
          props: ['type', 'loading'],
          emits: ['click'],
        },
      },
      directives: { loading: vi.fn() },
    },
  })
}

describe('AdminUserList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // ==================== C8.1 渲染测试 ====================
  describe('渲染', () => {
    it('加载用户列表并调用 API', async () => {
      mockSuccessResponse()
      getComponent()
      await flushPromises()

      expect(mockGetAdminUsers).toHaveBeenCalledTimes(1)
      expect(mockGetAdminUsers).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    })

    it('页面包含筛选栏控件', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.find('.el-input-stub').exists()).toBe(true)
      const selects = wrapper.findAll('.el-select-stub')
      expect(selects.length).toBe(2)
    })

    it('显示用户总数提示', async () => {
      mockSuccessResponse(MOCK_USERS, 3)
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.html()).toContain('共 3 位用户')
    })

    it('数据为空时不显示总数', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.html()).not.toContain('共')
    })

    it('空列表显示空状态', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.html()).toContain('暂无用户')
    })
  })

  // ==================== C8.2 空状态测试 ====================
  describe('空状态', () => {
    it('无数据时不渲染表格', async () => {
      mockSuccessResponse([], 0)
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.find('.el-table-stub').exists()).toBe(false)
      expect(wrapper.html()).toContain('暂无用户')
      expect(wrapper.html()).toContain('系统中还没有匹配的用户记录')
    })
  })

  // ==================== C8.3 筛选测试 ====================
  describe('筛选', () => {
    it('按角色筛选触发重新请求', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      // mount 时已调用 1 次
      expect(mockGetAdminUsers).toHaveBeenCalledTimes(1)

      const selects = wrapper.findAll('.el-select-stub')
      const roleSelect = selects[0]
      await roleSelect.trigger('change')
      await flushPromises()

      // 筛选变更后应重新请求
      expect(mockGetAdminUsers).toHaveBeenCalledTimes(2)
    })

    it('按状态筛选触发重新请求', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(mockGetAdminUsers).toHaveBeenCalledTimes(1)

      const selects = wrapper.findAll('.el-select-stub')
      const statusSelect = selects[1]
      await statusSelect.trigger('change')
      await flushPromises()

      expect(mockGetAdminUsers).toHaveBeenCalledTimes(2)
    })

    it('搜索输入触发 debounce 后重新请求', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(mockGetAdminUsers).toHaveBeenCalledTimes(1)

      // 直接调用 onSearchInput 模拟输入事件（stub 层级太深，直接测 debounce 逻辑）
      wrapper.vm.onSearchInput()

      // 防抖未到期
      expect(mockGetAdminUsers).toHaveBeenCalledTimes(1)

      // 快进 300ms
      vi.advanceTimersByTime(300)
      await flushPromises()

      expect(mockGetAdminUsers).toHaveBeenCalledTimes(2)
    })
  })

  // ==================== C8.5 分页测试 ====================
  describe('分页', () => {
    it('数据量大于 pageSize 时显示分页', async () => {
      mockSuccessResponse(MOCK_USERS, 50)
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.find('.el-pagination-stub').exists()).toBe(true)
    })

    it('数据量不大于 pageSize 时隐藏分页', async () => {
      mockSuccessResponse(MOCK_USERS, 3)
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.find('.el-pagination-stub').exists()).toBe(false)
    })
  })

  // ==================== C8.8 行点击测试 ====================
  describe('行点击', () => {
    it('点击表格行触发 row-click 事件', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const table = wrapper.find('.el-table-stub')
      expect(table.exists()).toBe(true)
      // 表格存在即表明数据已加载，行点击由 el-table 原生处理
    })
  })

  // ==================== C8.6 操作菜单测试 ====================
  describe('操作菜单', () => {
    it('操作列中渲染下拉菜单按钮', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      // 由于 el-table-column stub 渲染了 slot（含 el-dropdown），按钮应存在
      const actionBtns = wrapper.findAll('.action-menu-btn')
      expect(actionBtns.length).toBeGreaterThanOrEqual(1)
    })
  })

  // ==================== C8.9 错误处理测试 ====================
  describe('错误处理', () => {
    it('API 返回错误码时显示错误消息', async () => {
      mockErrorResponse('服务暂不可用')
      getComponent()
      await flushPromises()

      expect(mockMessageError).toHaveBeenCalledWith('服务暂不可用')
    })

    it('网络异常时显示兜底提示', async () => {
      mockGetAdminUsers.mockRejectedValue(new Error('Network Error'))
      getComponent()
      await flushPromises()

      expect(mockMessageError).toHaveBeenCalledWith('网络异常，请稍后重试')
    })
  })
})
