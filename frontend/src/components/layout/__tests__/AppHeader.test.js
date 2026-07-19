import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const push = vi.fn()
const route = reactive({ path: '/food-recipes' })

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => route,
    useRouter: () => ({ push }),
  }
})

vi.mock('element-plus', () => ({
  ElMessageBox: { confirm: vi.fn() },
}))

import { ElMessageBox } from 'element-plus'
import AppHeader from '../AppHeader.vue'
import { useUserStore } from '@/stores/user'

const DropdownStub = {
  emits: ['command'],
  template: `
    <div>
      <button data-testid="emit-logout" type="button" @click="$emit('command', 'logout')">logout</button>
      <slot />
      <slot name="dropdown" />
    </div>
  `,
}

function mountHeader(user) {
  setActivePinia(createPinia())
  const store = useUserStore()
  store.user = user

  const wrapper = mount(AppHeader, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        'router-link': { props: ['to'], template: '<a :href="to"><slot /></a>' },
        ElAvatar: { template: '<span><slot /></span>' },
        'el-avatar': { template: '<span><slot /></span>' },
        ElDropdown: DropdownStub,
        'el-dropdown': DropdownStub,
        ElDropdownMenu: { template: '<div><slot /></div>' },
        'el-dropdown-menu': { template: '<div><slot /></div>' },
        ElDropdownItem: { template: '<button><slot /></button>' },
        'el-dropdown-item': { template: '<button><slot /></button>' },
        ElIcon: { template: '<i><slot /></i>' },
        'el-icon': { template: '<i><slot /></i>' },
      },
    },
  })

  return { store, wrapper }
}

describe('AppHeader top navigation', () => {
  beforeEach(() => {
    localStorage.clear()
    push.mockReset()
    route.path = '/food-recipes'
    ElMessageBox.confirm.mockReset()
  })

  it('shows current navigation to a signed-in ordinary user without an admin entry', () => {
    const { wrapper } = mountHeader({
      id: 1,
      username: 'viewer',
      roles: ['viewer'],
      permissions: [],
    })

    expect(wrapper.find('[data-testid="top-nav"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-home"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-food"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-chat"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="nav-history"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-dashboard"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-profile"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-admin"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="nav-food"]').classes()).toContain('top-nav__item--active')
  })

  it('shows the current administrator entry only when the current permissions allow it', async () => {
    const { wrapper } = mountHeader({
      id: 2,
      username: 'manager',
      roles: ['admin'],
      permissions: ['user:list', 'role:list'],
    })

    expect(wrapper.find('[data-testid="nav-admin"]').text()).toBe('模型工作台')
    await wrapper.find('[data-testid="nav-admin"]').trigger('click')
    expect(push).toHaveBeenCalledWith('/admin/workbench')
  })

  it('keeps the compact navigation operable', async () => {
    const { wrapper } = mountHeader({ id: 1, username: 'viewer', roles: ['viewer'], permissions: [] })

    expect(wrapper.find('[data-testid="top-nav"]').classes()).not.toContain('top-nav--open')
    await wrapper.find('[data-testid="topnav-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="top-nav"]').classes()).toContain('top-nav--open')
  })

  it('keeps logout available from the user menu', async () => {
    const { store, wrapper } = mountHeader({ id: 1, username: 'viewer', roles: ['viewer'], permissions: [] })
    store.logout = vi.fn().mockResolvedValue()
    ElMessageBox.confirm.mockResolvedValue()

    await wrapper.find('[data-testid="emit-logout"]').trigger('click')
    await flushPromises()

    expect(store.logout).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith('/login')
  })
})
