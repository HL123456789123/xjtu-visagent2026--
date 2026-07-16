import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import IngredientEditor from '../IngredientEditor.vue'
import {
  buildConfirmedIngredients,
  validateConfirmedIngredients,
} from '../ingredientEditorModel'

const candidates = [
  {
    candidate_id: 'det-1',
    image_index: 0,
    class_name: 'tomato',
    display_name: '番茄',
    confidence: 0.93,
    bbox: { x1: 0, y1: 0, x2: 10, y2: 10 },
    source: 'model',
  },
  {
    candidate_id: 'det-2',
    image_index: 1,
    class_name: 'egg',
    display_name: '鸡蛋',
    confidence: 0.88,
    bbox: { x1: 20, y1: 20, x2: 40, y2: 40 },
    source: 'model',
  },
]

describe('ingredientEditorModel', () => {
  it('builds confirmed ingredients with trimmed names', () => {
    expect(
      buildConfirmedIngredients([
        {
          class_name: 'tomato',
          name: ' 番茄 ',
          quantity: 2,
          unit: ' 个 ',
          source: 'model',
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

  it('reports invalid confirmed ingredient fields', () => {
    const result = validateConfirmedIngredients([
      { name: '', class_name: null, quantity: 0, unit: '', source: 'manual' },
      { name: '番茄', class_name: 'tomato', quantity: 1, unit: '个', source: 'unknown' },
    ])

    expect(result.valid).toBe(false)
    expect(result.errors.join('\n')).toContain('不能为空')
    expect(result.errors.join('\n')).toContain('数量必须大于 0')
    expect(result.errors.join('\n')).toContain('来源无效')
  })
})

describe('IngredientEditor', () => {
  it('renders confidence and source from recognition candidates', () => {
    const wrapper = mount(IngredientEditor, {
      props: { modelValue: candidates },
    })

    expect(wrapper.findAll('[data-testid="ingredient-name"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('图 1')
    expect(wrapper.text()).toContain('图 2')
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
        modelValue: [{ draftId: 'manual', name: '', class_name: null, quantity: 1, unit: '个', source: 'manual' }],
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
        name: '番茄',
        class_name: 'tomato',
        quantity: 1,
        unit: '个',
        source: 'model',
      },
      {
        name: '鸡蛋',
        class_name: 'egg',
        quantity: 1,
        unit: '个',
        source: 'model',
      },
    ])
  })
})
