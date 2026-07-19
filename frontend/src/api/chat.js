import request from '@/utils/request'
import { streamChat } from '@/utils/stream'

export const CHAT_PATHS = Object.freeze({
  sessions: '/chat/sessions',
  sessionMessages: (sessionId) => `/chat/sessions/${sessionId}/messages`,
  messages: (sessionId) => `/chat/sessions/${sessionId}/messages`,
})

export function createChatSession(recipeId) {
  return request.post(CHAT_PATHS.sessions, { recipe_id: recipeId })
}

export function getChatSessions(recipeId) {
  return request.get(CHAT_PATHS.sessions, { params: { recipe_id: recipeId } })
}

export function getChatMessages(sessionId) {
  return request.get(CHAT_PATHS.sessionMessages(sessionId))
}

export function sendChatMessage(sessionId, content, callbacks = {}) {
  return streamChat(
    `/api${CHAT_PATHS.messages(sessionId)}`,
    { content },
    callbacks,
  )
}
