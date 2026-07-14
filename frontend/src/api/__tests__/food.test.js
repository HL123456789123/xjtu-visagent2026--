import { afterEach, describe, expect, it, vi } from 'vitest'
import { uploadRequest } from '@/utils/request'
import {
  FOOD_RECOGNITION_PATHS,
  confirmFoodIngredients,
  createFoodRecognition,
  createMockFoodApiClient,
  getFoodRecognition,
  resetFoodApiClient,
  setFoodApiClient,
} from '../food'

describe('food api contract', () => {
  afterEach(() => {
    resetFoodApiClient()
    vi.restoreAllMocks()
  })

  it('keeps the day-one frozen recognition paths', () => {
    expect(FOOD_RECOGNITION_PATHS.create).toBe('/food/recognitions')
    expect(FOOD_RECOGNITION_PATHS.get('rec_1')).toBe('/food/recognitions/rec_1')
    expect(FOOD_RECOGNITION_PATHS.confirm('rec_1')).toBe('/food/recognitions/rec_1/ingredients')
  })

  it('returns cloned success and empty fixtures through mock scenarios', async () => {
    const success = await createFoodRecognition(
      { images: [new File(['image'], 'meal.jpg')] },
      { mockScenario: 'success' }
    )
    const empty = await getFoodRecognition('rec_empty', { mockScenario: 'empty' })

    expect(success.data.recognition_id).toBe('rec_mock_day1_001')
    expect(success.data.ingredients).toHaveLength(3)
    expect(empty.data.recognition_id).toBe('rec_mock_day1_empty')
    expect(empty.data.ingredients).toHaveLength(0)
  })

  it('sends every selected image in the recognition upload form', async () => {
    const postSpy = vi.spyOn(uploadRequest, 'post').mockResolvedValue({ data: { recognition_id: 'rec_multi' } })
    const first = new File(['image-1'], 'meal-one.jpg', { type: 'image/jpeg' })
    const second = new File(['image-2'], 'meal-two.png', { type: 'image/png' })

    await createFoodRecognition(
      {
        images: [first, second],
        conf_threshold: 0.4,
      },
      { mockScenario: 'off' }
    )

    expect(postSpy).toHaveBeenCalledOnce()
    const [path, formData, config] = postSpy.mock.calls[0]

    expect(path).toBe(FOOD_RECOGNITION_PATHS.create)
    expect(formData.getAll('images')).toEqual([first, second])
    expect(formData.get('image')).toBe(first)
    expect(formData.get('image_count')).toBe('2')
    expect(formData.get('conf_threshold')).toBe('0.4')
    expect(config).toMatchObject({
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  })

  it('allows an injected client before the real backend is connected', async () => {
    const client = {
      create: vi.fn().mockResolvedValue({ data: { recognition_id: 'rec_injected' } }),
      get: vi.fn().mockResolvedValue({ data: { recognition_id: 'rec_injected' } }),
      confirm: vi.fn().mockResolvedValue({ data: { status: 'confirmed' } }),
    }
    setFoodApiClient(client)

    await createFoodRecognition({ image: new File(['image'], 'meal.jpg') })
    await getFoodRecognition('rec_injected')
    await confirmFoodIngredients('rec_injected', [{ key: 'egg', name: '鸡蛋' }])

    expect(client.create).toHaveBeenCalledOnce()
    expect(client.get).toHaveBeenCalledWith('rec_injected', {})
    expect(client.confirm).toHaveBeenCalledWith(
      {
        recognitionId: 'rec_injected',
        ingredients: [{ key: 'egg', name: '鸡蛋' }],
      },
      {}
    )
  })

  it('provides a reusable mock client for page-level injection', async () => {
    const client = createMockFoodApiClient('success')

    const created = await client.create()
    const confirmed = await client.confirm({
      recognitionId: created.data.recognition_id,
      ingredients: [{ key: 'tomato', name: '番茄' }],
    })

    expect(created.data.provider).toBe('mock')
    expect(confirmed.data).toEqual({
      recognition_id: 'rec_mock_day1_001',
      confirmed_ingredients: [{ key: 'tomato', name: '番茄' }],
      status: 'confirmed',
    })
  })
})
