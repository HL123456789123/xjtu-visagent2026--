/**
 * 智能体对话状态管理
 *
 * 管理对话消息、会话列表、加载状态
 */
import { defineStore } from 'pinia'

export const useAgentStore = defineStore('agent', {
  state: () => ({
    // 当前会话 ID
    currentSessionId: null,
    // 当前对话消息列表
    messages: [],
    // 历史会话列表
    sessions: [],
    // AI 是否正在生成回复
    isLoading: false,
    // SSE 中止控制器
    abortController: null,
  }),

  getters: {
    /** 消息总数 */
    messageCount: (state) => state.messages.length,
    /** 是否有历史会话 */
    hasSession: (state) => state.sessions.length > 0,
  },

  actions: {
    /** 添加一条消息 */
    addMessage(message) {
      this.messages.push(message)
    },

    /** 更新最后一条 AI 消息内容 */
    updateLastAssistantMessage(content) {
      const lastMsg = this.messages[this.messages.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        lastMsg.content = content
      }
    },

    /** 设置加载状态 */
    setLoading(loading) {
      this.isLoading = loading
    },

    /** 中止当前请求 */
    abort() {
      if (this.abortController) {
        this.abortController()
        this.abortController = null
        this.isLoading = false
      }
    },

    /** 新建对话 */
    newChat() {
      this.currentSessionId = null
      this.messages = []
      this.abort()
    },

    /** 清空所有状态 */
    clear() {
      this.currentSessionId = null
      this.messages = []
      this.sessions = []
      this.abort()
    },
  },
})
