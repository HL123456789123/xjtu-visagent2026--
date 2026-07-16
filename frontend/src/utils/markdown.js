/**
 * Markdown 渲染工具
 *
 * Day11 对话页面中渲染 AI 返回的 Markdown 内容
 */
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

// 创建 markdown-it 实例（禁用 HTML 标签以保障安全）
const md = new MarkdownIt({
  html: false,        // 禁用 HTML 标签
  linkify: true,      // 自动识别 URL
  typographer: true,  // 智能排版
  breaks: true,       // \n 转换为 <br>
})

/**
 * 将 Markdown 文本渲染为 HTML（使用 DOMPurify 消毒防止 XSS）
 * @param {string} text - Markdown 文本
 * @returns {string} 安全的 HTML 字符串
 */
export function renderMarkdown(text) {
  if (!text) return ''
  const html = md.render(text)
  // 使用 DOMPurify 消毒，防止 XSS 攻击
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'blockquote', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td'],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'src', 'alt', 'class'],
  })
}

export default md
