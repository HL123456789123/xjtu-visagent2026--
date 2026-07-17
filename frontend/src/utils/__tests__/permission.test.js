import { describe, expect, it } from 'vitest'
import { hasPermission, isAdmin, isSuperAdmin } from '../permission'

describe('permission helpers', () => {
  it('treats promoted admin users as admins but not super admins', () => {
    const user = {
      username: 'manager',
      is_superuser: false,
      roles: ['admin'],
      permissions: ['user:manage'],
    }

    expect(isAdmin(user)).toBe(true)
    expect(isSuperAdmin(user)).toBe(false)
    expect(hasPermission(user, 'user:manage')).toBe(true)
  })

  it('treats super_admin as the super-administrator identity', () => {
    expect(isSuperAdmin({ username: 'admin', is_superuser: false, roles: ['admin'] })).toBe(false)
    expect(isSuperAdmin({ username: 'super', is_superuser: false, roles: ['super_admin'] })).toBe(true)
    expect(isSuperAdmin({ username: 'legacy', is_superuser: true, roles: ['admin'] })).toBe(true)
  })
})
