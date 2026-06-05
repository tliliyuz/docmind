/** Markdown 渲染工具测试 — ROADMAP §5.5 */
import { describe, it, expect } from 'vitest'
import { renderMarkdown, wrapCodeBlocks } from '@/utils/markdown'

describe('renderMarkdown', () => {
  it('空文本返回空字符串', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
    expect(renderMarkdown(undefined)).toBe('')
  })

  it('基本 Markdown 渲染为 HTML', () => {
    const html = renderMarkdown('**粗体**')
    expect(html).toContain('<strong>粗体</strong>')
  })

  it('代码块使用 highlight.js 高亮', () => {
    const html = renderMarkdown('```javascript\nconst x = 1;\n```')
    // highlight.js 会添加 hljs 相关 class 和语言标注
    expect(html).toContain('hljs')
    expect(html).toContain('language-javascript')
  })

  it('自动识别裸链接并转为可点击', () => {
    const html = renderMarkdown('访问 https://example.com 了解更多')
    // linkify: true — 裸链接应被包裹为 <a>
    expect(html).toContain('href="https://example.com"')
  })

  it('禁用 raw HTML 防 XSS', () => {
    const html = renderMarkdown('<script>alert("xss")</script>')
    // html: false 配置下 raw HTML 被转义
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })

  it('换行符转换为 <br>', () => {
    const html = renderMarkdown('第一行\n第二行')
    expect(html).toContain('<br>')
  })

  it('链接被正确渲染且在新标签页中行为由 markdown-it 默认处理', () => {
    const html = renderMarkdown('[文档](https://doc.com)')
    expect(html).toContain('href="https://doc.com"')
    expect(html).toContain('>文档</a>')
  })

  it('标题标签正确渲染', () => {
    const html = renderMarkdown('# 一级标题\n## 二级标题')
    expect(html).toContain('<h1>一级标题</h1>')
    expect(html).toContain('<h2>二级标题</h2>')
  })

  it('无语言标注的代码块使用 escapeHtml 处理', () => {
    const html = renderMarkdown('```\n普通文本\n```')
    // <code> 应该被 escapeHtml 保护
    expect(html).toContain('<code>')
  })
})

describe('wrapCodeBlocks', () => {
  it('包装 <pre><code> 块为 code-block-wrapper', () => {
    const input = '<pre><code class="hljs">console.log("ok")</code></pre>'
    const result = wrapCodeBlocks(input)
    expect(result).toContain('<div class="code-block-wrapper">')
    expect(result).toContain('<button class="code-copy-btn"')
    expect(result).toContain('<pre><code class="hljs">console.log("ok")</code></pre>')
    expect(result).toContain('</div>')
  })

  it('复制按钮含 fa-copy 和 fa-check 图标（不含内联 onclick，改为事件委托）', () => {
    const input = '<pre><code>hello</code></pre>'
    const result = wrapCodeBlocks(input)
    expect(result).toContain('fa-copy')
    expect(result).toContain('fa-check')
    // M4: 内联 onclick 已移除，复制逻辑改为 MessageItem 事件委托
    expect(result).not.toContain('navigator.clipboard.writeText')
  })

  it('无代码块时不修改 HTML', () => {
    const input = '<p>普通段落</p><h1>标题</h1>'
    const result = wrapCodeBlocks(input)
    expect(result).toBe(input)
  })

  it('多个代码块各被包装', () => {
    const input = '<pre><code>a</code></pre><p>text</p><pre><code>b</code></pre>'
    const result = wrapCodeBlocks(input)
    // 应包含两个 wrapper div（匹配 div 标签而非 onclick 中的引用）
    const matches = result.match(/<div class="code-block-wrapper">/g)
    expect(matches).toHaveLength(2)
  })

  it('保留 code 标签内的属性（如 class="hljs"）', () => {
    const input = '<pre><code class="hljs language-python">print(1)</code></pre>'
    const result = wrapCodeBlocks(input)
    expect(result).toContain('class="hljs language-python"')
    expect(result).toContain('print(1)')
  })
})
