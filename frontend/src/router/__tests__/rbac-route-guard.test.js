import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import router from '../index'
import { useUserStore } from '@/stores/user'

function setAuthenticatedUser(user) {
  const store = useUserStore()
  store.user = user
  sessionStorage.setItem('visagent_verified', 'true')
  return store
}

describe('RBAC route guard', () => {
  beforeEach(async () => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
    await router.replace('/food-recipes')
  })

  it('blocks an ordinary user who enters an administrator URL directly', async () => {
    setAuthenticatedUser({
      id: 1,
      username: 'cook',
      roles: ['user'],
      permissions: ['food:recognize'],
    })

    await router.push('/admin/users')

    expect(router.currentRoute.value.name).toBe('NotFound')
  })

  it('allows a user with the current administrator permission to reach the route', async () => {
    setAuthenticatedUser({
      id: 2,
      username: 'manager',
      roles: ['admin'],
      permissions: ['user:list'],
    })

    await router.push('/admin/users')

    expect(router.currentRoute.value.name).toBe('UserManage')
  })

  it('uses the restored home page as the authenticated root route', async () => {
    setAuthenticatedUser({
      id: 1,
      username: 'cook',
      roles: ['user'],
      permissions: ['food:recognize'],
    })

    await router.push('/')

    expect(router.currentRoute.value.name).toBe('Home')
  })

  it('removes the legacy operator workbench route', async () => {
    setAuthenticatedUser({
      id: 3,
      username: 'operator',
      roles: ['operator'],
      permissions: ['training:task:view'],
    })

    await router.push('/admin/workbench')

    expect(router.currentRoute.value.name).toBe('NotFound')
  })

  it('redirects an unscoped chat route to history but keeps recipe-scoped chat available', async () => {
    setAuthenticatedUser({
      id: 4,
      username: 'cook',
      roles: ['user'],
      permissions: ['food:recognize'],
    })

    await router.push('/chat')

    expect(router.currentRoute.value.name).toBe('History')

    await router.push('/chat?recipe_id=42')

    expect(router.currentRoute.value.name).toBe('Chat')
  })
})
