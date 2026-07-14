import { afterEach, describe, expect, it, vi } from 'vitest'
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
  })

  it('keeps the day-one frozen recognition paths', () => {
    expect(FOOD_RECOGNITION_PATHS.create).toBe('/food/recognitions')
    expect(FOOD_RECOGNITION_PATHS.get('rec_1')).toBe('/food/recognitions/rec_1')
    expect(FOOD_RECOGNITION_PATHS.confirm('rec_1')).toBe('/food/recognitions/rec_1/ingredients')
  })

  it('returns cloned success and empty fixtures through mock scenarios', async () => {
    const success = await createFoodRecognition({ image: new File(['image'], 'meal.jpg') }, { mockScenario: 'success' })
    const empty = await getFoodRecognition('rec_empty', { mockScenario: 'empty' })

    expect(success.data.recognition_id).toBe('rec_mock_day1_001')
    expect(success.data.ingredients).toHaveLength(3)
    expect(empty.data.recognition_id).toBe('rec_mock_day1_empty')
    expect(empty.data.ingredients).toHaveLength(0)
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
