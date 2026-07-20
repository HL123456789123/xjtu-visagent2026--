import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatPage from '../ChatPage.vue'
import {
  createChatSession,
  getChatMessages,
  getChatSessions,
  sendChatMessage,
} from '@/api/chat'

vi.mock('@/api/chat', () => ({
  createChatSession: vi.fn(),
  getChatMessages: vi.fn(),
  getChatSessions: vi.fn(),
  sendChatMessage: vi.fn(),
}))

async function mountChat() {
  const wrapper = mount(ChatPage, { props: { recipeId: 101 } })
  await flushPromises()
  return wrapper
}

describe('ChatPage V1 boundary', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createChatSession.mockResolvedValue({
      data: { session_id: 501, recipe_id: 101 },
    })
    getChatSessions.mockResolvedValue({ data: [] })
    getChatMessages.mockResolvedValue({ data: [] })
  })

  it('sends only content and does not refresh a recipe for an answer', async () => {
    sendChatMessage.mockImplementation((_sessionId, _content, callbacks) => {
      callbacks.onToken({ content: 'Use medium heat.' })
      callbacks.onDone({ message_id: 9001 })
      return vi.fn()
    })
    const wrapper = await mountChat()

    await wrapper.find('[data-testid="chat-input"]').setValue('How should I cook it?')
    await wrapper.find('[data-testid="chat-send"]').trigger('submit')
    await flushPromises()

    expect(createChatSession).toHaveBeenCalledWith(101)
    expect(sendChatMessage.mock.calls[0][0]).toBe(501)
    expect(sendChatMessage.mock.calls[0][1]).toBe('How should I cook it?')
    expect(wrapper.text()).toContain('Use medium heat.')
    expect(wrapper.emitted('recipe-updated')).toBeUndefined()
  })

  it('forwards only an explicit recipe_updated event to the parent', async () => {
    sendChatMessage.mockImplementation((_sessionId, _content, callbacks) => {
      callbacks.onRecipeUpdated({ recipe_id: 101, version: 2 })
      callbacks.onDone({ message_id: 9002 })
      return vi.fn()
    })
    const wrapper = await mountChat()

    await wrapper.find('[data-testid="chat-input"]').setValue('Make it serve three.')
    await wrapper.find('[data-testid="chat-send"]').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('recipe-updated')).toEqual([[
      { recipe_id: 101, version: 2 },
    ]])
  })

  it('restores the newest existing session and never creates a duplicate', async () => {
    getChatSessions.mockResolvedValue({
      data: [{ session_id: 801, recipe_id: 101, title: '已有会话', message_count: 2 }],
    })
    getChatMessages.mockResolvedValue({
      data: [
        { message_id: 1, role: 'user', content: '旧问题' },
        { message_id: 2, role: 'assistant', content: '旧回答', recipe_version: 2 },
      ],
    })

    const wrapper = await mountChat()

    expect(getChatSessions).toHaveBeenCalledWith(101)
    expect(getChatMessages).toHaveBeenCalledWith(801)
    expect(createChatSession).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('旧问题')
    expect(wrapper.text()).toContain('旧回答')
    expect(wrapper.text()).toContain('查看本次生成的 v2 菜谱')
  })
})
