/**
 * SSE (Server-Sent Events) 流式聊天工具
 *
 * Day11 与 LangGraph Agent 通信时使用
 *
 * 使用示例:
 *   const stop = streamChat(
 *     '/api/chat/stream',
 *     { message: '你好' },
 *     {
 *       onMessage: (chunk) => { content += chunk },
 *       onDone: () => { console.log('完成') },
 *       onError: (err) => { console.error(err) },
 *     }
 *   )
 */

/**
 * 发起 SSE 流式请求
 *
 * @param {string} url - 请求路径（使用 Vite proxy 相对路径）
 * @param {Object} body - 请求体
 * @param {Object} callbacks - 回调函数
 * @param {Function} callbacks.onMessage - 收到消息块
 * @param {Function} callbacks.onDone - 流结束
 * @param {Function} callbacks.onError - 发生错误
 * @returns {Function} stop - 调用以中止请求
 */
export function streamChat(url, body, callbacks) {
  const { onMessage, onDone, onError } = callbacks

  // 使用 fetch + ReadableStream 处理 SSE
  const controller = new AbortController()

  // 如果 body 为空对象或 undefined，则不发送 body
  const hasBody = body && Object.keys(body).length > 0

  fetch(url, {
    method: 'POST',
    credentials: 'include',  // 自动携带 HttpOnly cookie
    headers: {
      'Content-Type': 'application/json',
    },
    ...(hasBody ? { body: JSON.stringify(body) } : {}),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        if (response.status === 401) {
          const { useUserStore } = await import('@/stores/user')
          const userStore = useUserStore()
          userStore.logout()
          window.location.href = '/login'
          return
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          onDone?.()
          break
        }

        // 解析 SSE 格式
        const text = decoder.decode(value, { stream: true })
        const lines = text.split('\n')

        for (const line of lines) {
          if (line.startsWith('data:')) {
            const data = line.slice(6) // 去掉 "data:"
            if (data === '[DONE]') {
              onDone?.()
              return
            }
            try {
              const parsed = JSON.parse(data)
              onMessage?.(parsed)
            } catch {
              // JSON 解析失败则直接返回原始文本
              onMessage?.(data)
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError?.(err)
      }
    })

  // 返回中止函数
  return () => controller.abort()
}
