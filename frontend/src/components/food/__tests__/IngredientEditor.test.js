import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import IngredientEditor from '../IngredientEditor.vue'
import {
  buildConfirmedIngredients,
  mapCandidatesToEditableIngredients,
  mergeConfirmedIngredientsWithCandidates,
  validateConfirmedIngredients,
} from '../ingredientEditorModel'

const candidates = [
  {
    candidate_id: 'img-0-det-1',
    image_index: 0,
    class_name: 'tomato',
    display_name: '番茄',
    confidence: 0.93,
    bbox: { x1: 0, y1: 0, x2: 10, y2: 10 },
    source: 'model',
  },
  {
    candidate_id: 'img-1-det-1',
    image_index: 1,
    class_name: 'egg',
    display_name: '鸡蛋',
    confidence: 0.88,
    bbox: { x1: 20, y1: 20, x2: 40, y2: 40 },
    source: 'model',
  },
]

const images = [
  { image_index: 0, image_url: '/api/files/food/12/0' },
  { image_index: 1, image_url: '/api/files/food/12/1' },
]

describe('ingredientEditorModel', () => {
  it('groups repeated model detections by class while preserving every source box', () => {
    const grouped = mapCandidatesToEditableIngredients([
      candidates[0],
      { ...candidates[0], candidate_id: 'img-0-det-2', confidence: 0.61 },
      { ...candidates[0], candidate_id: 'img-1-det-2', image_index: 1, confidence: 0.84 },
      candidates[1],
    ])

    expect(grouped).toHaveLength(2)
    expect(grouped[0]).toMatchObject({ class_name: 'tomato', confidence: 0.93, image_index: 0 })
    expect(grouped[0].sourceDetections).toHaveLength(3)
  })

  it('restores confirmed values without losing their raw detection sources', () => {
    const restored = mergeConfirmedIngredientsWithCandidates(candidates, [
      { name: '番茄', class_name: 'tomato', quantity: 2, unit: '个', source: 'model' },
    ])

    expect(restored).toHaveLength(1)
    expect(restored[0]).toMatchObject({ name: '番茄', quantity: 2, class_name: 'tomato' })
    expect(restored[0].sourceDetections).toHaveLength(1)
  })

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
      props: { modelValue: candidates, images },
    })

    expect(wrapper.findAll('[data-testid="ingredient-name"]')).toHaveLength(2)
    expect(wrapper.findAll('[data-testid="ingredient-image-link"]').map((link) => link.text()))
      .toEqual(['识别来源', '识别来源'])
    expect(wrapper.text()).toContain('93.0%')
    expect(wrapper.text()).toContain('模型识别')
    expect(wrapper.findAll('[data-testid="ingredient-image-link"]')).toHaveLength(2)
  })

  it('opens the matching source image for a model candidate', async () => {
    const wrapper = mount(IngredientEditor, {
      props: { modelValue: candidates, images },
      global: { stubs: { Teleport: true } },
    })

    await wrapper.find('[data-testid="ingredient-image-link"]').trigger('click')

    expect(wrapper.find('[data-testid="ingredient-preview"]').exists()).toBe(true)
    expect(wrapper.find('.ingredient-preview__figure img').attributes('src')).toBe(images[0].image_url)
    await wrapper.find('[data-testid="ingredient-preview-close"]').trigger('click')
    expect(wrapper.find('[data-testid="ingredient-preview"]').exists()).toBe(false)
  })

  it('shows one ingredient row and browses all locations for repeated detections', async () => {
    const repeatedTomatoes = [
      candidates[0],
      {
        ...candidates[0],
        candidate_id: 'img-1-det-2',
        image_index: 1,
        confidence: 0.72,
        bbox: { x1: 30, y1: 30, x2: 60, y2: 60 },
      },
    ]
    const wrapper = mount(IngredientEditor, {
      props: { modelValue: repeatedTomatoes, images },
      global: { stubs: { Teleport: true } },
    })

    expect(wrapper.findAll('[data-testid="ingredient-name"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="ingredient-image-link"]').text()).toBe('识别来源')

    await wrapper.find('[data-testid="ingredient-image-link"]').trigger('click')
    expect(wrapper.find('.ingredient-preview__figure img').attributes('src')).toBe(images[0].image_url)
    await wrapper.find('[data-testid="ingredient-preview-next"]').trigger('click')
    expect(wrapper.find('.ingredient-preview__figure img').attributes('src')).toBe(images[1].image_url)
  })

  it('allows a confirmed list to enter and cancel edit mode', async () => {
    const wrapper = mount(IngredientEditor, {
      props: { modelValue: candidates, confirmed: true },
    })

    expect(wrapper.find('[data-testid="ingredient-confirm"]').exists()).toBe(false)
    await wrapper.find('[data-testid="ingredient-edit-confirmed"]').trigger('click')
    expect(wrapper.emitted('edit-requested')).toHaveLength(1)

    await wrapper.setProps({ confirmed: false, editing: true })
    expect(wrapper.find('[data-testid="ingredient-confirm"]').text()).toBe('重新确认食材')
    await wrapper.find('[data-testid="ingredient-edit-cancel"]').trigger('click')
    expect(wrapper.emitted('cancel-edit')).toHaveLength(1)
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

    await wrapper.findAll('[data-testid="ingredient-name"]')[0].setValue('小番茄')
    await wrapper.findAll('[data-testid="ingredient-quantity"]')[0].setValue('2')
    await wrapper.find('[data-testid="ingredient-confirm"]').trigger('click')

    expect(wrapper.emitted('confirm')?.[0][0]).toEqual([
      {
        name: '小番茄',
        class_name: 'tomato',
        quantity: 2,
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
