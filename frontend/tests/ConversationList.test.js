/** ConversationList 组件测试（admin 用户活跃统计页 — 占位页面）
 *
 * 当前组件为静态占位页面（后端接口排期至后续 Phase），
 * 仅验证占位状态和预期结构，不做逐字段静态文本校验。
 * 待后端接口实现后应替换为真实数据交互测试。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConversationList from '@/views/admin/ConversationList.vue'

function getComponent() {
  return mount(ConversationList)
}

describe('ConversationList（占位页面）', () => {
  it('展示占位状态，提示后端接口尚未实现', () => {
    const wrapper = getComponent()
    expect(wrapper.find('.empty-title').text()).toBe('用户活跃统计')
    expect(wrapper.find('.empty-desc').text()).toContain('后端接口排期至后续 Phase')
  })

  it('预览 7 个统计维度卡片', () => {
    const wrapper = getComponent()
    const cards = wrapper.findAll('.dimension-card span')
    expect(cards.map(e => e.text())).toEqual([
      '用户', '会话数', '提问数', 'Token 消耗', '最近访问', '错误率', 'KB 使用',
    ])
  })

  it('预览表格包含 7 列且表头顺序正确', () => {
    const wrapper = getComponent()
    const headers = wrapper.findAll('.preview-table th')
    expect(headers.map(h => h.text())).toEqual([
      '用户', '会话数', '提问数', 'Token 消耗', '最近访问', '错误率', '主要使用的 KB',
    ])
  })
})
