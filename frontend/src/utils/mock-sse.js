/**
 * Mock SSE 客户端
 * 用于开发时模拟后端 SSE 流式响应，支持 Recipe + Chat 全链路测试
 *
 * 两种场景：
 *   - answerOnly: token → done（不触发 recipe_updated）
 *   - fullUpdate: token → recipe_updated → done（触发 recipe_updated）
 *   - error: error（模拟服务不可用）
 *
 * @module mock-sse
 */

import { recipeFixtures } from '@/fixtures/recipe'
import { sseFixtures } from '@/fixtures/sse'

/**
 * 将 SSE 文本块转换为 ReadableStream
 * @param {string} sseText - SSE 格式的文本
 * @param {number} [delayMs=80] - 每个 chunk 之间的延迟（毫秒）
 */
function createSSEStream(sseText, delayMs = 80) {
  // 按 \n\n 分割事件块
  const chunks = sseText.split('\n\n').filter(Boolean).map(c => c + '\n\n')

  return new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder()
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
        await new Promise(r => setTimeout(r, delayMs))
      }
      controller.close()
    }
  })
}

/**
 * 创建 Mock SSE Response
 * @param {string} sseText - SSE 文本
 * @param {number} [delayMs] - chunk 延迟
 */
function mockSSEResponse(sseText, delayMs = 80) {
  return new Response(createSSEStream(sseText, delayMs), {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  })
}

/**
 * 创建 Mock fetch 函数
 *
 * 根据请求 URL 和场景返回不同的 mock 响应：
 *   - POST /api/chat/sessions/{id}/messages → SSE 流
 *   - GET  /api/recipes/{id} → Recipe JSON
 *   - POST /api/chat/sessions → 创建会话响应
 *
 * @param {Object} options
 * @param {string} [options.chatScenario='fullUpdate'] - Chat 场景: 'fullUpdate' | 'answerOnly' | 'error'
 * @param {string} [options.recipeScenario='success'] - Recipe 场景: 'success' | 'v2'
 * @returns {Function} mockFetch
 */
export function createMockFetch({
  chatScenario = 'fullUpdate',
  recipeScenario = 'success',
} = {}) {
  // 内部状态：记录调用次数，用于判断首次/后续
  let messageCallCount = 0
  let currentRecipeScenario = recipeScenario

  function mockFetch(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase()
    const urlStr = typeof url === 'string' ? url : url.toString()

    // POST /api/chat/sessions/{id}/messages → SSE 流
    if (method === 'POST' && urlStr.match(/\/api\/chat\/sessions\/\d+\/messages/)) {
      messageCallCount++

      let sseText
      if (chatScenario === 'error') {
        sseText = sseFixtures.error
      } else if (chatScenario === 'answerOnly') {
        sseText = sseFixtures.answerOnly
      } else {
        // fullUpdate: 首次返回完整更新流
        sseText = sseFixtures.fullUpdate
        // 设置后续 recipe GET 返回 v2
        currentRecipeScenario = 'v2'
      }

      return Promise.resolve(mockSSEResponse(sseText))
    }

    // POST /api/chat/sessions → 创建会话
    if (method === 'POST' && urlStr.match(/\/api\/chat\/sessions$/) && !urlStr.includes('/messages')) {
      return Promise.resolve({
        ok: true,
        status: 201,
        json: () => Promise.resolve({
          code: 201,
          message: '会话创建成功',
          data: {
            session_id: 501,
            session_uuid: 'mock-uuid-501',
            recipe_id: 101,
            title: '对话修改菜谱',
            created_at: new Date().toISOString(),
          },
        }),
      })
    }

    // GET /api/recipes/{id} → Recipe JSON
    if (method === 'POST' && urlStr.match(/\/api\/recipes$/)) {
      return Promise.resolve({
        ok: true,
        status: 201,
        json: () => Promise.resolve({
          code: 201,
          message: '菜谱生成成功',
          data: currentRecipeScenario === 'v2'
            ? JSON.parse(JSON.stringify(recipeFixtures.v2))
            : JSON.parse(JSON.stringify(recipeFixtures.success)),
        }),
      })
    }

    // GET /api/recipes/{id}
    if (method === 'GET' && urlStr.match(/\/api\/recipes\/\d+$/)) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          code: 200,
          message: 'success',
          data: currentRecipeScenario === 'v2'
            ? JSON.parse(JSON.stringify(recipeFixtures.v2))
            : JSON.parse(JSON.stringify(recipeFixtures.success)),
        }),
      })
    }

    // GET /api/chat/sessions → 会话列表
    if (method === 'GET' && urlStr.match(/\/api\/chat\/sessions$/)) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({
          code: 200,
          message: 'success',
          data: {
            items: [],
            total: 0,
          },
        }),
      })
    }

    // 默认返回 404
    return Promise.resolve({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ code: 404, message: 'Not found' }),
    })
  }

  // 暴露状态查询方法
  mockFetch.getMessageCallCount = () => messageCallCount
  mockFetch.getCurrentRecipeScenario = () => currentRecipeScenario

  return mockFetch
}

/**
 * 快速创建全更新场景的 mock fetch
 * recipe_updated 触发后，后续 GET recipe 返回 version=2
 */
export function createFullUpdateMockFetch() {
  return createMockFetch({ chatScenario: 'fullUpdate', recipeScenario: 'success' })
}

/**
 * 快速创建纯问答场景的 mock fetch
 * 不会触发 recipe_updated
 */
export function createAnswerOnlyMockFetch() {
  return createMockFetch({ chatScenario: 'answerOnly', recipeScenario: 'success' })
}

/**
 * 快速创建错误场景的 mock fetch
 */
export function createErrorMockFetch() {
  return createMockFetch({ chatScenario: 'error', recipeScenario: 'success' })
}
