import request, { uploadRequest } from '@/utils/request'
import {
  foodRecognitionFixtures,
  foodRecognitionErrorFixtures,
} from '@/fixtures/foodRecognition'

export const FOOD_RECOGNITION_PATHS = Object.freeze({
  create: '/food/recognitions',
  get: (recognitionId) => `/food/recognitions/${recognitionId}`,
  confirm: (recognitionId) => `/food/recognitions/${recognitionId}/ingredients`,
})

let injectedClient = null

export function setFoodApiClient(client) {
  injectedClient = client
}

export function resetFoodApiClient() {
  injectedClient = null
}

function cloneFixture(value) {
  return JSON.parse(JSON.stringify(value))
}

function createMockError(status) {
  const fixture = foodRecognitionErrorFixtures[status] || foodRecognitionErrorFixtures[503]
  const error = new Error(fixture.message)
  error.response = {
    status: fixture.status,
    data: {
      code: fixture.code,
      message: fixture.message,
      detail: fixture.message,
    },
  }
  return error
}

export function normalizeRecognitionId(value) {
  const id = Number(value)
  return Number.isInteger(id) ? id : null
}

export function normalizeConfirmedIngredients(ingredients = []) {
  return ingredients.map((ingredient) => ({
    name: String(ingredient.name || '').trim(),
    class_name: ingredient.class_name || null,
    quantity: Number(ingredient.quantity),
    unit: String(ingredient.unit || '').trim(),
    source: ingredient.source || 'manual',
  }))
}

function mockResponse(data, message = 'mock', code = 200) {
  return Promise.resolve({
    code,
    message,
    data: cloneFixture(data),
  })
}

function resolveMockScenario(scenario, operation = 'create') {
  if (!scenario || scenario === 'off') return null
  const code = operation === 'create' ? 201 : 200
  if (scenario === 'success') return mockResponse(foodRecognitionFixtures.success, 'mock', code)
  if (scenario === 'empty') return mockResponse(foodRecognitionFixtures.empty, 'mock', code)
  if (foodRecognitionErrorFixtures[scenario]) {
    return Promise.reject(createMockError(scenario))
  }
  return null
}

export function createMockFoodApiClient(scenario = 'success') {
  return {
    create: () => resolveMockScenario(scenario, 'create') || mockResponse(foodRecognitionFixtures.success, 'mock', 201),
    get: () => mockResponse(foodRecognitionFixtures.success),
    confirm: ({ recognitionId, ingredients }) =>
      Promise.resolve({
        code: 200,
        message: 'mock',
        data: {
          recognition_id: normalizeRecognitionId(recognitionId),
          confirmed_ingredients: cloneFixture(normalizeConfirmedIngredients(ingredients)),
          confirmed_at: '2026-07-14T21:35:00+08:00',
        },
      }),
  }
}

export function unwrapFoodApiData(response) {
  return response?.data ?? response
}

function normalizeRecognitionImages(data = {}) {
  if (data.images && typeof data.images[Symbol.iterator] === 'function') {
    return Array.from(data.images).filter(Boolean)
  }
  return data.image ? [data.image] : []
}

export function createFoodRecognition(data, options = {}) {
  const scenario = options.mockScenario ?? options.mock
  const mock = resolveMockScenario(scenario, 'create')
  if (mock) return mock

  const client = options.client || injectedClient
  if (client?.create) return client.create(data, options)

  const images = normalizeRecognitionImages(data)
  const formData = new FormData()
  images.forEach((image) => {
    formData.append('images', image)
  })
  if (images[0]) formData.append('image', images[0])
  formData.append('conf_threshold', data.conf_threshold ?? 0.25)

  return uploadRequest.post(FOOD_RECOGNITION_PATHS.create, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getFoodRecognition(recognitionId, options = {}) {
  const scenario = options.mockScenario ?? options.mock
  const mock = resolveMockScenario(scenario, 'get')
  if (mock) return mock

  const client = options.client || injectedClient
  if (client?.get) return client.get(recognitionId, options)

  return request.get(FOOD_RECOGNITION_PATHS.get(recognitionId))
}

export function confirmFoodIngredients(recognitionId, ingredients, options = {}) {
  const scenario = options.mockScenario ?? options.mock
  if (foodRecognitionErrorFixtures[scenario]) return Promise.reject(createMockError(scenario))

  const normalizedRecognitionId = normalizeRecognitionId(recognitionId)
  const confirmedIngredients = normalizeConfirmedIngredients(ingredients)

  const client = options.client || injectedClient
  if (client?.confirm) {
    return client.confirm(
      {
        recognitionId: normalizedRecognitionId,
        ingredients: confirmedIngredients,
      },
      options
    )
  }

  if (scenario && scenario !== 'off') {
    return createMockFoodApiClient('success').confirm({
      recognitionId: normalizedRecognitionId,
      ingredients: confirmedIngredients,
    })
  }

  return request.put(FOOD_RECOGNITION_PATHS.confirm(normalizedRecognitionId), {
    ingredients: confirmedIngredients,
  })
}
