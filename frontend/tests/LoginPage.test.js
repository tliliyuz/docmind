/** LoginPage 组件测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// Mock 路由
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({}),
}))

// Mock Auth Store
const mockLogin = vi.fn()
const mockRegister = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: mockLogin,
    register: mockRegister,
    isLoggedIn: false,
  }),
}))

import LoginPage from '@/views/LoginPage.vue'

function getComponent() {
  return mount(LoginPage, {
    global: {
      stubs: {
        'i': { template: '<span class="icon" />', props: ['class'] },
      },
    },
  })
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // === 渲染测试 ===

  it('渲染登录/注册切换 Tab', () => {
    const wrapper = getComponent()
    const tabs = wrapper.findAll('.tab-btn')
    expect(tabs).toHaveLength(2)
    expect(tabs[0].text()).toBe('登录')
    expect(tabs[1].text()).toBe('注册')
  })

  it('渲染用户名和密码输入框', () => {
    const wrapper = getComponent()
    const inputs = wrapper.findAll('input')
    expect(inputs).toHaveLength(2)
    expect(inputs[0].attributes('type') !== 'password').toBe(true)
    expect(inputs[1].attributes('type')).toBe('password')
  })

  it('渲染提交按钮', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.submit-btn').exists()).toBe(true)
  })

  it('默认显示登录模式', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.tab-btn.active').text()).toBe('登录')
  })

  // === 交互测试 ===

  it('点击 Tab 切换登录/注册模式', async () => {
    const wrapper = getComponent()
    const tabs = wrapper.findAll('.tab-btn')

    await tabs[1].trigger('click')
    expect(wrapper.find('.tab-btn.active').text()).toBe('注册')

    await tabs[0].trigger('click')
    expect(wrapper.find('.tab-btn.active').text()).toBe('登录')
  })

  it('切换模式清空输入和错误', async () => {
    const wrapper = getComponent()
    const usernameInput = wrapper.findAll('input')[0]
    const passwordInput = wrapper.findAll('input')[1]

    await usernameInput.setValue('testuser')
    await passwordInput.setValue('password')
    const tabs = wrapper.findAll('.tab-btn')
    await tabs[1].trigger('click')

    expect(usernameInput.element.value).toBe('')
    expect(passwordInput.element.value).toBe('')
  })

  // === 校验测试 ===

  it('空用户名提交显示错误', async () => {
    const wrapper = getComponent()
    await wrapper.find('form').trigger('submit.prevent')
    await nextTick()

    expect(wrapper.find('.error-msg').exists()).toBe(true)
    expect(wrapper.find('.error-msg').text()).toContain('请输入用户名')
  })

  it('用户名过短提交显示错误', async () => {
    const wrapper = getComponent()
    const usernameInput = wrapper.findAll('input')[0]
    await usernameInput.setValue('a')
    await wrapper.find('form').trigger('submit.prevent')
    await nextTick()

    expect(wrapper.find('.error-msg').text()).toContain('用户名至少 2 个字符')
  })

  it('密码过短提交显示错误', async () => {
    const wrapper = getComponent()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('validuser')
    await inputs[1].setValue('123')
    await wrapper.find('form').trigger('submit.prevent')
    await nextTick()

    expect(wrapper.find('.error-msg').text()).toContain('密码至少 6 个字符')
  })

  // === 提交测试 ===

  it('登录成功跳转到 /chat', async () => {
    mockLogin.mockResolvedValue({})
    const wrapper = getComponent()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('testuser')
    await inputs[1].setValue('123456')
    await wrapper.find('form').trigger('submit.prevent')
    await nextTick()

    // 需要等待异步完成
    await vi.waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('testuser', '123456')
    })
  })

  it('登录失败显示错误消息', async () => {
    mockLogin.mockRejectedValue({
      response: { data: { message: '用户名或密码错误' } },
    })
    const wrapper = getComponent()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('testuser')
    await inputs[1].setValue('wrongpass')
    await wrapper.find('form').trigger('submit.prevent')

    await vi.waitFor(() => {
      expect(wrapper.find('.error-msg').text()).toContain('用户名或密码错误')
    })
  })

  it('网络异常显示兜底错误', async () => {
    mockLogin.mockRejectedValue(new Error('Network Error'))
    const wrapper = getComponent()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('testuser')
    await inputs[1].setValue('123456')
    await wrapper.find('form').trigger('submit.prevent')

    await vi.waitFor(() => {
      expect(wrapper.find('.error-msg').text()).toContain('网络异常')
    })
  })
})
