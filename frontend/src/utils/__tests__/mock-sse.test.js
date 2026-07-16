/**
 * Mock SSE 客户端测试
 * 验证 createMockFetch 返回的 mock fetch 函数能正确模拟各种场景
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  createMockFetch,
  createFullUpdateMockFetch,
  createAnswerOnlyMockFetch,
  createErrorMockFetch,
} from '../mock-sse'
import { recipeFixtures } from '@/fixtures/recipe'

describe('createMockFetch', () => {
  describe('Chat API 模拟', () => {
    it('POST /api/chat/sessions/{id}/messages 返回 SSE 流（fullUpdate）', async () => {
      const mockFetch = createFullUpdateMockFetch()
      const response = await mockFetch('/api/chat/sessions/501/messages', {
        method: 'POST',
        body: JSON.stringify({ content: '改成三人份并少放油' }),
      })

      expect(response.status).toBe(200)
      expect(response.headers.get('Content-Type')).toBe('text/event-stream')

      // 读取流内容
      const text = await readSSEStream(response)
      expect(text).toContain('event: token')
      expect(text).toContain('event: recipe_updated')
      expect(text).toContain('event: done')
    })

    it('POST /api/chat/sessions/{id}/messages 返回纯问答流（answerOnly）', async () => {
      const mockFetch = createAnswerOnlyMockFetch()
      const response = await mockFetch('/api/chat/sessions/501/messages', {
        method: 'POST',
        body: JSON.stringify({ content: '怎么炒鸡蛋' }),
      })

      const text = await readSSEStream(response)
      expect(text).toContain('event: token')
      expect(text).toContain('event: done')
      expect(text).not.toContain('event: recipe_updated')
    })

    it('POST /api/chat/sessions/{id}/messages 返回错误流（error）', async () => {
      const mockFetch = createErrorMockFetch()
      const response = await mockFetch('/api/chat/sessions/501/messages', {
        method: 'POST',
        body: JSON.stringify({ content: '测试' }),
      })

      const text = await readSSEStream(response)
      expect(text).toContain('event: error')
      expect(text).toContain('LLM_UNAVAILABLE')
    })

    it('POST /api/chat/sessions 返回会话创建响应', async () => {
      const mockFetch = createFullUpdateMockFetch()
      const response = await mockFetch('/api/chat/sessions', {
        method: 'POST',
        body: JSON.stringify({ recipe_id: 101 }),
      })

      expect(response.status).toBe(201)
      const data = await response.json()
      expect(data.data.session_id).toBe(501)
      expect(data.data.recipe_id).toBe(101)
    })

    it('记录消息调用次数', async () => {
      const mockFetch = createFullUpdateMockFetch()
      expect(mockFetch.getMessageCallCount()).toBe(0)

      await mockFetch('/api/chat/sessions/501/messages', { method: 'POST' })
      expect(mockFetch.getMessageCallCount()).toBe(1)

      await mockFetch('/api/chat/sessions/501/messages', { method: 'POST' })
      expect(mockFetch.getMessageCallCount()).toBe(2)
    })
  })

  describe('Recipe API 模拟', () => {
    it('POST /api/recipes 返回菜谱数据（success）', async () => {
      const mockFetch = createFullUpdateMockFetch()
      const response = await mockFetch('/api/recipes', {
        method: 'POST',
        body: JSON.stringify({ recognition_id: 12 }),
      })

      expect(response.status).toBe(201)
      const data = await response.json()
      expect(data.data.title).toBe(recipeFixtures.success.title)
      expect(data.data.version).toBe(1)
    })

    it('GET /api/recipes/{id} 返回菜谱数据（success）', async () => {
      const mockFetch = createFullUpdateMockFetch()
      const response = await mockFetch('/api/recipes/101', { method: 'GET' })

      expect(response.status).toBe(200)
      const data = await response.json()
      expect(data.data.recipe_id).toBe(101)
      expect(data.data.title).toBe('番茄炒蛋')
    })

    it('fullUpdate 场景：发送消息后 GET recipe 返回 version=2', async () => {
      const mockFetch = createFullUpdateMockFetch()

      // 初始 GET 返回 v1
      const res1 = await mockFetch('/api/recipes/101', { method: 'GET' })
      const data1 = await res1.json()
      expect(data1.data.version).toBe(1)
      expect(data1.data.title).toBe('番茄炒蛋')

      // 发送修改消息（触发 recipe_updated）
      await mockFetch('/api/chat/sessions/501/messages', { method: 'POST' })

      // 后续 GET 返回 v2
      const res2 = await mockFetch('/api/recipes/101', { method: 'GET' })
      const data2 = await res2.json()
      expect(data2.data.version).toBe(2)
      expect(data2.data.title).toBe('少油版番茄炒蛋')
    })

    it('answerOnly 场景：发送消息后 GET recipe 仍返回 v1', async () => {
      const mockFetch = createAnswerOnlyMockFetch()

      // 初始 GET 返回 v1
      const res1 = await mockFetch('/api/recipes/101', { method: 'GET' })
      const data1 = await res1.json()
      expect(data1.data.version).toBe(1)

      // 发送纯问答消息（不触发 recipe_updated）
      await mockFetch('/api/chat/sessions/501/messages', { method: 'POST' })

      // 后续 GET 仍返回 v1
      const res2 = await mockFetch('/api/recipes/101', { method: 'GET' })
      const data2 = await res2.json()
      expect(data2.data.version).toBe(1)
      expect(data2.data.title).toBe('番茄炒蛋')
    })

    it('getCurrentRecipeScenario 正确反映场景状态', async () => {
      const mockFetch = createFullUpdateMockFetch()
      expect(mockFetch.getCurrentRecipeScenario()).toBe('success')

      // 发送修改消息
      await mockFetch('/api/chat/sessions/501/messages', { method: 'POST' })
      expect(mockFetch.getCurrentRecipeScenario()).toBe('v2')
    })
  })

  describe('会话列表', () => {
    it('GET /api/chat/sessions 返回空列表', async () => {
      const mockFetch = createFullUpdateMockFetch()
      const response = await mockFetch('/api/chat/sessions', { method: 'GET' })

      expect(response.status).toBe(200)
      const data = await response.json()
      expect(data.data.items).toEqual([])
      expect(data.data.total).toBe(0)
    })
  })

  describe('默认处理', () => {
    it('未知 URL 返回 404', async () => {
      const mockFetch = createFullUpdateMockFetch()
      const response = await mockFetch('/api/unknown', { method: 'GET' })

      expect(response.status).toBe(404)
    })
  })
})

/**
 * 辅助函数：读取 SSE 响应流内容
 */
async function readSSEStream(response) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let result = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    result += decoder.decode(value, { stream: true })
  }
  return result
}
