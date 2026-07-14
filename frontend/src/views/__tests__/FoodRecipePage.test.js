import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FoodImageUploader from '@/components/food/FoodImageUploader.vue'
import FoodRecipePage from '../FoodRecipePage.vue'

function makeImageFile(name = 'meal.jpg') {
  return new File(['image'], name, { type: 'image/jpeg' })
}

async function selectImage(wrapper) {
  const uploader = wrapper.findComponent(FoodImageUploader)
  uploader.vm.selectFile(makeImageFile())
  await flushPromises()
}

describe('FoodRecipePage', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:food-preview'),
      revokeObjectURL: vi.fn(),
    })
  })

  it('runs the success mock flow and emits the recipe contract after confirmation', async () => {
    const wrapper = mount(FoodRecipePage)

    await selectImage(wrapper)
    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('selecting')

    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('recognized')
    const ingredientNames = wrapper
      .findAll('[data-testid="ingredient-name"]')
      .map((input) => input.element.value)
    expect(ingredientNames).toEqual(['番茄', '鸡蛋', '菠菜'])

    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('confirmed')
    expect(wrapper.find('[data-testid="summary-recognition-id"]').text()).toBe('rec_mock_day1_001')
    expect(wrapper.find('[data-testid="summary-confirmed-count"]').text()).toBe('3 项')
    expect(wrapper.emitted('confirmed')?.[0][0]).toMatchObject({
      recognition_id: 'rec_mock_day1_001',
      confirmed_ingredients: [
        { key: 'tomato', name: '番茄' },
        { key: 'egg', name: '鸡蛋' },
        { key: 'spinach', name: '菠菜' },
      ],
    })

    await wrapper.find('[data-testid="recipe-generate"]').trigger('click')
    expect(wrapper.emitted('recipe-requested')?.[0][0]).toMatchObject({
      recognition_id: 'rec_mock_day1_001',
      confirmed_ingredients: [
        { key: 'tomato', name: '番茄' },
        { key: 'egg', name: '鸡蛋' },
        { key: 'spinach', name: '菠菜' },
      ],
    })
  })

  it('keeps the empty-recognition state visible and allows manual ingredient input', async () => {
    const wrapper = mount(FoodRecipePage)

    await wrapper.find('[data-testid="mock-scenario"]').setValue('empty')
    await selectImage(wrapper)
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
    await selectImage(wrapper)
    await wrapper.find('[data-testid="start-recognition"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('error')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('识别服务不可用')
    expect(wrapper.find('[data-testid="error-state"]').text()).toContain('食物识别服务暂不可用')
  })
})
