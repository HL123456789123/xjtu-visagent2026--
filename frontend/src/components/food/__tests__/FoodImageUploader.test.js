import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FoodImageUploader from '../FoodImageUploader.vue'

describe('FoodImageUploader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn((file) => `blob:${file.name}`),
      revokeObjectURL: vi.fn(),
    })
  })

  it('accepts one JPG image and emits preview metadata', () => {
    const wrapper = mount(FoodImageUploader)
    const file = new File(['image'], 'meal.jpg', { type: 'image/jpeg' })

    const selected = wrapper.vm.selectFile(file)

    expect(selected).toBe(true)
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([[file]])
    expect(wrapper.emitted('selected')?.[0]).toEqual([[file]])
    expect(wrapper.emitted('preview-change')?.[0]).toEqual([['blob:meal.jpg']])
  })

  it('rejects non JPG/PNG files', async () => {
    const wrapper = mount(FoodImageUploader)
    const file = new File(['text'], 'notes.txt', { type: 'text/plain' })

    const selected = wrapper.vm.selectFile(file)
    await flushPromises()

    expect(selected).toBe(false)
    expect(wrapper.emitted('validation-error')?.[0][0]).toContain('JPG')
    expect(wrapper.find('[data-testid="food-image-error"]').text()).toContain('JPG')
  })

  it('rejects images over the configured size limit', () => {
    const wrapper = mount(FoodImageUploader, {
      props: { maxSizeMB: 1 },
    })
    const file = new File([new Uint8Array(1024 * 1024 + 1)], 'large.png', {
      type: 'image/png',
    })

    const selected = wrapper.vm.selectFile(file)

    expect(selected).toBe(false)
    expect(wrapper.emitted('validation-error')?.[0][0]).toContain('1 MB')
  })

  it('accepts multiple dropped images as one recognition batch', async () => {
    const wrapper = mount(FoodImageUploader)
    const first = new File(['image'], 'meal-one.jpg', { type: 'image/jpeg' })
    const second = new File(['image'], 'meal-two.png', { type: 'image/png' })

    await wrapper.find('[data-testid="food-image-dropzone"]').trigger('drop', {
      dataTransfer: {
        files: [first, second],
      },
    })

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([[first, second]])
    expect(wrapper.emitted('selected')?.[0]).toEqual([[first, second]])
    expect(wrapper.emitted('preview-change')?.[0]).toEqual([['blob:meal-one.jpg', 'blob:meal-two.png']])
    expect(wrapper.findAll('.food-uploader__preview img')).toHaveLength(2)
  })
})
