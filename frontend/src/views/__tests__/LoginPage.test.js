import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LoginPage from '../LoginPage.vue'

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ push: vi.fn() }),
  }
})

describe('LoginPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    window.matchMedia = vi.fn(() => ({ matches: false }))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('uses the current brand and rotates the food image every four seconds', async () => {
    const wrapper = shallowMount(LoginPage, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
          'router-link': { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('VisAgent · 拍食寻味')
    expect(wrapper.text()).toContain('开始你的专属美食之旅')

    const images = wrapper.findAll('.login-carousel__image')
    expect(images).toHaveLength(3)
    expect(images[0].classes()).toContain('is-active')

    await vi.advanceTimersByTimeAsync(4000)

    expect(images[1].classes()).toContain('is-active')
    wrapper.unmount()
  })
})
