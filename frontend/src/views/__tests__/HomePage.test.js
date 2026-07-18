import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import HomePage from '../HomePage.vue'
import { useUserStore } from '@/stores/user'

function mountHome(user) {
  setActivePinia(createPinia())
  const store = useUserStore()
  store.user = user
  return mount(HomePage, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        'router-link': { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

describe('HomePage', () => {
  it('offers only existing ordinary-user routes without fabricated statistics', () => {
    const wrapper = mountHome({ id: 1, username: 'viewer', roles: ['viewer'], permissions: [] })

    expect(wrapper.text()).toContain('开始食物识别')
    expect(wrapper.text()).toContain('菜谱对话')
    expect(wrapper.text()).toContain('个人中心')
    expect(wrapper.text()).not.toContain('管理后台')
  })

  it('offers the current administrator route only when user:list is present', () => {
    const wrapper = mountHome({ id: 2, username: 'manager', roles: ['admin'], permissions: ['user:list'] })

    expect(wrapper.text()).toContain('管理后台')
    expect(wrapper.html()).toContain('/admin/users')
  })
})
