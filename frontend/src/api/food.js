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

function normalizeUploadImages(data = {}) {
  if (data?.images && typeof data.images[Symbol.iterator] === 'function') {
    return Array.from(data.images).filter(Boolean)
  }
  return []
}

function normalizeImageIndex(value, fallback) {
  if (value === null || value === undefined || value === '') return fallback
  const imageIndex = Number(value)
  return Number.isInteger(imageIndex) && imageIndex >= 0 ? imageIndex : fallback
}

function normalizeCandidate(candidate, imageIndex) {
  return {
    ...candidate,
    image_index: normalizeImageIndex(candidate?.image_index, imageIndex),
  }
}

/**
 * 将后端的多图响应转换为页面可直接渲染的结构。
 *
 * 后端 V1.1 的 ``images[].ingredients`` 才是候选食材与原图的一一对应关系，
 * 此处同时补全扁平 ``ingredients`` 的 image_index，供食材确认编辑器沿用。
 * 对只有 ``image_url``/``ingredients`` 的旧单图响应仍保持兼容。
 */
export function normalizeFoodRecognitionData(data = {}) {
  if (!data || typeof data !== 'object') {
    return { images: [], ingredients: [] }
  }

  const sourceImages = Array.isArray(data.images) ? data.images : []
  const hasGroupedIngredients = sourceImages.some((image) => Array.isArray(image?.ingredients))
  let images = sourceImages.map((image, fallbackIndex) => {
    const imageIndex = normalizeImageIndex(image?.image_index, fallbackIndex)
    return {
      ...image,
      image_index: imageIndex,
      image_url: image?.image_url || '',
      ingredients: Array.isArray(image?.ingredients)
        ? image.ingredients.map((candidate) => normalizeCandidate(candidate, imageIndex))
        : [],
    }
  })

  const fallbackIngredients = Array.isArray(data.ingredients) ? data.ingredients : []
  if (!images.length && data.image_url) {
    images = [
      {
        image_index: 0,
        image_url: data.image_url,
        ingredients: fallbackIngredients.map((candidate) => normalizeCandidate(candidate, 0)),
      },
    ]
  }

  if (!hasGroupedIngredients && images.length) {
    const imageIndexes = new Set(images.map((image) => image.image_index))
    const singleImageIndex = images.length === 1 ? images[0].image_index : null
    const ingredientsByImageIndex = new Map(images.map((image) => [image.image_index, []]))

    fallbackIngredients.forEach((candidate) => {
      const candidateImageIndex = normalizeImageIndex(candidate?.image_index, singleImageIndex)
      if (imageIndexes.has(candidateImageIndex)) {
        ingredientsByImageIndex.get(candidateImageIndex).push(normalizeCandidate(candidate, candidateImageIndex))
      }
    })
    images = images.map((image) => ({
      ...image,
      ingredients: ingredientsByImageIndex.get(image.image_index) || [],
    }))
  }

  const ingredients = hasGroupedIngredients
    ? images.flatMap((image) => image.ingredients)
    : fallbackIngredients.map((candidate) => {
        const fallbackIndex = images.length === 1 ? images[0].image_index : null
        return normalizeCandidate(candidate, fallbackIndex)
      })

  return {
    ...data,
    image_url: data.image_url || images[0]?.image_url || '',
    images,
    ingredients,
  }
}

export function createFoodRecognition(data, options = {}) {
  const scenario = options.mockScenario ?? options.mock
  const mock = resolveMockScenario(scenario, 'create')
  if (mock) return mock

  const client = options.client || injectedClient
  if (client?.create) return client.create(data, options)

  const images = normalizeUploadImages(data)
  const formData = new FormData()
  images.forEach((image) => {
    formData.append('images', image)
  })
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
