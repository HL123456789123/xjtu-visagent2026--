import { describe, expect, it } from 'vitest'
import {
  SSE_EVENT_TYPES,
  parseSSEBuffer,
  parseSSEEvent,
} from '../stream'
import {
  sseFullUpdateStream,
  sseAnswerOnlyStream,
  sseErrorStream,
  sseChunkedStream,
  sseUnknownEventStream,
} from '@/fixtures/sse'

describe('SSE_EVENT_TYPES', () => {
  it('只保留 V1 规定的四类事件名', () => {
    expect(SSE_EVENT_TYPES.TOKEN).toBe('token')
    expect(SSE_EVENT_TYPES.RECIPE_UPDATED).toBe('recipe_updated')
    expect(SSE_EVENT_TYPES.DONE).toBe('done')
    expect(SSE_EVENT_TYPES.ERROR).toBe('error')
  })
})

describe('parseSSEBuffer', () => {
  it('解析完整的 token 事件流', () => {
    const { events, remaining } = parseSSEBuffer(sseFullUpdateStream)

    expect(events).toHaveLength(3)
    expect(events[0].event).toBe('token')
    expect(events[0].data).toBe('{"content":"已经调整为三人份，并减少了食用油用量。"}')
    expect(events[1].event).toBe('recipe_updated')
    expect(events[1].data).toBe('{"recipe_id":101,"version":2}')
    expect(events[2].event).toBe('done')
    expect(remaining).toBe('')
  })

  it('解析纯问答流（token → done）', () => {
    const { events } = parseSSEBuffer(sseAnswerOnlyStream)

    expect(events).toHaveLength(2)
    expect(events[0].event).toBe('token')
    expect(events[1].event).toBe('done')
  })

  it('解析错误流', () => {
    const { events } = parseSSEBuffer(sseErrorStream)

    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('error')
    expect(events[0].data).toContain('LLM_UNAVAILABLE')
  })

  it('保留不完整的块到 remaining', () => {
    // 只有一半 event，没有空行结束
    const partial = 'event: token\ndata: {"content":"hello"}'
    const { events, remaining } = parseSSEBuffer(partial)

    expect(events).toHaveLength(0)
    expect(remaining).toBe(partial)
  })

  it('分块拼接后正确解析', () => {
    // 模拟跨 chunk 到达
    let buffer = ''
    let allEvents = []

    for (const chunk of sseChunkedStream) {
      buffer += chunk
      const result = parseSSEBuffer(buffer)
      allEvents.push(...result.events)
      buffer = result.remaining
    }

    expect(allEvents).toHaveLength(3)
    expect(allEvents[0].event).toBe('token')
    expect(allEvents[0].data).toContain('已经调整为三人份')
    expect(allEvents[1].event).toBe('recipe_updated')
    expect(allEvents[2].event).toBe('done')
  })

  it('处理多行 data 字段', () => {
    const stream = 'event: token\ndata: line1\ndata: line2\n\n'
    const { events } = parseSSEBuffer(stream)

    expect(events).toHaveLength(1)
    expect(events[0].data).toBe('line1\nline2')
  })
})

describe('parseSSEEvent', () => {
  it('解析 token 事件', () => {
    const result = parseSSEEvent({
      event: 'token',
      data: '{"content":"你好"}',
    })

    expect(result.type).toBe('token')
    expect(result.payload.content).toBe('你好')
  })

  it('解析 recipe_updated 事件', () => {
    const result = parseSSEEvent({
      event: 'recipe_updated',
      data: '{"recipe_id":101,"version":2}',
    })

    expect(result.type).toBe('recipe_updated')
    expect(result.payload.recipe_id).toBe(101)
    expect(result.payload.version).toBe(2)
  })

  it('解析 done 事件', () => {
    const result = parseSSEEvent({
      event: 'done',
      data: '{"message_id":9001}',
    })

    expect(result.type).toBe('done')
    expect(result.payload.message_id).toBe(9001)
  })

  it('解析 error 事件', () => {
    const result = parseSSEEvent({
      event: 'error',
      data: '{"code":"LLM_UNAVAILABLE","message":"智能服务暂时不可用"}',
    })

    expect(result.type).toBe('error')
    expect(result.payload.code).toBe('LLM_UNAVAILABLE')
    expect(result.payload.message).toBe('智能服务暂时不可用')
  })

  it('对未知事件返回 null（不新增兼容）', () => {
    expect(parseSSEEvent({ event: 'tool_call', data: '{}' })).toBeNull()
    expect(parseSSEEvent({ event: 'tool_result', data: '{}' })).toBeNull()
    expect(parseSSEEvent({ event: 'custom_event', data: '{}' })).toBeNull()
  })

  it('对无 event 字段的事件返回 null', () => {
    expect(parseSSEEvent({ event: null, data: '{}' })).toBeNull()
  })

  it('对无效 JSON 返回 error 类型', () => {
    const result = parseSSEEvent({
      event: 'token',
      data: 'not-json',
    })

    expect(result.type).toBe('error')
    expect(result.payload.code).toBe('PARSE_ERROR')
  })

  it('对 null 输入返回 null', () => {
    expect(parseSSEEvent(null)).toBeNull()
    expect(parseSSEEvent({})).toBeNull()
  })

  it('完整未知事件流中只处理四类事件', () => {
    const { events } = parseSSEBuffer(sseUnknownEventStream)

    // 解析出 3 个原始事件：token, tool_call, done
    expect(events).toHaveLength(3)

    // 只有 token 和 done 被识别为有效事件
    const parsed = events.map(parseSSEEvent).filter(Boolean)
    expect(parsed).toHaveLength(2)
    expect(parsed[0].type).toBe('token')
    expect(parsed[1].type).toBe('done')
  })
})
