/**
 * Markdown 渲染工具
 *
 * 基于 markdown-it + highlight.js 实现：
 * - 代码块语法高亮（highlight.js）
 * - XSS 防护（禁用 raw HTML）
 * - 一键复制支持（通过 wrapCodeWithCopy 辅助函数）
 */

import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

// 创建 markdown-it 实例
const md = new MarkdownIt({
  html: false, // 禁用 raw HTML，防止 XSS
  linkify: true, // 自动识别链接
  typographer: false,
  breaks: true, // 换行符转 <br>
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        const result = hljs.highlight(str, { language: lang, ignoreIllegals: true })
        return result.value
      } catch {
        // 高亮失败时降级
      }
    }
    // 无语言指定或高亮失败时，使用 autoDetect
    return md.utils.escapeHtml(str)
  },
})

/**
 * 渲染 Markdown 文本为 HTML
 * @param {string} text - Markdown 文本
 * @returns {string} 渲染后的 HTML
 */
export function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text)
}

/**
 * 生成带复制按钮的代码块包装 HTML
 * 用于在 MessageItem 组件中给 <pre><code> 块添加复制按钮
 *
 * 使用方式：在 MessageItem 中将渲染后的 HTML 通过此函数处理
 * @param {string} html - 渲染后的 HTML
 * @returns {string} 包装后的 HTML
 */
export function wrapCodeBlocks(html) {
  // 匹配 <pre><code...>...</code></pre>，添加复制按钮
  return html.replace(
    /<pre><code(.*?)>([\s\S]*?)<\/code><\/pre>/g,
    (match, attrs, code) => {
      return `<div class="code-block-wrapper">
        <button class="code-copy-btn" title="复制代码">
          <i class="fas fa-copy"></i>
          <i class="fas fa-check"></i>
        </button>
        <pre><code${attrs}>${code}</code></pre>
      </div>`
    }
  )
}

export default md
