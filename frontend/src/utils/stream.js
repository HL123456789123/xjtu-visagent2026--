/**
 * V1 SSE 流式解析器
 * 对应 api_v1.md 第八节 SSE 只保留四种事件
 *
 * 只识别以下四类事件：
 *   - token          : {"content":"..."}
 *   - recipe_updated : {"recipe_id":101,"version":2}
 *   - done           : {"message_id":9001}
 *   - error          : {"code":"LLM_UNAVAILABLE","message":"..."}
 *
 * 其他事件（如 tool_call / tool_result）按未知事件处理，不新增兼容。
 */

/** V1 规定的四类 SSE 事件名 */
export const SSE_EVENT_TYPES = Object.freeze({
  TOKEN: 'token',
  RECIPE_UPDATED: 'recipe_updated',
  DONE: 'done',
  ERROR: 'error',
})

/** 已知事件名集合 */
const KNOWN_EVENTS = new Set(Object.values(SSE_EVENT_TYPES))

/**
 * 解析 SSE 文本缓冲区，提取完整事件
 *
 * SSE 格式：
 *   event: token
 *   data: {"content":"..."}
 *   <空行表示一个事件结束>
 *
 * @param {string} buffer - 累积的文本缓冲区
 * @returns {{ events: Array, remaining: string }}
 *   - events: [{ event: string|null, data: string }]
 *   - remaining: 未完成的文本（下一次拼接用）
 */
export function parseSSEBuffer(buffer) {
  const events = []
  // SSE 事件之间用空行分隔（\n\n）
  const blocks = buffer.split('\n\n')
  // 最后一块可能不完整，保留到下次
  const remaining = blocks.pop() || ''

  for (const block of blocks) {
    if (!block.trim()) continue

    let eventType = null
    const dataLines = []

    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
      // 忽略 id:、retry: 等其他 SSE 字段
    }

    // 至少要有 data 才算有效事件
    if (dataLines.length === 0) continue

    events.push({
      event: eventType,
      data: dataLines.join('\n'),
    })
  }

  return { events, remaining }
}

/**
 * 将原始 SSE 事件对象解析为 V1 标准化的回调数据
 *
 * @param {{ event: string|null, data: string }} raw
 * @returns {{ type: string, payload: any } | null}
 *   返回 null 表示未知事件，不处理
 */
export function parseSSEEvent(raw) {
  if (!raw || !raw.data) return null

  let parsed
  try {
    parsed = JSON.parse(raw.data)
  } catch {
    // data 不是合法 JSON，按错误处理
    return { type: SSE_EVENT_TYPES.ERROR, payload: { code: 'PARSE_ERROR', message: 'SSE 数据解析失败' } }
  }

  const eventType = raw.event

  // 只有四类已知事件才处理
  if (!eventType || !KNOWN_EVENTS.has(eventType)) {
    return null // 未知事件，返回 null
  }

  return { type: eventType, payload: parsed }
}

/**
 * 发起 V1 SSE 流式请求
 *
 * 只回调四类事件：onToken / onRecipeUpdated / onDone / onError
 * 未知事件不触发任何回调（按 V1 要求不新增兼容）
 *
 * @param {string} url - 请求路径（使用 Vite proxy 相对路径，如 /api/chat/sessions/501/messages）
 * @param {Object} body - 请求体，V1 格式: { content: "..." }
 * @param {Object} callbacks
 * @param {Function} [callbacks.onToken] - 收到 token 事件
 * @param {Function} [callbacks.onRecipeUpdated] - 收到 recipe_updated 事件
 * @param {Function} [callbacks.onDone] - 收到 done 事件，流结束
 * @param {Function} [callbacks.onError] - 收到 error 事件或网络错误
 * @param {Function} [callbacks.onUnknown] - 收到未知事件（可选，仅用于调试）
 * @returns {Function} stop - 调用以中止请求
 */
export function streamChat(url, body, callbacks = {}) {
  const { onToken, onRecipeUpdated, onDone, onError, onUnknown } = callbacks

  const controller = new AbortController()

  const hasBody = body && Object.keys(body).length > 0

  fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    ...(hasBody ? { body: JSON.stringify(body) } : {}),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        // 503 等非 2xx 状态码
        if (response.status === 401) {
          const { useUserStore } = await import('@/stores/user')
          const { default: router } = await import('@/router')
          const userStore = useUserStore()
          userStore.logout()
          router.push('/login')
          return
        }
        // 尝试解析错误响应体
        let errorPayload
        try {
          const errorData = await response.json()
          errorPayload = {
            code: errorData.code || 'HTTP_ERROR',
            message: errorData.message || `HTTP ${response.status}`,
          }
        } catch {
          errorPayload = {
            code: 'HTTP_ERROR',
            message: `HTTP ${response.status}: ${response.statusText}`,
          }
        }
        onError?.(errorPayload)
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          // 流正常结束，如果没有收到 done 事件也要触发 onDone
          onDone?.({ message_id: null })
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const { events, remaining } = parseSSEBuffer(buffer)
        buffer = remaining

        for (const rawEvent of events) {
          const parsed = parseSSEEvent(rawEvent)
          if (!parsed) {
            // 未知事件，不新增兼容
            onUnknown?.({ event: rawEvent.event, data: rawEvent.data })
            continue
          }

          switch (parsed.type) {
            case SSE_EVENT_TYPES.TOKEN:
              onToken?.(parsed.payload)
              break
            case SSE_EVENT_TYPES.RECIPE_UPDATED:
              onRecipeUpdated?.(parsed.payload)
              break
            case SSE_EVENT_TYPES.DONE:
              onDone?.(parsed.payload)
              return
            case SSE_EVENT_TYPES.ERROR:
              onError?.(parsed.payload)
              return
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError?.({ code: 'NETWORK_ERROR', message: '网络连接失败' })
      }
    })

  return () => controller.abort()
}
