/**
 * 权限判断工具函数
 * 用于前端页面和组件的权限控制
 */

/**
 * 判断用户是否拥有指定权限
 * @param {Object} user - 用户对象
 * @param {string} permissionCode - 权限编码，如 'user:manage'
 * @returns {boolean}
 */
export function hasPermission(user, permissionCode) {
  if (!user) return false
  // 超级管理员拥有所有权限
  if (isSuperAdmin(user)) return true
  // 检查权限列表（后端 /me 接口返回 permissions 字段）
  const permissions = user.permissions || []
  // '*' 表示拥有所有权限（超级管理员标记）
  if (permissions.includes('*')) return true
  return permissions.includes(permissionCode)
}

/**
 * 判断用户是否拥有任一权限
 * @param {Object} user - 用户对象
 * @param {string[]} codes - 权限编码数组
 * @returns {boolean}
 */
export function hasAnyPermission(user, codes) {
  if (!user || !codes || codes.length === 0) return false
  return codes.some((code) => hasPermission(user, code))
}

/**
 * 判断用户是否拥有指定角色
 * @param {Object} user - 用户对象（需包含 roles 字段）
 * @param {string} roleName - 角色标识，如 'admin'
 * @returns {boolean}
 */
export function hasRole(user, roleName) {
  if (!user || !user.roles) return false
  return user.roles.includes(roleName)
}

/**
 * 判断用户是否为管理员（admin 或 super_admin）
 * @param {Object} user - 用户对象
 * @returns {boolean}
 */
export function isAdmin(user) {
  return isSuperAdmin(user) || hasRole(user, 'admin')
}

/**
 * 判断用户是否为超级管理员
 * @param {Object} user - 用户对象
 * @returns {boolean}
 */
export function isSuperAdmin(user) {
  return Boolean(user?.is_superuser) || hasRole(user, 'super_admin')
}
