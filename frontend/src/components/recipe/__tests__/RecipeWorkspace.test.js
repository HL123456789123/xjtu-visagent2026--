import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RecipeWorkspace from '../RecipeWorkspace.vue'

const RecipeCardStub = {
  name: 'RecipeCard',
  emits: ['retry', 'version-change'],
  template: `
    <div data-testid="recipe-card-stub">
      <button data-testid="retry-stub" @click="$emit('retry')">重试</button>
      <button data-testid="version-stub" @click="$emit('version-change', 1)">v1</button>
    </div>
  `,
}

const ChatPageStub = {
  name: 'ChatPage',
  props: ['recipeId'],
  emits: ['recipe-updated'],
  template: `
    <button data-testid="chat-stub" @click="$emit('recipe-updated', { recipe_id: recipeId })">
      对话
    </button>
  `,
}

function mountWorkspace(overrides = {}) {
  return mount(RecipeWorkspace, {
    props: {
      recipe: { recipe_id: 17, title: '番茄牛肉', version: 3 },
      preferences: {
        servings: 2,
        taste: '家常',
        max_time_minutes: 30,
        avoid_ingredients: [],
      },
      versions: [
        { version: 1, is_current: false },
        { version: 3, is_current: true },
      ],
      currentVersion: 3,
      selectedVersion: 3,
      ...overrides,
    },
    global: {
      stubs: {
        RecipeCard: RecipeCardStub,
        ChatPage: ChatPageStub,
      },
    },
  })
}

describe('RecipeWorkspace', () => {
  it('通过更新事件提交偏好和忌口输入', async () => {
    const wrapper = mountWorkspace()
    const inputs = wrapper.findAll('[data-testid="recipe-preferences"] input')

    await inputs[0].setValue('4')
    await inputs[3].setValue('香菜, 辣椒')

    expect(wrapper.emitted('update:preferences')?.at(-1)?.[0]).toMatchObject({
      servings: 4,
      taste: '家常',
    })
    expect(wrapper.emitted('update:avoidIngredientsText')?.at(-1)).toEqual(['香菜, 辣椒'])
  })

  it('查看旧版本时隐藏对话并可返回当前版本', async () => {
    const wrapper = mountWorkspace({
      selectedVersion: 1,
      isHistoricalVersion: true,
    })

    expect(wrapper.find('[data-testid="historical-version-note"]').text()).toContain('正在查看 v1')
    expect(wrapper.find('[data-testid="chat-stub"]').exists()).toBe(false)

    await wrapper.find('[data-testid="return-current-version"]').trigger('click')
    expect(wrapper.emitted('version-change')?.at(-1)).toEqual([3])
  })

  it('当前版本显示对话并透传菜谱更新', async () => {
    const wrapper = mountWorkspace()

    await wrapper.find('[data-testid="chat-stub"]').trigger('click')

    expect(wrapper.emitted('recipe-updated')?.at(-1)).toEqual([{ recipe_id: 17 }])
  })
})
