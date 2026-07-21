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
    const wrapper = mountHome({ id: 1, username: 'viewer', roles: ['user'], permissions: [] })

    expect(wrapper.text()).toContain('VisAgent · 拍食寻味')
    expect(wrapper.text()).toContain('拍下手边的新鲜食材，一键收获美味菜谱')
    expect(wrapper.text()).toContain('开始识别食材')
    expect(wrapper.text()).toContain('历史记录')
    expect(wrapper.text()).toContain('数据看板')
    expect(wrapper.text()).toContain('个人中心')
    expect(wrapper.text()).not.toContain('管理后台')
    expect(wrapper.findAll('.home-hero__image')).toHaveLength(3)
    expect(wrapper.find('.home-shortcuts__heading').text()).toContain('继续探索')
    wrapper.unmount()
  })

  it('offers the two real management entries only to a fixed administrator role', () => {
    const wrapper = mountHome({ id: 2, username: 'manager', roles: ['admin'], permissions: ['user:list'] })

    expect(wrapper.text()).toContain('模型管理')
    expect(wrapper.text()).toContain('用户管理')
    expect(wrapper.html()).toContain('/admin/models')
    expect(wrapper.html()).toContain('/admin/users')
    expect(wrapper.html()).not.toContain('/admin/workbench')
    wrapper.unmount()
  })
})
