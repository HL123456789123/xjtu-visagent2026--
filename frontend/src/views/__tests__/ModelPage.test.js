import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  activateFoodModel: vi.fn(),
  deleteFoodModel: vi.fn(),
  getFoodModels: vi.fn(),
  rollbackFoodModel: vi.fn(),
  uploadFoodModel: vi.fn(),
}))

vi.mock('@/api/foodModel', () => api)
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue() },
}))

import ModelPage from '../ModelPage.vue'

describe('ModelPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getFoodModels.mockResolvedValue({
      data: {
        active_model_id: 4,
        items: [{
          model_id: 4,
          name: 'Food 101',
          version: 'food-101-v1',
          task: 'classify',
          status: 'active',
          is_active: true,
          available: true,
          class_count: 101,
          classes: [],
          weight_sha256: 'a'.repeat(64),
          classes_sha256: 'b'.repeat(64),
          created_at: '2026-07-20T10:00:00+08:00',
        }],
      },
    })
  })

  it('shows the active Food model and its real task without internal paths', async () => {
    const wrapper = mount(ModelPage, {
      global: {
        directives: { loading: {} },
        stubs: {
          ElTable: { template: '<div><slot /></div>' },
          ElTableColumn: { template: '<div />' },
        },
      },
    })
    await flushPromises()

    expect(api.getFoodModels).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Food 101')
    expect(wrapper.text()).toContain('整图分类')
    expect(wrapper.text()).toContain('101 个类别')
    expect(wrapper.text()).not.toContain('weights_path')
  })
})
