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

function mockResponse(data, message = 'mock') {
  return Promise.resolve({
    code: 200,
    message,
    data: cloneFixture(data),
  })
}

function resolveMockScenario(scenario) {
  if (!scenario || scenario === 'off') return null
  if (scenario === 'success') return mockResponse(foodRecognitionFixtures.success)
  if (scenario === 'empty') return mockResponse(foodRecognitionFixtures.empty)
  if (foodRecognitionErrorFixtures[scenario]) {
    return Promise.reject(createMockError(scenario))
  }
  return null
}

export function createMockFoodApiClient(scenario = 'success') {
  return {
    create: () => resolveMockScenario(scenario) || mockResponse(foodRecognitionFixtures.success),
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

export function createFoodRecognition(data, options = {}) {
  const scenario = options.mockScenario ?? options.mock
  const mock = resolveMockScenario(scenario)
  if (mock) return mock

  const client = options.client || injectedClient
  if (client?.create) return client.create(data, options)

  const formData = new FormData()
  formData.append('image', data.image)
  formData.append('conf_threshold', data.conf_threshold ?? 0.25)

  return uploadRequest.post(FOOD_RECOGNITION_PATHS.create, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getFoodRecognition(recognitionId, options = {}) {
  const scenario = options.mockScenario ?? options.mock
  const mock = resolveMockScenario(scenario)
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
