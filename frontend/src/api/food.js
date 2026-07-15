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
          recognition_id: recognitionId,
          confirmed_ingredients: cloneFixture(ingredients),
          status: 'confirmed',
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
  formData.append('image_count', String(images.length))
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
  const client = options.client || injectedClient
  if (client?.confirm) return client.confirm({ recognitionId, ingredients }, options)

  return request.put(FOOD_RECOGNITION_PATHS.confirm(recognitionId), {
    ingredients,
  })
}
