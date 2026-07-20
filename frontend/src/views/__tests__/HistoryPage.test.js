import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getRecipeHistory: vi.fn(),
  getRecipeVersion: vi.fn(),
  getRecipeVersions: vi.fn(),
  restoreRecipeVersion: vi.fn(),
}))
const push = vi.hoisted(() => vi.fn())

vi.mock('@/api/recipe', () => api)
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue() },
}))

import HistoryPage from '../HistoryPage.vue'

describe('HistoryPage recipe versions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getRecipeHistory.mockResolvedValue({
      data: {
        total: 1,
        items: [{
          recipe_id: 17,
          title: '番茄牛肉',
          version: 2,
          confirmed_ingredients: [{ name: '番茄' }, { name: '牛肉' }],
          updated_at: '2026-07-20T10:00:00+08:00',
          latest_session: { message_count: 4 },
        }],
      },
    })
    api.getRecipeVersions.mockResolvedValue({
      data: {
        current_version: 2,
        versions: [
          { version: 2, change_type: 'chat_update', change_reason: '少放油', source_message: '改成三人份并且少放油', is_current: true, created_at: '2026-07-20T10:00:00+08:00' },
          { version: 1, change_type: 'generated', change_reason: '初次生成菜谱', is_current: false, created_at: '2026-07-20T09:00:00+08:00' },
        ],
      },
    })
    api.restoreRecipeVersion.mockResolvedValue({ data: { recipe_id: 17, version: 3 } })
  })

  it('expands immutable versions and restores an old version as a new one', async () => {
    const wrapper = mount(HistoryPage)
    await flushPromises()

    expect(wrapper.text()).toContain('番茄牛肉')
    await wrapper.find('[data-testid="history-versions"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('v2 · 对话修改')
    expect(wrapper.text()).toContain('v1 · 初次生成')
    expect(wrapper.text()).toContain('你当时说：改成三人份并且少放油')
    await wrapper.find('[data-testid="history-restore-version"]').trigger('click')
    await flushPromises()

    expect(api.restoreRecipeVersion).toHaveBeenCalledWith(17, 1)
    expect(api.getRecipeVersions).toHaveBeenCalledTimes(2)
  })
})
