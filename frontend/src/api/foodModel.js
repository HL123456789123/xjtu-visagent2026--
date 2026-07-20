import request, { uploadRequest } from '@/utils/request'

export const FOOD_MODEL_PATHS = Object.freeze({
  list: '/admin/food-models',
  activate: (modelId) => `/admin/food-models/${modelId}/activate`,
  rollback: '/admin/food-models/rollback',
  remove: (modelId) => `/admin/food-models/${modelId}`,
})

export function getFoodModels() {
  return request.get(FOOD_MODEL_PATHS.list)
}

export function uploadFoodModel(file, onUploadProgress) {
  const form = new FormData()
  form.append('package', file)
  return uploadRequest.post(FOOD_MODEL_PATHS.list, form, { onUploadProgress })
}

export function activateFoodModel(modelId) {
  return request.post(FOOD_MODEL_PATHS.activate(modelId))
}

export function rollbackFoodModel() {
  return request.post(FOOD_MODEL_PATHS.rollback)
}

export function deleteFoodModel(modelId) {
  return request.delete(FOOD_MODEL_PATHS.remove(modelId))
}
