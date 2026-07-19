import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetFoodApiClient, setFoodApiClient } from '@/api/food'
import { resetRecipeApiClient, setRecipeApiClient } from '@/api/recipe'
import FoodImageUploader from '@/components/food/FoodImageUploader.vue'
import FoodRecipePage from '../FoodRecipePage.vue'

function makeImageFile(name = 'meal.jpg') {
  return new File(['image'], name, { type: 'image/jpeg' })
}

async function selectImages(wrapper, files = [makeImageFile()]) {
  const uploader = wrapper.findComponent(FoodImageUploader)
  uploader.vm.selectFiles(files)
  await flushPromises()
}

describe('FoodRecipePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn((file) => `blob:${file.name}`),
      revokeObjectURL: vi.fn(),
    })
  })

  afterEach(() => {
    resetFoodApiClient()
    resetRecipeApiClient()
  })

  it('restores confirmed ingredients instead of raw empty candidates for a saved recipe', async () => {
    setRecipeApiClient({
      get: vi.fn().mockResolvedValue({
        data: {
          recipe_id: 101,
          recognition_id: 12,
          version: 2,
          title: '恢复菜谱',
          summary: '用于历史恢复验证。',
          servings: 3,
          cooking_time_minutes: 20,
          difficulty: '简单',
          ingredients: [],
          steps: [],
          nutrition: {
            basis: 'per_serving',
            calories_kcal: 0,
            protein_g: 0,
            fat_g: 0,
            carbohydrates_g: 0,
          },
          nutrition_disclaimer: '仅供参考。',
          generator: { provider: 'fake', model: 'fixture-v1', is_mock: true },
        },
      }),
    })
    setFoodApiClient({
      get: vi.fn().mockResolvedValue({
        data: {
          recognition_id: 12,
          provider: 'mock',
          model_version: 'food-mock-v1',
          images: [{ image_index: 0, image_url: '/food/12/0' }],
          ingredients: [],
          confirmed_ingredients: [
            { name: 'egg', class_name: null, quantity: 1, unit: 'piece', source: 'manual' },
          ],
        },
      }),
    })

    const wrapper = mount(FoodRecipePage, { props: { recipeId: 101 } })
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('confirmed')
    expect(wrapper.findAll('[data-testid="ingredient-name"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="ingredient-name"]').element.value).toBe('egg')
    expect(wrapper.find('[data-testid="summary-confirmed-count"]').text()).toBe('1 项')
  })

  it('runs the success mock flow and emits the recipe contract after confirmation', async () => {
    const wrapper = mount(FoodRecipePage)

    await wrapper.find('[data-testid="mock-scenario"]').setValue('success')
    await selectImages(wrapper, [makeImageFile('breakfast.jpg'), makeImageFile('vegetables.jpg')])
    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('selecting')
    expect(wrapper.find('[data-testid="selecting-state"]').text()).toContain('2 张图片')

    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('recognized')
    const ingredientNames = wrapper
      .findAll('[data-testid="ingredient-name"]')
      .map((input) => input.element.value)
    expect(ingredientNames).toEqual(['番茄', '鸡蛋'])

    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('confirmed')
    expect(wrapper.find('[data-testid="summary-recognition-id"]').text()).toBe('12')
    expect(wrapper.find('[data-testid="summary-confirmed-count"]').text()).toBe('2 项')
    expect(wrapper.find('[data-testid="summary-image-count"]').text()).toBe('2 张')
    expect(wrapper.find('[data-testid="recipe-flow-recognition-id"]').text()).toContain('12')
    expect(wrapper.emitted('confirmed')?.[0][0]).toEqual({
      recognition_id: 12,
      confirmed_ingredients: [
        { name: '番茄', class_name: 'tomato', quantity: 1, unit: '个', source: 'model' },
        { name: '鸡蛋', class_name: 'egg', quantity: 1, unit: '个', source: 'model' },
      ],
    })

    await wrapper.find('[data-testid="recipe-generate"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('recipe-requested')?.[0][0]).toEqual({
      recognition_id: 12,
      preferences: {
        servings: 2,
        taste: '家常',
        max_time_minutes: 30,
        avoid_ingredients: [],
      },
      recipe_id: 101,
      confirmed_ingredients: [
        { name: '番茄', class_name: 'tomato', quantity: 1, unit: '个', source: 'model' },
        { name: '鸡蛋', class_name: 'egg', quantity: 1, unit: '个', source: 'model' },
      ],
    })
    expect(wrapper.find('[data-testid="recipe-card"]').text()).toContain('番茄炒蛋')
  })

  it('keeps the empty-recognition state visible and allows manual ingredient input', async () => {
    const wrapper = mount(FoodRecipePage)

    await wrapper.find('[data-testid="mock-scenario"]').setValue('empty')
    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('recognized')
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ingredient-empty"]').exists()).toBe(true)

    await wrapper.find('[data-testid="ingredient-add"]').trigger('click')
    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')

    expect(wrapper.find('[data-testid="ingredient-errors"]').text()).toContain('不能为空')
  })

  it('shows reserved 503 error state from the mock API', async () => {
    const wrapper = mount(FoodRecipePage)

    await wrapper.find('[data-testid="mock-scenario"]').setValue('503')
    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('error')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('识别服务不可用')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('食物识别服务暂不可用')
  })

  it('shows reserved 413 and 415 error states from the mock API', async () => {
    const wrapper = mount(FoodRecipePage)

    await wrapper.find('[data-testid="mock-scenario"]').setValue('413')
    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('error')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('图片过大')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('单张图片不能超过 10 MB')

    await wrapper.find('[data-testid="mock-scenario"]').setValue('415')
    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('error')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('图片格式不支持')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('JPG、JPEG 或 PNG')
  })

  it('shows a network failure state when the mock backend is unreachable', async () => {
    const wrapper = mount(FoodRecipePage)

    await wrapper.find('[data-testid="mock-scenario"]').setValue('network')
    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('error')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('网络连接失败')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('后端 Mock 服务')
  })
})
