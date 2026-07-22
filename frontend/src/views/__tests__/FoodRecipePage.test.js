import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetFoodApiClient, setFoodApiClient } from '@/api/food'
import { resetRecipeApiClient, setRecipeApiClient } from '@/api/recipe'
import FoodImageUploader from '@/components/food/FoodImageUploader.vue'
import { foodRecognitionFixtures } from '@/fixtures/foodRecognition'
import { recipeSuccessFixture } from '@/fixtures/recipe'
import FoodRecipePage from '../FoodRecipePage.vue'

const routerMocks = vi.hoisted(() => ({
  query: {},
  replace: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ query: routerMocks.query }),
    useRouter: () => ({ replace: routerMocks.replace }),
  }
})

function makeImageFile(name = 'meal.jpg') {
  return new File(['image'], name, { type: 'image/jpeg' })
}

async function selectImages(wrapper, files = [makeImageFile()]) {
  const uploader = wrapper.findComponent(FoodImageUploader)
  uploader.vm.selectFiles(files)
  await flushPromises()
}

function makeFoodApiError(status, message) {
  const error = new Error(message)
  if (status !== 0) {
    error.response = {
      status,
      data: { message },
    }
  }
  return error
}

describe('FoodRecipePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.keys(routerMocks.query).forEach((key) => delete routerMocks.query[key])
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
          task: 'classify',
          localization: 'full_image',
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

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('可以生成菜谱啦～')
    expect(wrapper.findAll('[data-testid="ingredient-name"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="ingredient-name"]').element.value).toBe('egg')
    expect(wrapper.find('[data-testid="recipe-stage"]').isVisible()).toBe(true)
    expect(wrapper.text()).not.toContain('开始生成菜谱')
    expect(wrapper.text()).toContain('当前为整图分类模式')
  })

  it('shows v1 from the title selector and can return to the current version', async () => {
    const currentRecipe = {
      ...recipeSuccessFixture,
      recipe_id: 101,
      recognition_id: 12,
      version: 3,
      title: '当前菜谱',
    }
    const get = vi.fn().mockResolvedValue({ data: currentRecipe })
    const version = vi.fn().mockResolvedValue({
      data: {
        version: 1,
        recipe: { ...recipeSuccessFixture, version: undefined, title: '初版菜谱' },
      },
    })
    setRecipeApiClient({
      get,
      versions: vi.fn().mockResolvedValue({
        data: {
          recipe_id: 101,
          current_version: 3,
          versions: [
            { version: 1, is_current: false },
            { version: 2, is_current: false },
            { version: 3, is_current: true },
          ],
        },
      }),
      version,
    })
    setFoodApiClient({
      get: vi.fn().mockResolvedValue({
        data: {
          recognition_id: 12,
          provider: 'mock',
          model_version: 'food-mock-v1',
          images: [],
          ingredients: [],
          confirmed_ingredients: [
            { name: '番茄', class_name: 'tomato', quantity: 1, unit: '个', source: 'model' },
          ],
        },
      }),
    })

    const wrapper = mount(FoodRecipePage, { props: { recipeId: 101 } })
    await flushPromises()

    await wrapper.find('[data-testid="recipe-version-select"]').setValue('1')
    await flushPromises()

    expect(version).toHaveBeenCalledWith(101, 1, expect.any(Object))
    expect(wrapper.find('[data-testid="recipe-title"]').text()).toBe('初版菜谱')
    expect(wrapper.find('[data-testid="historical-version-note"]').text()).toContain('正在查看 v1')

    await wrapper.find('[data-testid="return-current-version"]').trigger('click')
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="recipe-title"]').text()).toBe('当前菜谱')
  })

  it('does not present recipe suggestions as owned ingredients', async () => {
    setRecipeApiClient({
      get: vi.fn().mockResolvedValue({
        data: {
          recipe_id: 101,
          recognition_id: 12,
          version: 2,
          title: '番茄土豆炖牛肉',
          summary: '包含建议补充食材的菜谱。',
          servings: 2,
          cooking_time_minutes: 30,
          difficulty: '简单',
          ingredients: [
            { name: '番茄', amount: 1, unit: '个', note: null },
            { name: '土豆', amount: 2, unit: '个', note: '建议补充' },
          ],
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
          images: [],
          ingredients: [],
          confirmed_ingredients: [
            { name: '番茄', class_name: 'tomato', quantity: 1, unit: '个', source: 'model' },
          ],
        },
      }),
    })

    const wrapper = mount(FoodRecipePage, { props: { recipeId: 101 } })
    await flushPromises()

    expect(wrapper.find('[data-testid="recipe-suggestions"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('纳入本次食材')
  })

  it('runs the supplied recognition flow and emits the recipe contract after confirmation', async () => {
    setFoodApiClient({
      create: vi.fn().mockResolvedValue({ data: foodRecognitionFixtures.success }),
      confirm: vi.fn().mockImplementation(({ recognitionId, ingredients }) =>
        Promise.resolve({
          data: {
            recognition_id: recognitionId,
            confirmed_ingredients: ingredients,
          },
        })
      ),
    })
    setRecipeApiClient({
      create: vi.fn().mockResolvedValue({ data: recipeSuccessFixture }),
    })
    const wrapper = mount(FoodRecipePage)

    expect(wrapper.find('[data-testid="mock-scenario"]').exists()).toBe(false)
    await selectImages(wrapper, [makeImageFile('breakfast.jpg'), makeImageFile('vegetables.jpg')])
    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('图片已选好')
    expect(wrapper.find('[data-testid="selecting-state"]').text()).toContain('2 张图片')

    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请确认食材')
    const ingredientNames = wrapper
      .findAll('[data-testid="ingredient-name"]')
      .map((input) => input.element.value)
    expect(ingredientNames).toEqual(['番茄', '鸡蛋'])

    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('可以生成菜谱啦～')
    expect(wrapper.find('[data-testid="next-stage"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('食材都确认好啦，可以生成菜谱啦～')
    expect(wrapper.text()).not.toContain('recognition_id')
    expect(wrapper.text()).not.toContain('model_version')
    expect(wrapper.emitted('confirmed')?.[0][0]).toEqual({
      recognition_id: 12,
      confirmed_ingredients: [
        { name: '番茄', class_name: 'tomato', quantity: 1, unit: '个', source: 'model' },
        { name: '鸡蛋', class_name: 'egg', quantity: 1, unit: '个', source: 'model' },
      ],
    })

    await wrapper.find('[data-testid="next-stage"]').trigger('click')
    expect(wrapper.find('[data-testid="recipe-stage"]').isVisible()).toBe(true)
    expect(wrapper.find('[data-testid="recognition-stage"]').isVisible()).toBe(false)

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
    expect(routerMocks.replace).toHaveBeenLastCalledWith({
      query: { step: 'recipe', recipe_id: '101' },
    })
  })

  it('groups repeated detections into one confirmed ingredient', async () => {
    const repeated = {
      ...foodRecognitionFixtures.success,
      ingredients: [
        foodRecognitionFixtures.success.ingredients[0],
        {
          ...foodRecognitionFixtures.success.ingredients[0],
          candidate_id: 'img-1-det-repeat',
          image_index: 1,
          confidence: 0.62,
        },
      ],
    }
    const confirm = vi.fn().mockImplementation(({ recognitionId, ingredients }) =>
      Promise.resolve({
        data: { recognition_id: recognitionId, confirmed_ingredients: ingredients },
      })
    )
    setFoodApiClient({
      create: vi.fn().mockResolvedValue({ data: repeated }),
      confirm,
    })
    const wrapper = mount(FoodRecipePage)

    await selectImages(wrapper, [makeImageFile('one.jpg'), makeImageFile('two.jpg')])
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[data-testid="ingredient-name"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="ingredient-image-link"]').text()).toBe('识别来源')
    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')
    await flushPromises()

    expect(confirm.mock.calls[0][0].ingredients).toHaveLength(1)
    expect(confirm.mock.calls[0][0].ingredients[0].class_name).toBe('tomato')
  })

  it('can undo confirmation, cancel edits, and reconfirm updated ingredients', async () => {
    const confirm = vi.fn().mockImplementation(({ recognitionId, ingredients }) =>
      Promise.resolve({
        data: { recognition_id: recognitionId, confirmed_ingredients: ingredients },
      })
    )
    setFoodApiClient({
      create: vi.fn().mockResolvedValue({ data: foodRecognitionFixtures.success }),
      confirm,
    })
    const wrapper = mount(FoodRecipePage)

    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="ingredient-edit-confirmed"]').trigger('click')
    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('正在调整食材')
    expect(wrapper.find('[data-testid="next-stage"]').attributes('disabled')).toBeDefined()
    await wrapper.find('[data-testid="ingredient-name"]').setValue('改名番茄')
    await wrapper.find('[data-testid="ingredient-edit-cancel"]').trigger('click')
    expect(wrapper.find('[data-testid="ingredient-name"]').element.value).toBe('番茄')

    await wrapper.find('[data-testid="ingredient-edit-confirmed"]').trigger('click')
    await wrapper.find('[data-testid="ingredient-quantity"]').setValue(2)
    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalledTimes(2)
    expect(confirm.mock.calls[1][0].ingredients[0].quantity).toBe(2)
    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('可以生成菜谱啦～')
  })

  it('keeps the empty-recognition state visible and allows manual ingredient input', async () => {
    setFoodApiClient({
      create: vi.fn().mockResolvedValue({ data: foodRecognitionFixtures.empty }),
    })
    const wrapper = mount(FoodRecipePage)

    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请确认食材')
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ingredient-empty"]').exists()).toBe(true)

    await wrapper.find('[data-testid="ingredient-add"]').trigger('click')
    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')

    expect(wrapper.find('[data-testid="ingredient-errors"]').text()).toContain('不能为空')
  })

  it('shows the reserved 503 error state from the recognition API', async () => {
    setFoodApiClient({
      create: vi.fn().mockRejectedValue(makeFoodApiError(503, '食物识别服务暂不可用')),
    })
    const wrapper = mount(FoodRecipePage)

    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请重试')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('识别服务不可用')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('食物识别服务暂不可用')
  })

  it('shows reserved 413 and 415 error states from the recognition API', async () => {
    const create = vi
      .fn()
      .mockRejectedValueOnce(makeFoodApiError(413, '单张图片不能超过 10 MB'))
      .mockRejectedValueOnce(makeFoodApiError(415, '仅支持 JPG、JPEG 或 PNG'))
    setFoodApiClient({ create })
    const wrapper = mount(FoodRecipePage)

    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请重试')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('图片过大')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('单张图片不能超过 10 MB')

    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请重试')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('图片格式不支持')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('JPG、JPEG 或 PNG')
  })

  it('shows a network failure state when the recognition backend is unreachable', async () => {
    setFoodApiClient({
      create: vi.fn().mockRejectedValue(makeFoodApiError(0, '后端服务不可达')),
    })
    const wrapper = mount(FoodRecipePage)

    await selectImages(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请重试')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('网络连接失败')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('后端服务不可达')
  })
})
