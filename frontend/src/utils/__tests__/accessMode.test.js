import { beforeEach, describe, expect, it } from 'vitest'
import {
  ACCESS_MODE_KEY,
  ACCESS_MODES,
  clearStoredAccessMode,
  getStoredAccessMode,
  isManagerPath,
  normalizeAccessMode,
  setStoredAccessMode,
} from '../accessMode'

describe('access mode helpers', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('normalizes unknown mode values to user mode', () => {
    expect(normalizeAccessMode(ACCESS_MODES.ADMIN)).toBe(ACCESS_MODES.ADMIN)
    expect(normalizeAccessMode('guest')).toBe(ACCESS_MODES.USER)
    expect(normalizeAccessMode()).toBe(ACCESS_MODES.USER)
  })

  it('stores and clears the selected access mode in the current session', () => {
    expect(getStoredAccessMode()).toBe(ACCESS_MODES.USER)

    setStoredAccessMode(ACCESS_MODES.ADMIN)
    expect(sessionStorage.getItem(ACCESS_MODE_KEY)).toBe(ACCESS_MODES.ADMIN)
    expect(getStoredAccessMode()).toBe(ACCESS_MODES.ADMIN)

    clearStoredAccessMode()
    expect(getStoredAccessMode()).toBe(ACCESS_MODES.USER)
  })

  it('identifies routes reserved for the manager entry', () => {
    expect(isManagerPath('/training')).toBe(true)
    expect(isManagerPath('/dashboard?tab=today')).toBe(true)
    expect(isManagerPath('/models')).toBe(true)
    expect(isManagerPath('/datasets')).toBe(true)
    expect(isManagerPath('/admin/users')).toBe(true)
    expect(isManagerPath('/food-recipes')).toBe(false)
  })
})
