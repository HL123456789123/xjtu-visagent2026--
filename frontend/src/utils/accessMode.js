export const ACCESS_MODE_KEY = 'visagent_access_mode'
export const MANAGER_ACCESS_PERMISSION = 'system:manager_access'

export const ACCESS_MODES = {
  USER: 'user',
  ADMIN: 'admin',
}

export function normalizeAccessMode(mode) {
  return mode === ACCESS_MODES.ADMIN ? ACCESS_MODES.ADMIN : ACCESS_MODES.USER
}

export function getStoredAccessMode() {
  if (typeof sessionStorage === 'undefined') return ACCESS_MODES.USER
  return normalizeAccessMode(sessionStorage.getItem(ACCESS_MODE_KEY))
}

export function setStoredAccessMode(mode) {
  const normalizedMode = normalizeAccessMode(mode)
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(ACCESS_MODE_KEY, normalizedMode)
  }
  return normalizedMode
}

export function clearStoredAccessMode() {
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(ACCESS_MODE_KEY)
  }
}

export function isManagerPath(path) {
  if (!path || typeof path !== 'string') return false
  return (
    path.startsWith('/training')
    || path.startsWith('/dashboard')
    || path.startsWith('/models')
    || path.startsWith('/datasets')
    || path.startsWith('/admin')
  )
}
