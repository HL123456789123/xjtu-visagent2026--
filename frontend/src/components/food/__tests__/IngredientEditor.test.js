import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import IngredientEditor from '../IngredientEditor.vue'
import {
  buildConfirmedIngredients,
  validateConfirmedIngredients,
} from '../ingredientEditorModel'

const candidates = [
  { id: 'tomato-1', key: 'tomato', name: '番茄', confidence: 0.93, source: 'model' },
  { id: 'egg-1', key: 'egg', name: '鸡蛋', confidence: 0.88, source: 'model' },
]

describe('ingredientEditorModel', () => {
  it('builds confirmed ingredients with trimmed names', () => {
    expect(
      buildConfirmedIngredients([
        { key: 'tomato', name: ' 番茄 ', confidence: 0.9, source: 'model' },
      ])
    ).toEqual([
      {
        key: 'tomato',
        name: '番茄',
        confidence: 0.9,
        source: 'model',
      },
    ])
  })

  it('reports empty names and duplicate keys', () => {
    const result = validateConfirmedIngredients([
      { key: 'tomato', name: '番茄' },
      { key: 'tomato', name: '番茄' },
      { key: '', name: '' },
    ])

    expect(result.valid).toBe(false)
    expect(result.errors.join('\n')).toContain('重复')
    expect(result.errors.join('\n')).toContain('不能为空')
  })
})

describe('IngredientEditor', () => {
  it('renders confidence and source from recognition candidates', () => {
    const wrapper = mount(IngredientEditor, {
      props: { modelValue: candidates },
    })

    expect(wrapper.findAll('[data-testid="ingredient-name"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('93.0%')
    expect(wrapper.text()).toContain('模型识别')
  })

  it('supports deleting and manually adding ingredients', async () => {
    const wrapper = mount(IngredientEditor, {
      props: { modelValue: candidates },
    })

    await wrapper.find('[data-testid="ingredient-delete"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)[0]).toHaveLength(1)

    await wrapper.find('[data-testid="ingredient-add"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)[0]).toHaveLength(2)
  })

  it('blocks confirmation when an ingredient name is empty', async () => {
    const wrapper = mount(IngredientEditor, {
      props: {
        modelValue: [{ id: 'manual', key: '', name: '', confidence: null, source: 'manual' }],
      },
    })

    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')

    expect(wrapper.emitted('confirm')).toBeUndefined()
    expect(wrapper.find('[data-testid="ingredient-errors"]').text()).toContain('不能为空')
  })

  it('emits confirmed ingredients after validation passes', async () => {
    const wrapper = mount(IngredientEditor, {
      props: { modelValue: candidates },
    })

    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')

    expect(wrapper.emitted('confirm')?.[0][0]).toEqual([
      {
        key: 'tomato',
        name: '番茄',
        confidence: 0.93,
        source: 'model',
      },
      {
        key: 'egg',
        name: '鸡蛋',
        confidence: 0.88,
        source: 'model',
      },
    ])
  })
})
