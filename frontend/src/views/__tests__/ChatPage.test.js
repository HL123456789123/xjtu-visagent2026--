import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatPage from '../ChatPage.vue'
import { createChatSession, sendChatMessage } from '@/api/chat'

vi.mock('@/api/chat', () => ({
  createChatSession: vi.fn(),
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
})
