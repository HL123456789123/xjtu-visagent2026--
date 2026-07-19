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
      username: 'viewer',
      roles: ['viewer'],
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

  it('allows an operator to reach the model workbench without granting user administration', async () => {
    setAuthenticatedUser({
      id: 3,
      username: 'operator',
      roles: ['operator'],
      permissions: ['training:task:view'],
    })

    await router.push('/admin/workbench')

    expect(router.currentRoute.value.name).toBe('AdminWorkbench')
  })

  it('redirects an unscoped chat route to history but keeps recipe-scoped chat available', async () => {
    setAuthenticatedUser({
      id: 4,
      username: 'cook',
      roles: ['viewer'],
      permissions: ['food:recognize'],
    })

    await router.push('/chat')

    expect(router.currentRoute.value.name).toBe('History')

    await router.push('/chat?recipe_id=42')

    expect(router.currentRoute.value.name).toBe('Chat')
  })
})
