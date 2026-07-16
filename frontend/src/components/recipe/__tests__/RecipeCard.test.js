import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RecipeCard from '../RecipeCard.vue'
import { recipeSuccessFixture, recipeEmptyFixture } from '@/fixtures/recipe'

describe('RecipeCard', () => {
  it('renders loading state', () => {
    const wrapper = mount(RecipeCard, {
      props: { recipe: {}, loading: true },
    })

    expect(wrapper.find('[data-testid="recipe-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="recipe-card"]').exists()).toBe(true)
  })

  it('renders 503 error with retry button', () => {
    const wrapper = mount(RecipeCard, {
      props: {
        recipe: {},
        error: { code: 'LLM_UNAVAILABLE', message: '智能服务暂时不可用' },
      },
    })

    expect(wrapper.find('[data-testid="recipe-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('智能服务不可用')
    expect(wrapper.find('[data-testid="recipe-retry"]').exists()).toBe(true)
  })

  it('renders 404 error without retry button', () => {
    const wrapper = mount(RecipeCard, {
      props: {
        recipe: {},
        error: { code: 'RECIPE_NOT_FOUND', message: '菜谱不存在' },
      },
    })

    expect(wrapper.find('[data-testid="recipe-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('菜谱不存在')
    expect(wrapper.find('[data-testid="recipe-retry"]').exists()).toBe(false)
  })

  it('emits retry when retry button clicked', async () => {
    const wrapper = mount(RecipeCard, {
      props: {
        recipe: {},
        error: { status: 503, code: 'LLM_UNAVAILABLE', message: '智能服务暂时不可用' },
      },
    })

    await wrapper.find('[data-testid="recipe-retry"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('renders empty state when no recipe', () => {
    const wrapper = mount(RecipeCard, {
      props: { recipe: {} },
    })

    expect(wrapper.find('[data-testid="recipe-empty"]').exists()).toBe(true)
  })

  it('renders full recipe with all V1 fields', () => {
    const wrapper = mount(RecipeCard, {
      props: { recipe: recipeSuccessFixture },
    })

    // Title
    expect(wrapper.find('[data-testid="recipe-title"]').text()).toBe('番茄炒蛋')
    expect(wrapper.find('[data-testid="recipe-version"]').text()).toBe('v1')
    expect(wrapper.find('[data-testid="recipe-summary"]').text()).toContain('家常快手菜')

    // Meta
    expect(wrapper.find('[data-testid="recipe-servings"]').text()).toContain('2')
    expect(wrapper.find('[data-testid="recipe-cooking-time"]').text()).toContain('20')
    expect(wrapper.find('[data-testid="recipe-difficulty"]').text()).toBe('简单')

    // Ingredients
    const ingredients = wrapper.findAll('[data-testid="ingredient-item"]')
    expect(ingredients).toHaveLength(3)
    expect(wrapper.find('[data-testid="ingredient-name"]').text()).toBe('番茄')
    expect(wrapper.find('[data-testid="ingredient-amount"]').text()).toContain('2')

    // Steps
    const steps = wrapper.findAll('[data-testid="step-item"]')
    expect(steps).toHaveLength(4)
    expect(wrapper.find('[data-testid="step-description"]').text()).toContain('番茄洗净切块')

    // Nutrition
    expect(wrapper.find('[data-testid="nutrition-calories"]').text()).toContain('280')
    expect(wrapper.find('[data-testid="nutrition-protein"]').text()).toContain('16.5')
    expect(wrapper.find('[data-testid="nutrition-fat"]').text()).toContain('15.2')
    expect(wrapper.find('[data-testid="nutrition-carbohydrates"]').text()).toContain('18.4')

    // Disclaimer (固定显示)
    expect(wrapper.find('[data-testid="nutrition-disclaimer"]').text()).toContain('营养数据由模型估算')
  })

  it('renders empty ingredient list message', () => {
    const wrapper = mount(RecipeCard, {
      props: {
        recipe: { ...recipeSuccessFixture, ingredients: [] },
      },
    })

    expect(wrapper.find('[data-testid="ingredient-empty"]').exists()).toBe(true)
  })

  it('renders empty steps message', () => {
    const wrapper = mount(RecipeCard, {
      props: {
        recipe: { ...recipeSuccessFixture, steps: [] },
      },
    })

    expect(wrapper.find('[data-testid="step-empty"]').exists()).toBe(true)
  })

  it('emits open-chat with recipe_id when chat button clicked', async () => {
    const wrapper = mount(RecipeCard, {
      props: { recipe: recipeSuccessFixture },
    })

    await wrapper.find('[data-testid="recipe-open-chat"]').trigger('click')
    expect(wrapper.emitted('open-chat')).toBeTruthy()
    expect(wrapper.emitted('open-chat')[0][0]).toEqual({ recipe_id: 101 })
  })

  it('renders empty fixture without errors', () => {
    const wrapper = mount(RecipeCard, {
      props: { recipe: recipeEmptyFixture },
    })

    // Empty fixture has no recipe_id or title, so should show empty state
    expect(wrapper.find('[data-testid="recipe-empty"]').exists()).toBe(true)
  })

  it('disables chat button when recipe_id is missing', () => {
    const wrapper = mount(RecipeCard, {
      props: {
        recipe: { title: 'test', ingredients: [], steps: [] },
      },
    })

    const btn = wrapper.find('[data-testid="recipe-open-chat"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })
})
