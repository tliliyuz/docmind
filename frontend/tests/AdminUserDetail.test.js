/** AdminUserDetail 组件测试（C8.10-C8.14） */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockRouteParams = { user_id: '2' }

const { mockGetAdminUserDetail, mockChangeUserStatus, mockResetUserPassword, mockRouterPush, mockMessageSuccess, mockMessageError } = vi.hoisted(() => ({
  mockGetAdminUserDetail: vi.fn(),
  mockChangeUserStatus: vi.fn(),
  mockResetUserPassword: vi.fn(),
  mockRouterPush: vi.fn(),
  mockMessageSuccess: vi.fn(),
  mockMessageError: vi.fn(),
}))

vi.mock('@/api/admin', () => ({
  getAdminUserDetail: mockGetAdminUserDetail,
  changeUserStatus: mockChangeUserStatus,
  resetUserPassword: mockResetUserPassword,
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({ push: mockRouterPush })),
  useRoute: vi.fn(() => ({ params: mockRouteParams })),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMessageSuccess, error: mockMessageError },
  }
})

import AdminUserDetail from '@/views/admin/AdminUserDetail.vue'

const MOCK_USER = {
  id: 2,
  username: 'zhangsan',
  role: 'user',
  status: 'active',
  kb_count: 2,
  doc_count: 15,
  conversation_count: 28,
  message_count: 156,
  total_input_tokens: 524000,
  total_output_tokens: 128000,
  last_active_at: '2026-06-13T10:30:00+00:00',
  created_at: '2026-05-06T08:00:00+00:00',
}

const MOCK_DISABLED_USER = {
  ...MOCK_USER,
  id: 3,
  username: 'lisi',
  status: 'disabled',
  kb_count: 0,
  doc_count: 0,
  conversation_count: 0,
  message_count: 0,
  total_input_tokens: 0,
  total_output_tokens: 0,
  last_active_at: null,
}

function mockSuccessResponse(user = MOCK_USER) {
  mockGetAdminUserDetail.mockResolvedValue({
    data: { code: '0', data: user },
  })
}

function mockErrorResponse(message = '获取用户详情失败') {
  mockGetAdminUserDetail.mockResolvedValue({
    data: { code: 'E7002', message },
  })
}

function getComponent() {
  return mount(AdminUserDetail, {
    global: {
      stubs: {
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
        'el-input': {
          template: '<input class="el-input-stub" />',
          props: ['modelValue', 'type', 'showPassword', 'placeholder'],
          emits: ['update:modelValue'],
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

describe('AdminUserDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // 重置 route params
    mockRouteParams.user_id = '2'
  })

  // ==================== C8.10 渲染测试 ====================
  describe('渲染', () => {
    it('加载用户详情并显示信息卡片', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      expect(mockGetAdminUserDetail).toHaveBeenCalledWith(2)
      const html = wrapper.html()
      expect(html).toContain('zhangsan')
      expect(html).toContain('普通用户')
      expect(html).toContain('正常')
    })

    it('显示 6 张统计卡片', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const html = wrapper.html()
      expect(html).toContain('知识库')
      expect(html).toContain('文档')
      expect(html).toContain('会话')
      expect(html).toContain('消息')
      expect(html).toContain('Input Token')
      expect(html).toContain('Output Token')
    })

    it('统计卡片显示正确的数值', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const html = wrapper.html()
      expect(html).toContain('2')      // kb_count
      expect(html).toContain('15')     // doc_count
      expect(html).toContain('28')     // conversation_count
      expect(html).toContain('156')    // message_count
      expect(html).toContain('524.0k') // total_input_tokens
      expect(html).toContain('128.0k') // total_output_tokens
    })

    it('Token 超过 1M 时显示 M 单位', async () => {
      mockSuccessResponse({
        ...MOCK_USER,
        total_input_tokens: 2500000,
        total_output_tokens: 1500000,
      })
      const wrapper = getComponent()
      await flushPromises()

      const html = wrapper.html()
      expect(html).toContain('2.5M')
      expect(html).toContain('1.5M')
    })

    it('显示快捷操作按钮', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const html = wrapper.html()
      expect(html).toContain('禁用用户')
      expect(html).toContain('重置密码')
    })

    it('已禁用用户显示启用按钮', async () => {
      mockSuccessResponse(MOCK_DISABLED_USER)
      const wrapper = getComponent()
      await flushPromises()

      const html = wrapper.html()
      expect(html).toContain('启用用户')
    })

    it('显示注册时间', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const html = wrapper.html()
      expect(html).toContain('2026-05-06')
    })

    it('从未活跃显示"从未活跃"', async () => {
      mockSuccessResponse(MOCK_DISABLED_USER)
      const wrapper = getComponent()
      await flushPromises()

      const html = wrapper.html()
      expect(html).toContain('从未活跃')
    })
  })

  // ==================== C8.11 加载状态测试 ====================
  describe('加载状态', () => {
    it('加载中显示 loading 状态', () => {
      mockGetAdminUserDetail.mockReturnValue(new Promise(() => {})) // 永不 resolve
      const wrapper = getComponent()
      // loading 为 true 时不渲染用户内容
      expect(wrapper.html()).not.toContain('zhangsan')
    })
  })

  // ==================== C8.12 错误状态测试 ====================
  describe('错误状态', () => {
    it('API 返回错误时显示错误信息', async () => {
      mockErrorResponse('用户不存在')
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.html()).toContain('加载失败')
      expect(wrapper.html()).toContain('用户不存在')
      expect(wrapper.html()).toContain('返回列表')
    })

    it('缺少 user_id 参数时显示错误', async () => {
      mockRouteParams.user_id = undefined
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.html()).toContain('缺少 user_id 参数')
    })

    it('网络异常时显示兜底提示', async () => {
      mockGetAdminUserDetail.mockRejectedValue({ response: { data: { message: '网络异常，请稍后重试' } } })
      const wrapper = getComponent()
      await flushPromises()

      expect(wrapper.html()).toContain('加载失败')
    })
  })

  // ==================== C8.13 导航测试 ====================
  describe('导航', () => {
    it('点击返回按钮跳转到用户列表', async () => {
      mockSuccessResponse()
      const wrapper = getComponent()
      await flushPromises()

      const backBtn = wrapper.find('.back-btn')
      await backBtn.trigger('click')
      expect(mockRouterPush).toHaveBeenCalledWith('/admin/users')
    })

    it('错误状态下也显示返回按钮', async () => {
      mockErrorResponse('用户不存在')
      const wrapper = getComponent()
      await flushPromises()

      const backBtns = wrapper.findAll('.back-btn')
      expect(backBtns.length).toBeGreaterThanOrEqual(1)
    })
  })


})
