/**
 * V1 SSE Canonical Fixture
 * 对应 backend/tests/fixtures/sse_recipe_update.txt
 * 只包含 V1 规定的四类事件: token / recipe_updated / done / error
 */

/**
 * 完整更新流程 SSE（token → recipe_updated → done）
 */
export const sseFullUpdateStream = [
  'event: token\n',
  'data: {"content":"已经调整为三人份，并减少了食用油用量。"}\n',
  '\n',
  'event: recipe_updated\n',
  'data: {"recipe_id":101,"version":2}\n',
  '\n',
  'event: done\n',
  'data: {"message_id":9001}\n',
  '\n',
].join('')

/**
 * 纯问答流程 SSE（token → done，无 recipe_updated）
 */
export const sseAnswerOnlyStream = [
  'event: token\n',
  'data: {"content":"鸡蛋炒至刚凝固时先盛出，可以避免口感过老。"}\n',
  '\n',
  'event: done\n',
  'data: {"message_id":9002}\n',
  '\n',
].join('')

/**
 * 错误流程 SSE（error）
 */
export const sseErrorStream = [
  'event: error\n',
  'data: {"code":"LLM_UNAVAILABLE","message":"智能服务暂时不可用"}\n',
  '\n',
].join('')

/**
 * 分块到达的 SSE（模拟跨 chunk 截断）
 */
export const sseChunkedStream = [
  'event: tok',
  'en\ndata: {"content":"',
  '已经调整为三人份"}\n\n',
  'event: recipe_upd',
  'ated\ndata: {"recipe_id":101,"version":2}\n\n',
  'event: done\ndata: {"message_id":9003}\n\n',
]

/**
 * 未知事件 SSE（遇到非四类事件时必须按未知处理）
 */
export const sseUnknownEventStream = [
  'event: token\n',
  'data: {"content":"正常回答"}\n',
  '\n',
  'event: tool_call\n',
  'data: {"name":"some_tool"}\n',
  '\n',
  'event: done\n',
  'data: {"message_id":9004}\n',
  '\n',
].join('')

export const sseFixtures = Object.freeze({
  fullUpdate: sseFullUpdateStream,
  answerOnly: sseAnswerOnlyStream,
  error: sseErrorStream,
  chunked: sseChunkedStream,
  unknownEvent: sseUnknownEventStream,
})
