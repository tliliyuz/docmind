/** ConversationList 组件测试（活跃统计占位页） */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConversationList from '@/views/admin/ConversationList.vue'

function getComponent() {
  return mount(ConversationList, {
    global: {
      stubs: {
        'router-link': { template: '<a><slot /></a>', props: ['to'] },
      },
    },
  })
}

describe('ConversationList', () => {
  it('渲染页面标题"活跃统计"', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.detail-title').text()).toBe('活跃统计')
  })

  it('渲染页面描述', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.detail-desc').text()).toContain('用户活跃度')
  })

  it('渲染占位提示标题', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.empty-title').text()).toBe('用户活跃统计')
  })

  it('渲染占位提示描述', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.empty-desc').text()).toContain('后端接口排期至后续 Phase')
  })

  it('渲染计划展示的统计维度标题', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.preview-title').text()).toBe('计划展示的统计维度')
  })

  it('渲染全部 7 个维度卡片', () => {
    const wrapper = getComponent()
    const cards = wrapper.findAll('.dimension-card')
    expect(cards).toHaveLength(7)
  })

  it('维度卡片包含"用户"', () => {
    const wrapper = getComponent()
    const texts = wrapper.findAll('.dimension-card span').map(e => e.text())
    expect(texts).toContain('用户')
  })

  it('维度卡片包含"会话数"', () => {
    const wrapper = getComponent()
    const texts = wrapper.findAll('.dimension-card span').map(e => e.text())
    expect(texts).toContain('会话数')
  })

  it('维度卡片包含"提问数"', () => {
    const wrapper = getComponent()
    const texts = wrapper.findAll('.dimension-card span').map(e => e.text())
    expect(texts).toContain('提问数')
  })

  it('维度卡片包含"Token 消耗"', () => {
    const wrapper = getComponent()
    const texts = wrapper.findAll('.dimension-card span').map(e => e.text())
    expect(texts).toContain('Token 消耗')
  })

  it('维度卡片包含"最近访问"', () => {
    const wrapper = getComponent()
    const texts = wrapper.findAll('.dimension-card span').map(e => e.text())
    expect(texts).toContain('最近访问')
  })

  it('维度卡片包含"错误率"', () => {
    const wrapper = getComponent()
    const texts = wrapper.findAll('.dimension-card span').map(e => e.text())
    expect(texts).toContain('错误率')
  })

  it('维度卡片包含"KB 使用"', () => {
    const wrapper = getComponent()
    const texts = wrapper.findAll('.dimension-card span').map(e => e.text())
    expect(texts).toContain('KB 使用')
  })

  it('渲染数据表格预览标题', () => {
    const wrapper = getComponent()
    const titles = wrapper.findAll('.preview-title')
    expect(titles[1].text()).toBe('数据表格预览')
  })

  it('渲染预览表格（含 7 列表头）', () => {
    const wrapper = getComponent()
    const headers = wrapper.findAll('.preview-table th')
    expect(headers).toHaveLength(7)
  })

  it('预览表格表头依次为用户/会话数/提问数/Token消耗/最近访问/错误率/主要使用的KB', () => {
    const wrapper = getComponent()
    const headers = wrapper.findAll('.preview-table th')
    const texts = headers.map(h => h.text())
    expect(texts[0]).toBe('用户')
    expect(texts[1]).toBe('会话数')
    expect(texts[2]).toBe('提问数')
    expect(texts[3]).toBe('Token 消耗')
    expect(texts[4]).toBe('最近访问')
    expect(texts[5]).toBe('错误率')
    expect(texts[6]).toBe('主要使用的 KB')
  })

  it('占位行展示"数据加载后将在此显示用户活跃排行"', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.placeholder-row td').text()).toContain('数据加载后将在此显示用户活跃排行')
  })
})
