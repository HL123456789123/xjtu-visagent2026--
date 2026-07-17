import request from '@/utils/request'
import { streamChat } from '@/utils/stream'

export const CHAT_PATHS = Object.freeze({
  sessions: '/chat/sessions',
  messages: (sessionId) => `/chat/sessions/${sessionId}/messages`,
})

export function createChatSession(recipeId) {
  return request.post(CHAT_PATHS.sessions, { recipe_id: recipeId })
}

export function sendChatMessage(sessionId, content, callbacks = {}) {
  return streamChat(
    `/api${CHAT_PATHS.messages(sessionId)}`,
    { content },
    callbacks,
  )
}
