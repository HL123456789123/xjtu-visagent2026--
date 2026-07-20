import { beforeEach, describe, expect, it, vi } from 'vitest'

const clients = vi.hoisted(() => ({
  request: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
  uploadRequest: { post: vi.fn() },
}))

vi.mock('@/utils/request', () => ({
  default: clients.request,
  uploadRequest: clients.uploadRequest,
}))

import {
  activateFoodModel,
  deleteFoodModel,
  getFoodModels,
  rollbackFoodModel,
  uploadFoodModel,
} from '../foodModel'

describe('Food model administration API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses only the Food model registry routes', async () => {
    const packageFile = new File(['zip'], 'food-v2.zip', { type: 'application/zip' })
    const progress = vi.fn()

    getFoodModels()
    uploadFoodModel(packageFile, progress)
    activateFoodModel(7)
    rollbackFoodModel()
    deleteFoodModel(6)

    expect(clients.request.get).toHaveBeenCalledWith('/admin/food-models')
    const [path, form, config] = clients.uploadRequest.post.mock.calls[0]
    expect(path).toBe('/admin/food-models')
    expect(form.get('package')).toBe(packageFile)
    expect(config.onUploadProgress).toBe(progress)
    expect(clients.request.post).toHaveBeenCalledWith('/admin/food-models/7/activate')
    expect(clients.request.post).toHaveBeenCalledWith('/admin/food-models/rollback')
    expect(clients.request.delete).toHaveBeenCalledWith('/admin/food-models/6')
  })
})
