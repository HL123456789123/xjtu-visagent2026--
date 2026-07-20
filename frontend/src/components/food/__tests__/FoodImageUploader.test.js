import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FoodImageUploader from '../FoodImageUploader.vue'

describe('FoodImageUploader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn((file) => `blob:${file.name}`),
      revokeObjectURL: vi.fn(),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
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

  it('marks the native file input as multi-image capable', () => {
    const wrapper = mount(FoodImageUploader)

    expect(wrapper.find('[data-testid="food-image-input"]').attributes('multiple')).toBeDefined()
    expect(wrapper.text()).toContain('1 至 8 张')
    expect(wrapper.text()).toContain('单图不超过 10 MB')
    expect(wrapper.text()).toContain('整批不超过 50 MB')
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

  it('rejects images over the default 10 MB limit', () => {
    const wrapper = mount(FoodImageUploader)
    const file = new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.png', {
      type: 'image/png',
    })

    const selected = wrapper.vm.selectFile(file)

    expect(selected).toBe(false)
    expect(wrapper.emitted('validation-error')?.[0][0]).toContain('10 MB')
  })

  it('accepts eight images and rejects a ninth image in one batch', () => {
    const wrapper = mount(FoodImageUploader)
    const files = Array.from({ length: 9 }, (_, index) =>
      new File(['image'], `meal-${index + 1}.jpg`, { type: 'image/jpeg' })
    )

    expect(wrapper.vm.selectFiles(files.slice(0, 8))).toBe(true)
    const selected = wrapper.vm.selectFiles(files)

    expect(selected).toBe(false)
    expect(wrapper.emitted('validation-error')?.[0][0]).toContain('最多上传 8 张')
  })

  it('rejects batches over the default 50 MB limit', () => {
    const wrapper = mount(FoodImageUploader, {
      props: { maxSizeMB: 20 },
    })
    const files = Array.from({ length: 5 }, (_, index) =>
      new File([new Uint8Array(11 * 1024 * 1024)], `meal-${index + 1}.jpg`, {
        type: 'image/jpeg',
      })
    )

    const selected = wrapper.vm.selectFiles(files)

    expect(selected).toBe(false)
    expect(wrapper.emitted('validation-error')?.[0][0]).toContain('50 MB')
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

  it('removes a single selected image from the preview list', async () => {
    const wrapper = mount(FoodImageUploader)
    const first = new File(['image'], 'meal-one.jpg', { type: 'image/jpeg' })
    const second = new File(['image'], 'meal-two.png', { type: 'image/png' })

    wrapper.vm.selectFiles([first, second])
    await wrapper.setProps({ modelValue: [first, second] })
    await wrapper.findAll('[data-testid="food-image-remove"]')[0].trigger('click')

    expect(wrapper.emitted('update:modelValue')?.at(-1)[0]).toEqual([second])
    expect(wrapper.emitted('preview-change')?.at(-1)[0]).toEqual(['blob:meal-two.png'])
  })
})
