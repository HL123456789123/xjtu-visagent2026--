import { afterEach, describe, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import {
  CHAT_PATHS,
  createChatSession,
  createSessionApi,
  sendChatMessage,
} from '../chat'

// Mock streamChat to avoid real fetch calls
vi.mock('@/utils/stream', () => ({
  streamChat: vi.fn(() => () => {}),
}))

describe('chat api contract (V1)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps the V1 frozen chat paths', () => {
    expect(CHAT_PATHS.sessions).toBe('/chat/sessions')
    expect(CHAT_PATHS.session(501)).toBe('/chat/sessions/501')
    expect(CHAT_PATHS.messages(501)).toBe('/chat/sessions/501/messages')
  })

  it('createChatSession sends only recipe_id in request body', async () => {
    const postSpy = vi.spyOn(request, 'post').mockResolvedValue({
      code: 201,
      message: '会话创建成功',
      data: {
        session_id: 501,
        recipe_id: 101,
        created_at: '2026-07-14T21:45:00+08:00',
      },
    })

    const result = await createChatSession(101)

    expect(postSpy).toHaveBeenCalledOnce()
    const [path, body] = postSpy.mock.calls[0]

    expect(path).toBe(CHAT_PATHS.sessions)
    // V1: 请求体只传 recipe_id
    expect(body).toEqual({ recipe_id: 101 })
    expect(result.data.session_id).toBe(501)
    expect(result.data.recipe_id).toBe(101)
  })

  it('createChatSession does not send title or other fields', async () => {
    const postSpy = vi.spyOn(request, 'post').mockResolvedValue({
      code: 201,
      data: { session_id: 502, recipe_id: 102 },
    })

    await createChatSession(102)

    const [, body] = postSpy.mock.calls[0]
    const keys = Object.keys(body)
    expect(keys).toEqual(['recipe_id'])
  })

  it('sendChatMessage calls streamChat with V1 content body and correct url', async () => {
    const { streamChat } = await import('@/utils/stream')
    const streamSpy = vi.mocked(streamChat)
    streamSpy.mockClear()

    const callbacks = {
      onToken: vi.fn(),
      onRecipeUpdated: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    }

    sendChatMessage(501, '把这道菜改成三人份', callbacks)

    expect(streamSpy).toHaveBeenCalledOnce()
    const [url, body, cb] = streamSpy.mock.calls[0]

    // URL 包含 /api 前缀和正确的路径
    expect(url).toBe('/api/chat/sessions/501/messages')
    // V1: 请求体只传 content
    expect(body).toEqual({ content: '把这道菜改成三人份' })
    // 回调函数传递
    expect(cb).toBe(callbacks)
  })

  it('legacy createSessionApi still works for backward compatibility', async () => {
    const postSpy = vi.spyOn(request, 'post').mockResolvedValue({
      code: 201,
      data: { session_id: 503 },
    })

    await createSessionApi({ title: '旧版对话' })

    const [path, body] = postSpy.mock.calls[0]
    expect(path).toBe(CHAT_PATHS.sessions)
    expect(body).toEqual({ title: '旧版对话' })
  })
})
