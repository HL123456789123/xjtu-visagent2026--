/**
 * Markdown 渲染工具测试
 */
import { describe, it, expect } from 'vitest'
import { renderMarkdown } from '../markdown'

describe('renderMarkdown', () => {
  it('应该返回空字符串当输入为空', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
    expect(renderMarkdown(undefined)).toBe('')
  })

  it('应该渲染普通文本', () => {
    const result = renderMarkdown('Hello World')
    expect(result).toContain('Hello World')
    expect(result).toContain('<p>')
  })

  it('应该渲染标题', () => {
    const result = renderMarkdown('# 一级标题')
    expect(result).toContain('<h1>')
    expect(result).toContain('一级标题')
  })

  it('应该渲染二级标题', () => {
    const result = renderMarkdown('## 二级标题')
    expect(result).toContain('<h2>')
    expect(result).toContain('二级标题')
  })

  it('应该渲染粗体文本', () => {
    const result = renderMarkdown('**粗体文本**')
    expect(result).toContain('<strong>')
    expect(result).toContain('粗体文本')
  })

  it('应该渲染斜体文本', () => {
    const result = renderMarkdown('*斜体文本*')
    expect(result).toContain('<em>')
    expect(result).toContain('斜体文本')
  })

  it('应该渲染无序列表', () => {
    const result = renderMarkdown('- 项目1\n- 项目2\n- 项目3')
    expect(result).toContain('<ul>')
    expect(result).toContain('<li>')
    expect(result).toContain('项目1')
    expect(result).toContain('项目2')
    expect(result).toContain('项目3')
  })

  it('应该渲染有序列表', () => {
    const result = renderMarkdown('1. 第一项\n2. 第二项\n3. 第三项')
    expect(result).toContain('<ol>')
    expect(result).toContain('<li>')
    expect(result).toContain('第一项')
    expect(result).toContain('第二项')
    expect(result).toContain('第三项')
  })

  it('应该渲染链接', () => {
    const result = renderMarkdown('[链接文本](https://example.com)')
    expect(result).toContain('<a ')
    expect(result).toContain('href="https://example.com"')
    expect(result).toContain('链接文本')
  })

  it('应该渲染代码块', () => {
    const result = renderMarkdown('```\nconst a = 1;\n```')
    expect(result).toContain('<code>')
    expect(result).toContain('const a = 1;')
  })

  it('应该渲染行内代码', () => {
    const result = renderMarkdown('这是 `code` 文本')
    expect(result).toContain('<code>')
    expect(result).toContain('code')
  })

  it('应该渲染表格', () => {
    const table = '| 列1 | 列2 |\n| --- | --- |\n| 值1 | 值2 |'
    const result = renderMarkdown(table)
    expect(result).toContain('<table>')
    expect(result).toContain('<th>')
    expect(result).toContain('<td>')
    expect(result).toContain('列1')
    expect(result).toContain('值1')
  })

  it('应该渲染引用块', () => {
    const result = renderMarkdown('> 这是引用文本')
    expect(result).toContain('<blockquote>')
    expect(result).toContain('这是引用文本')
  })

  it('应该渲染水平线', () => {
    const result = renderMarkdown('---')
    expect(result).toContain('<hr>')
  })

  it('应该将换行符转换为 <br>', () => {
    const result = renderMarkdown('第一行\n第二行')
    expect(result).toContain('<br>')
  })

  it('应该禁用 HTML 标签', () => {
    const result = renderMarkdown('<script>alert("xss")</script>')
    expect(result).not.toContain('<script>')
    expect(result).toContain('&lt;script&gt;')
  })

  it('应该自动识别 URL', () => {
    const result = renderMarkdown('访问 https://example.com 获取更多信息')
    expect(result).toContain('<a ')
    expect(result).toContain('href="https://example.com"')
  })
})
