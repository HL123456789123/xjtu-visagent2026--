import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProfilePage from '../ProfilePage.vue'
import { useUserStore } from '@/stores/user'
import { getUserInfoApi } from '@/api/auth'

vi.mock('@/api/auth', () => ({
  getUserInfoApi: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() },
}))

async function mountProfile(user) {
  setActivePinia(createPinia())
  const store = useUserStore()
  store.user = user
  getUserInfoApi.mockResolvedValue(user)

  const wrapper = mount(ProfilePage, {
    global: {
      stubs: {
        'el-avatar': { template: '<div><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-descriptions': { template: '<div><slot /></div>' },
        'el-descriptions-item': { template: '<div><slot /></div>' },
        'el-icon': { template: '<span><slot /></span>' },
        'el-button': { template: '<button><slot /></button>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ProfilePage role label', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows an admin as 管理员 instead of 普通用户', async () => {
    const wrapper = await mountProfile({
      id: 1,
      username: 'admin-user',
      roles: ['admin'],
      permissions: ['user:list'],
      is_active: true,
    })

    expect(wrapper.text()).toContain('管理员')
    expect(wrapper.text()).not.toContain('普通用户')
  })

  it('keeps the distinct super-admin and regular-user labels', async () => {
    const superAdmin = await mountProfile({
      id: 2,
      username: 'super-user',
      roles: ['super_admin'],
      permissions: ['*'],
      is_active: true,
    })
    const regularUser = await mountProfile({
      id: 3,
      username: 'regular-user',
      roles: ['user'],
      permissions: [],
      is_active: true,
    })

    expect(superAdmin.text()).toContain('超级管理员')
    expect(regularUser.text()).toContain('普通用户')
  })
})
