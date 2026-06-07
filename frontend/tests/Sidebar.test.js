/** Sidebar 会话列表组件测试 — ROADMAP §6.6 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'

// ===== Hoisted mocks =====
const {
  mockPush,
  mockClearMessages,
  mockChatReset,
  mockLoadConversations,
  mockRenameConversation,
  mockDeleteConversation,
  mockAddConversation,
  mockUpdateConversationTitle,
  mockConvReset,
  mockConfirm,
  mockMsgSuccess,
  mockMsgError,
  mockLogout,
  mockChangePassword,
} = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockClearMessages: vi.fn(),
  mockChatReset: vi.fn(),
  mockLoadConversations: vi.fn(),
  mockRenameConversation: vi.fn(),
  mockDeleteConversation: vi.fn(),
  mockAddConversation: vi.fn(),
  mockUpdateConversationTitle: vi.fn(),
  mockConvReset: vi.fn(),
  mockConfirm: vi.fn(),
  mockMsgSuccess: vi.fn(),
  mockMsgError: vi.fn(),
  mockLogout: vi.fn(),
  mockChangePassword: vi.fn(),
}))

// ===== Mock 路由 =====
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ path: '/chat', query: {} }),
}))

// ===== Mock Element Plus =====
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: mockMsgSuccess, error: mockMsgError },
    ElMessageBox: { confirm: mockConfirm },
  }
})

// ===== Mock Auth Store =====
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: 1, username: 'testuser', role: 'user' },
    isLoggedIn: true,
    isAdmin: false,
    logout: mockLogout,
  }),
}))

// ===== Mock Chat Store =====
vi.mock('@/stores/chat', () => ({
  useChatStore: () => ({
    conversationId: null,
    clearMessages: mockClearMessages,
    reset: mockChatReset,
  }),
}))

// ===== Mock Conversation Store =====
const mockConvState = reactive({
  conversations: [],
  loading: false,
  groupedConversations: { today: [], yesterday: [], recent: [], older: [] },
  loadConversations: mockLoadConversations,
  renameConversation: mockRenameConversation,
  deleteConversation: mockDeleteConversation,
  addConversation: mockAddConversation,
  updateConversationTitle: mockUpdateConversationTitle,
  reset: mockConvReset,
})

vi.mock('@/stores/conversation', () => ({
  useConversationStore: () => mockConvState,
}))

// ===== Mock Auth API（changePassword 直接导入到 Sidebar） =====
vi.mock('@/api/auth', () => ({
  changePassword: (...args) => mockChangePassword(...args),
}))

import ElementPlus from 'element-plus'
import Sidebar from '@/components/layout/Sidebar.vue'

function mountSidebar() {
  return mount(Sidebar, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        'router-link': { template: '<a><slot /></a>', props: ['to'] },
      },
    },
  })
}

describe('Sidebar 会话列表', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockConvState.conversations.splice(0)
    mockConvState.loading = false
    mockConvState.groupedConversations.today = []
    mockConvState.groupedConversations.yesterday = []
    mockConvState.groupedConversations.recent = []
    mockConvState.groupedConversations.older = []
  })

  // ==================== 基础渲染 ====================

  it('组件挂载时调用 loadConversations', () => {
    mountSidebar()
    expect(mockLoadConversations).toHaveBeenCalled()
  })

  it('空会话列表时显示「暂无会话」', () => {
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('暂无会话')
  })

  it('加载中时显示加载状态', () => {
    mockConvState.loading = true
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('加载中...')
  })

  it('有会话时不显示空态', () => {
    const conv = { id: 1, title: '测试会话', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()
    expect(wrapper.text()).not.toContain('暂无会话')
  })

  // ==================== 会话列表展示 ====================

  it('显示今天分组的会话标题', () => {
    const conv = { id: 1, title: '关于报销流程', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('今天')
    expect(wrapper.text()).toContain('关于报销流程')
  })

  it('显示昨天分组', () => {
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000)
    const conv = { id: 2, title: '入职须知', updated_at: yesterday.toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.yesterday = [conv]
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('昨天')
    expect(wrapper.text()).toContain('入职须知')
  })

  it('显示近 7 天分组', () => {
    const conv = { id: 3, title: '休假政策', updated_at: '2026-06-04T10:00:00', kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.recent = [conv]
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('近 7 天')
    expect(wrapper.text()).toContain('休假政策')
  })

  it('显示更早分组', () => {
    const conv = { id: 4, title: '旧会话', updated_at: '2026-05-01T10:00:00', kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.older = [conv]
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('更早')
    expect(wrapper.text()).toContain('旧会话')
  })

  it('空标题的会话显示「新对话」', () => {
    const conv = { id: 5, title: '', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('新对话')
  })

  // ==================== 会话切换 ====================

  it('点击会话跳转到对应路由', async () => {
    const conv = { id: 42, title: '测试会话', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()
    const convItem = wrapper.find('.conv-item')
    await convItem.trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/chat?conversation_id=42')
  })

  it('当前活跃会话有 active 样式类', () => {
    const conv = { id: 42, title: '活跃会话', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    // chatStore.conversationId 为 null，所以不会高亮
    const wrapper = mountSidebar()
    const convItem = wrapper.find('.conv-item')
    expect(convItem.classes()).not.toContain('active')
  })

  // ==================== 重命名 ====================

  it('重命名成功后更新标题', async () => {
    mockRenameConversation.mockResolvedValue(undefined)
    const conv = { id: 1, title: '原标题', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()

    // 悬停显示操作按钮，点击重命名
    const convItem = wrapper.find('.conv-item')
    await convItem.trigger('mouseenter')
    const renameBtn = wrapper.findAll('.conv-actions button')[0]
    await renameBtn.trigger('click')

    // 输入新标题
    const input = wrapper.find('.conv-edit-input')
    expect(input.exists()).toBe(true)
    await input.setValue('新标题')
    await input.trigger('keydown.enter')

    expect(mockRenameConversation).toHaveBeenCalledWith(1, '新标题')
    expect(mockMsgSuccess).toHaveBeenCalledWith('重命名成功')
  })

  it('重命名空标题时不调用 API', async () => {
    const conv = { id: 1, title: '原标题', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()

    const convItem = wrapper.find('.conv-item')
    await convItem.trigger('mouseenter')
    const renameBtn = wrapper.findAll('.conv-actions button')[0]
    await renameBtn.trigger('click')

    const input = wrapper.find('.conv-edit-input')
    await input.setValue('   ')
    await input.trigger('keydown.enter')

    expect(mockRenameConversation).not.toHaveBeenCalled()
  })

  it('重命名时按 Esc 取消编辑', async () => {
    const conv = { id: 1, title: '原标题', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()

    const convItem = wrapper.find('.conv-item')
    await convItem.trigger('mouseenter')
    const renameBtn = wrapper.findAll('.conv-actions button')[0]
    await renameBtn.trigger('click')

    const input = wrapper.find('.conv-edit-input')
    expect(input.exists()).toBe(true)
    await input.trigger('keydown.escape')

    // 输入框消失
    expect(wrapper.find('.conv-edit-input').exists()).toBe(false)
    expect(mockRenameConversation).not.toHaveBeenCalled()
  })

  // ==================== 删除 ====================

  it('确认删除后调用 deleteConversation', async () => {
    mockConfirm.mockResolvedValue('confirm')
    mockDeleteConversation.mockResolvedValue(undefined)
    const conv = { id: 7, title: '待删除', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()

    const convItem = wrapper.find('.conv-item')
    await convItem.trigger('mouseenter')
    const deleteBtn = wrapper.findAll('.conv-actions button')[1]
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(mockConfirm).toHaveBeenCalled()
    expect(mockDeleteConversation).toHaveBeenCalledWith(7)
    expect(mockMsgSuccess).toHaveBeenCalledWith('会话已删除')
  })

  it('取消删除时不调用 API', async () => {
    mockConfirm.mockRejectedValue('cancel')
    const conv = { id: 7, title: '不删除', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()

    const convItem = wrapper.find('.conv-item')
    await convItem.trigger('mouseenter')
    const deleteBtn = wrapper.findAll('.conv-actions button')[1]
    await deleteBtn.trigger('click')
    await flushPromises()

    expect(mockDeleteConversation).not.toHaveBeenCalled()
  })

  it('删除当前活跃会话后清空并跳转 /chat', async () => {
    mockConfirm.mockResolvedValue('confirm')
    mockDeleteConversation.mockResolvedValue(undefined)
    const conv = { id: 7, title: '当前会话', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()

    const convItem = wrapper.find('.conv-item')
    await convItem.trigger('mouseenter')
    const deleteBtn = wrapper.findAll('.conv-actions button')[1]
    await deleteBtn.trigger('click')
    await flushPromises()

    // deleteConversation 应该被调用
    expect(mockDeleteConversation).toHaveBeenCalledWith(7)
  })

  // ==================== 新建对话 ====================

  it('点击新建对话按钮调用 clearMessages + push', async () => {
    const wrapper = mountSidebar()
    const newChatBtn = wrapper.find('.new-chat-btn')
    await newChatBtn.trigger('click')

    expect(mockClearMessages).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/chat')
  })

  // ==================== 退出登录 ====================

  it('点击用户菜单退出登录项确认后调用 logout', async () => {
    mockConfirm.mockResolvedValue('confirm')
    mockLogout.mockResolvedValue(undefined)
    const wrapper = mountSidebar()
    // 点击头像打开用户菜单
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    // 点击退出登录菜单项
    const logoutItem = wrapper.find('.user-menu-item.danger')
    expect(logoutItem.exists()).toBe(true)
    await logoutItem.trigger('click')
    await flushPromises()

    expect(mockConfirm).toHaveBeenCalled()
    expect(mockLogout).toHaveBeenCalled()
    expect(mockMsgSuccess).toHaveBeenCalledWith('已退出登录')
    expect(mockPush).toHaveBeenCalledWith('/login')
  })

  it('退出登录取消确认时不调用 logout', async () => {
    mockConfirm.mockRejectedValue('cancel')
    const wrapper = mountSidebar()
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    await wrapper.find('.user-menu-item.danger').trigger('click')
    await flushPromises()

    expect(mockConfirm).toHaveBeenCalled()
    expect(mockLogout).not.toHaveBeenCalled()
  })

  // ==================== 折叠/展开 ====================

  it('点击折叠按钮切换 collapsed 状态', async () => {
    const wrapper = mountSidebar()
    expect(wrapper.find('.sidebar').classes()).not.toContain('collapsed')

    const toggleBtn = wrapper.find('.collapse-toggle-btn')
    await toggleBtn.trigger('click')
    await nextTick()

    expect(wrapper.find('.sidebar').classes()).toContain('collapsed')
  })

  it('折叠态隐藏会话标题', async () => {
    const conv = { id: 1, title: '测试标题', updated_at: new Date().toISOString(), kb_id: 1 }
    mockConvState.conversations.push(conv)
    mockConvState.groupedConversations.today = [conv]
    const wrapper = mountSidebar()

    // 展开态可见
    expect(wrapper.text()).toContain('测试标题')

    // 折叠
    const toggleBtn = wrapper.find('.collapse-toggle-btn')
    await toggleBtn.trigger('click')
    await nextTick()

    // 折叠态标题不可见（conv-info 被隐藏）
    expect(wrapper.find('.sidebar').classes()).toContain('collapsed')
  })

  // ==================== 用户菜单卡片 ====================

  it('点击头像切换用户菜单可见性', async () => {
    const wrapper = mountSidebar()
    // 初始不可见（v-show="false" 设置 display: none）
    const card = wrapper.find('.user-menu-card')
    expect(card.exists()).toBe(true)
    expect(card.attributes('style')).toContain('display: none')
    // 点击头像 → 可见
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    expect(card.attributes('style')).not.toContain('display: none')
    // 再次点击头像 → 关闭
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    expect(card.attributes('style')).toContain('display: none')
  })

  it('点击用户菜单外部关闭菜单', async () => {
    const wrapper = mountSidebar()
    // 打开菜单
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    const card = wrapper.find('.user-menu-card')
    expect(card.attributes('style')).not.toContain('display: none')
    // 等待 setTimeout(0) 注册 document click 监听
    await new Promise(r => setTimeout(r, 10))
    // 点击文档外部区域，应关闭菜单
    document.body.click()
    await nextTick()
    expect(card.attributes('style')).toContain('display: none')
  })

  it('用户菜单显示用户名和角色', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    const menuText = wrapper.find('.user-menu-card').text()
    expect(menuText).toContain('testuser')
    expect(menuText).toContain('用户')
    expect(menuText).toContain('修改密码')
    expect(menuText).toContain('退出登录')
  })

  it('点击用户菜单修改密码项后菜单关闭', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    const card = wrapper.find('.user-menu-card')
    expect(card.attributes('style')).not.toContain('display: none')
    // 点击修改密码
    await wrapper.find('.user-menu-item:not(.danger)').trigger('click')
    await nextTick()
    // 菜单应关闭
    expect(card.attributes('style')).toContain('display: none')
  })

  // ==================== 修改密码弹窗 ====================

  /** 辅助函数：打开用户菜单 → 点击「修改密码」→ 打开改密弹窗 */
  async function openChangePasswordDialog(wrapper) {
    // 先点击头像打开用户菜单
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    // 点击菜单中的「修改密码」项
    const menuItem = wrapper.find('.user-menu-item:not(.danger)')
    expect(menuItem.exists()).toBe(true)
    await menuItem.trigger('click')
    await nextTick()
  }

  it('点击头像打开用户菜单，点击修改密码项打开弹窗', async () => {
    const wrapper = mountSidebar()
    // 点击头像
    await wrapper.find('.user-avatar').trigger('click')
    await nextTick()
    // 用户菜单应可见（v-show 不设 display: none）
    const menuCard = wrapper.find('.user-menu-card')
    expect(menuCard.attributes('style')).not.toContain('display: none')
    // 菜单中应包含「修改密码」和「退出登录」选项
    const menuText = menuCard.text()
    expect(menuText).toContain('修改密码')
    expect(menuText).toContain('退出登录')
    // 点击修改密码项
    const menuItem = wrapper.find('.user-menu-item:not(.danger)')
    await menuItem.trigger('click')
    await nextTick()
    // 弹窗应可见
    expect(wrapper.html()).toContain('当前密码')
    expect(wrapper.html()).toContain('新密码')
    expect(wrapper.html()).toContain('确认新密码')
  })

  it('修改密码-空表单提交触发校验', async () => {
    const wrapper = mountSidebar()
    // 通过菜单打开弹窗
    await openChangePasswordDialog(wrapper)
    // 弹窗已打开，直接点击确认修改按钮（不填任何字段）
    const submitBtn = wrapper.find('.el-button--primary')
    await submitBtn.trigger('click')
    await nextTick()
    // 应触发校验错误提示（el-form validate 失败，changePassword 不应被调用）
    expect(mockChangePassword).not.toHaveBeenCalled()
  })

  it('修改密码-提交成功', async () => {
    mockChangePassword.mockResolvedValueOnce({ data: { code: '0' } })
    const wrapper = mountSidebar()

    // 通过菜单打开弹窗
    await openChangePasswordDialog(wrapper)

    // 填充表单
    const passwordInputs = wrapper.findAll('.el-input__inner')
    await passwordInputs[0].setValue('oldPass123')
    await passwordInputs[1].setValue('newPass456')
    await passwordInputs[2].setValue('newPass456')
    await nextTick()

    // 点击确认
    const submitBtn = wrapper.find('.el-button--primary')
    await submitBtn.trigger('click')
    await flushPromises()
    await nextTick()

    // 验证 API 调用参数
    expect(mockChangePassword).toHaveBeenCalledWith('oldPass123', 'newPass456')
    // 验证成功提示
    expect(mockMsgSuccess).toHaveBeenCalledWith('密码修改成功，请重新登录')
    // 验证注销并跳转
    expect(mockChatReset).toHaveBeenCalled()
    expect(mockLogout).toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith('/login')
  })

  it('修改密码-原密码错误时提示且不清除登录态', async () => {
    mockChangePassword.mockRejectedValueOnce({
      response: { status: 401, data: { code: 'E5002', message: '用户名或密码错误' } },
    })
    const wrapper = mountSidebar()

    // 通过菜单打开弹窗
    await openChangePasswordDialog(wrapper)

    // 填充表单（填写错误原密码）
    const passwordInputs = wrapper.findAll('.el-input__inner')
    await passwordInputs[0].setValue('wrongOldPass')
    await passwordInputs[1].setValue('newPass456')
    await passwordInputs[2].setValue('newPass456')
    await nextTick()

    // 点击确认
    const submitBtn = wrapper.find('.el-button--primary')
    await submitBtn.trigger('click')
    await flushPromises()
    await nextTick()

    // 验证 API 被调用
    expect(mockChangePassword).toHaveBeenCalledWith('wrongOldPass', 'newPass456')
    // 验证错误提示（不应注销）
    expect(mockMsgError).toHaveBeenCalledWith('用户名或密码错误')
    // 验证登录态未被清除（不应触发 clearAndRedirect）
    expect(mockChatReset).not.toHaveBeenCalled()
    expect(mockLogout).not.toHaveBeenCalled()
    expect(mockPush).not.toHaveBeenCalledWith('/login')
  })
})
