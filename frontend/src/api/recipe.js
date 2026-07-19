/**
 * V1 Recipe API
 * 对应 api_v1.md 第六节 Recipe API
 * - POST /api/recipes  生成菜谱
 * - GET  /api/recipes/{recipe_id}  查询菜谱
 */
import request from '@/utils/request'
import { recipeFixtures, recipeErrorFixtures } from '@/fixtures/recipe'

export const RECIPE_PATHS = Object.freeze({
  create: '/recipes',
  get: (recipeId) => `/recipes/${recipeId}`,
  history: '/recipes/history',
})

let injectedClient = null

export function setRecipeApiClient(client) {
  injectedClient = client
}

export function resetRecipeApiClient() {
  injectedClient = null
}

function cloneFixture(value) {
  return JSON.parse(JSON.stringify(value))
}

function createMockError(status) {
  const fixture = recipeErrorFixtures[status] || recipeErrorFixtures[503]
  const error = new Error(fixture.message)
  error.response = {
    status: fixture.status,
    data: {
      code: fixture.code,
      message: fixture.message,
    },
  }
  return error
}

function mockResponse(data, code = 201, message = 'success') {
  return Promise.resolve({
    code,
    message,
    data: cloneFixture(data),
  })
}

/**
 * 生成菜谱
 * @param {Object} data - { recognition_id, preferences }
 * @param {Object} options - { mockScenario, client }
 * @returns {Promise}
 */
export function createRecipe(data, options = {}) {
  const scenario = options.mockScenario ?? options.mock

  if (scenario === 'success') return mockResponse(recipeFixtures.success, 201, '菜谱生成成功')
  if (scenario === 'v2') return mockResponse(recipeFixtures.v2, 201, '菜谱生成成功')

  if (scenario && recipeErrorFixtures[scenario]) {
    return Promise.reject(createMockError(scenario))
  }

  const client = options.client || injectedClient
  if (client?.create) return client.create(data, options)

  // V1 请求体: recognition_id + preferences
  return request.post(RECIPE_PATHS.create, {
    recognition_id: data.recognition_id,
    preferences: data.preferences || {
      servings: 2,
      taste: '清淡',
      max_time_minutes: 30,
      avoid_ingredients: [],
    },
  })
}

/**
 * 查询菜谱
 * @param {number} recipeId
 * @param {Object} options - { mockScenario, client }
 * @returns {Promise}
 */
export function getRecipe(recipeId, options = {}) {
  const scenario = options.mockScenario ?? options.mock

  if (scenario === 'success') return mockResponse(recipeFixtures.success, 200, 'success')
  if (scenario === 'v2') return mockResponse(recipeFixtures.v2, 200, 'success')

  if (scenario && recipeErrorFixtures[scenario]) {
    return Promise.reject(createMockError(scenario))
  }

  const client = options.client || injectedClient
  if (client?.get) return client.get(recipeId, options)

  return request.get(RECIPE_PATHS.get(recipeId))
}

export function getRecipeHistory(params = {}) {
  return request.get(RECIPE_PATHS.history, { params })
}

/**
 * 解包 API 响应，提取 data 字段
 */
export function unwrapRecipeApiData(response) {
  return response?.data ?? response
}

/**
 * 创建 Mock Recipe API 客户端（用于页面级注入）
 */
export function createMockRecipeApiClient(scenario = 'success') {
  return {
    create: () => mockResponse(recipeFixtures[scenario] || recipeFixtures.success, 201, '菜谱生成成功'),
    get: (recipeId) => {
      // version=2 场景时返回 v2 fixture
      const fixture = scenario === 'v2' ? recipeFixtures.v2 : recipeFixtures.success
      return mockResponse(fixture, 200, 'success')
    },
  }
}
