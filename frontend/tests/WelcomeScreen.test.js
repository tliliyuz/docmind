/** WelcomeScreen 组件测试 — ROADMAP §5.5 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

import WelcomeScreen from '@/components/chat/WelcomeScreen.vue'

function getComponent() {
  return mount(WelcomeScreen, {
    global: {
      stubs: { 'i': { template: '<span class="icon" />', props: ['class'] } },
    },
  })
}

describe('WelcomeScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ==================== 渲染测试 ====================

  it('渲染欢迎标题', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.welcome-title').text()).toBe('我是 DocMind，你的企业知识助手')
  })

  it('渲染描述文字', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.welcome-desc').text()).toBe('选择一个知识库，开始提问吧')
  })

  it('渲染 4 个快捷问题卡片', () => {
    const wrapper = getComponent()
    const cards = wrapper.findAll('.quick-card')
    expect(cards).toHaveLength(4)
  })

  it('每个卡片包含图标和文字', () => {
    const wrapper = getComponent()
    const cards = wrapper.findAll('.quick-card')
    for (let i = 0; i < cards.length; i++) {
      expect(cards[i].find('.quick-card-icon').exists()).toBe(true)
      expect(cards[i].find('.quick-card-text').exists()).toBe(true)
      expect(cards[i].find('.quick-card-text').text()).toBeTruthy()
    }
  })

  it('快捷问题卡片显示预设问题', () => {
    const wrapper = getComponent()
    const cardTexts = wrapper.findAll('.quick-card-text').map(el => el.text())
    expect(cardTexts).toContain('报销流程是怎样的？')
    expect(cardTexts).toContain('入职需要准备什么？')
    expect(cardTexts).toContain('如何申请年假？')
    expect(cardTexts).toContain('VPN 怎么配置？')
  })

  // ==================== 交互测试 ====================

  it('点击快捷问题卡片 emit select 事件', async () => {
    const wrapper = getComponent()
    const firstCard = wrapper.findAll('.quick-card')[0]
    await firstCard.trigger('click')

    const expectedText = wrapper.findAll('.quick-card-text')[0].text()
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0][0]).toBe(expectedText)
  })

  it('不同卡片 emit 不同问题文本', async () => {
    const wrapper = getComponent()
    const cards = wrapper.findAll('.quick-card')

    await cards[1].trigger('click')
    expect(wrapper.emitted('select')[0][0]).toBe('入职需要准备什么？')

    await cards[2].trigger('click')
    expect(wrapper.emitted('select')[1][0]).toBe('如何申请年假？')
  })

  it('所有快捷问题卡片均可点击', async () => {
    const wrapper = getComponent()
    const cards = wrapper.findAll('.quick-card')

    for (let i = 0; i < cards.length; i++) {
      await cards[i].trigger('click')
    }

    expect(wrapper.emitted('select')).toHaveLength(4)
  })
})
