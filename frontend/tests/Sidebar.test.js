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

import Sidebar from '@/components/layout/Sidebar.vue'

function mountSidebar() {
  return mount(Sidebar, {
    global: {
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

  it('点击退出按钮调用 logout', async () => {
    mockLogout.mockResolvedValue(undefined)
    const wrapper = mountSidebar()
    const logoutBtn = wrapper.find('.logout-btn')
    await logoutBtn.trigger('click')
    await flushPromises()

    expect(mockLogout).toHaveBeenCalled()
    expect(mockMsgSuccess).toHaveBeenCalledWith('已退出登录')
    expect(mockPush).toHaveBeenCalledWith('/login')
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
})
