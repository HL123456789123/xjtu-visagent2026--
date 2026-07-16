import { afterEach, describe, expect, it, vi } from 'vitest'
import { uploadRequest } from '@/utils/request'
import {
  FOOD_RECOGNITION_PATHS,
  confirmFoodIngredients,
  createFoodRecognition,
  createMockFoodApiClient,
  getFoodRecognition,
  normalizeConfirmedIngredients,
  normalizeRecognitionId,
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
    expect(FOOD_RECOGNITION_PATHS.get(12)).toBe('/food/recognitions/12')
    expect(FOOD_RECOGNITION_PATHS.confirm(12)).toBe('/food/recognitions/12/ingredients')
  })

  it('returns cloned success and empty fixtures through mock scenarios', async () => {
    const success = await createFoodRecognition(
      { images: [new File(['image'], 'meal.jpg')] },
      { mockScenario: 'success' }
    )
    const empty = await getFoodRecognition('rec_empty', { mockScenario: 'empty' })

    expect(success.code).toBe(201)
    expect(success.data.recognition_id).toBe(12)
    expect(success.data.ingredients).toHaveLength(2)
    expect(success.data.ingredients[0]).toMatchObject({
      candidate_id: 'det-1',
      class_name: 'tomato',
      display_name: '番茄',
      confidence: 0.9321,
    })
    expect(empty.code).toBe(200)
    expect(empty.data.recognition_id).toBe(13)
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
    expect(formData.has('image_count')).toBe(false)
    expect(formData.get('conf_threshold')).toBe('0.4')
    expect(config).toMatchObject({
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  })

  it('normalizes recognition ids and strips confirmation-only payload fields', () => {
    expect(normalizeRecognitionId('12')).toBe(12)
    expect(normalizeRecognitionId('rec_12')).toBeNull()
    expect(
      normalizeConfirmedIngredients([
        {
          name: ' 番茄 ',
          class_name: 'tomato',
          quantity: '2',
          unit: ' 个 ',
          source: 'model',
          candidate_id: 'det-1',
          confidence: 0.93,
        },
      ])
    ).toEqual([
      {
        name: '番茄',
        class_name: 'tomato',
        quantity: 2,
        unit: '个',
        source: 'model',
      },
    ])
  })

  it('allows an injected client before the real backend is connected', async () => {
    const client = {
      create: vi.fn().mockResolvedValue({ data: { recognition_id: 'rec_injected' } }),
      get: vi.fn().mockResolvedValue({ data: { recognition_id: 'rec_injected' } }),
      confirm: vi.fn().mockResolvedValue({ data: { status: 'confirmed' } }),
    }
    setFoodApiClient(client)

    await createFoodRecognition({ images: [new File(['image'], 'meal.jpg')] })
    await getFoodRecognition(12)
    const confirmedIngredient = {
      name: '鸡蛋',
      class_name: 'egg',
      quantity: 1,
      unit: '个',
      source: 'model',
      candidate_id: 'det-extra',
    }
    await confirmFoodIngredients(12, [confirmedIngredient])

    expect(client.create).toHaveBeenCalledOnce()
    expect(client.get).toHaveBeenCalledWith(12, {})
    expect(client.confirm).toHaveBeenCalledWith(
      {
        recognitionId: 12,
        ingredients: [
          {
            name: '鸡蛋',
            class_name: 'egg',
            quantity: 1,
            unit: '个',
            source: 'model',
          },
        ],
      },
      {}
    )
  })

  it('provides a reusable mock client for page-level injection', async () => {
    const client = createMockFoodApiClient('success')

    const created = await client.create()
    const confirmedIngredient = {
      name: '番茄',
      class_name: 'tomato',
      quantity: 2,
      unit: '个',
      source: 'model',
    }
    const confirmed = await client.confirm({
      recognitionId: created.data.recognition_id,
      ingredients: [confirmedIngredient],
    })

    expect(created.code).toBe(201)
    expect(created.data.provider).toBe('mock')
    expect(confirmed.data).toEqual({
      recognition_id: 12,
      confirmed_ingredients: [confirmedIngredient],
      confirmed_at: '2026-07-14T21:35:00+08:00',
    })
  })

  it('exposes reserved mock errors for 413 and 415', async () => {
    await expect(createFoodRecognition({}, { mockScenario: '413' })).rejects.toMatchObject({
      response: {
        status: 413,
        data: { code: 'IMAGE_TOO_LARGE' },
      },
    })
    await expect(confirmFoodIngredients(12, [], { mockScenario: '415' })).rejects.toMatchObject({
      response: {
        status: 415,
        data: { code: 'UNSUPPORTED_IMAGE_TYPE' },
      },
    })
  })
})
