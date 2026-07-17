/**
 * 对话相关 API
 * 对应 api_v1.md 第八节 Chat API 与 SSE
 */
import request from '@/utils/request'
import { streamChat } from '@/utils/stream'

export const CHAT_PATHS = Object.freeze({
  sessions: '/chat/sessions',
  session: (sessionId) => `/chat/sessions/${sessionId}`,
  messages: (sessionId) => `/chat/sessions/${sessionId}/messages`,
})

/**
 * 创建对话会话（V1）
 * POST /api/chat/sessions
 * 请求体只传 recipe_id
 * @param {number} recipeId
 * @returns {Promise}
 */
export function createChatSession(recipeId) {
  return request.post(CHAT_PATHS.sessions, {
    recipe_id: recipeId,
  })
}

/**
 * 发送消息并接收 SSE 流式响应（V1）
 * POST /api/chat/sessions/{session_id}/messages
 * 请求体只传 content
 * Accept: text/event-stream
 *
 * @param {number} sessionId
 * @param {string} content
 * @param {Object} callbacks - { onToken, onRecipeUpdated, onDone, onError, onUnknown }
 * @returns {Function} stop - 调用以中止请求
 */
export function sendChatMessage(sessionId, content, callbacks = {}) {
  const url = `/api${CHAT_PATHS.messages(sessionId)}`
  return streamChat(
    url,
    { content },
    callbacks
  )
}

// ========== 以下为保留的兼容函数 ==========

/**
 * 创建对话会话（旧版，兼容）
 * @deprecated 请使用 createChatSession(recipeId)
 * @param {Object} data - { title }
 */
export function createSessionApi(data) {
  return request.post(CHAT_PATHS.sessions, data)
}

/**
 * 获取会话列表
 * @param {Object} params - { page, page_size }
 */
export function getSessionsApi(params) {
  return request.get(CHAT_PATHS.sessions, { params })
}

/**
 * 获取对话历史
 * @param {number} sessionId
 * @param {Object} params - { limit }
 */
export function getMessagesApi(sessionId, params) {
  return request.get(CHAT_PATHS.messages(sessionId), { params })
}

/**
 * 删除会话
 * @param {number} sessionId
 */
export function deleteSessionApi(sessionId) {
  return request.delete(CHAT_PATHS.session(sessionId))
}
