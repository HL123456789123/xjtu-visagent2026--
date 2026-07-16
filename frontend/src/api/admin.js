/**
 * 系统管理 API
 * 用户管理、角色管理、权限管理
 */
import request from '@/utils/request'

// ══════════════════════════════════════════════════════════════
// 一、用户管理
// ══════════════════════════════════════════════════════════════

/**
 * 获取用户列表
 * @param {Object} params - { page, page_size, keyword, is_active }
 */
export function getUserListApi(params) {
  return request.get('/admin/users', { params })
}

/**
 * 获取用户详情
 * @param {number} userId
 */
export function getUserDetailApi(userId) {
  return request.get(`/admin/users/${userId}`)
}

/**
 * 管理员修改用户信息
 * @param {number} userId
 * @param {Object} data - { email, phone, is_active, is_superuser }
 */
export function updateUserApi(userId, data) {
  return request.put(`/admin/users/${userId}`, data)
}

/**
 * 分配用户角色
 * @param {number} userId
 * @param {Object} data - { role_ids: number[] }
 */
export function assignUserRolesApi(userId, data) {
  return request.put(`/admin/users/${userId}/roles`, data)
}

/**
 * 启用/禁用用户
 * @param {number} userId
 * @param {Object} data - { is_active: boolean }
 */
export function toggleUserStatusApi(userId, data) {
  return request.put(`/admin/users/${userId}/status`, data)
}

/**
 * 删除用户
 * @param {number} userId
 */
export function deleteUserApi(userId) {
  return request.delete(`/admin/users/${userId}`)
}

// ══════════════════════════════════════════════════════════════
// 二、角色管理
// ══════════════════════════════════════════════════════════════

/**
 * 获取角色列表
 */
export function getRoleListApi() {
  return request.get('/admin/roles')
}

/**
 * 获取角色详情
 * @param {number} roleId
 */
export function getRoleDetailApi(roleId) {
  return request.get(`/admin/roles/${roleId}`)
}

/**
 * 创建角色
 * @param {Object} data - { name, display_name, description, permission_codes }
 */
export function createRoleApi(data) {
  return request.post('/admin/roles', data)
}

/**
 * 更新角色
 * @param {number} roleId
 * @param {Object} data - { display_name, description, permission_codes }
 */
export function updateRoleApi(roleId, data) {
  return request.put(`/admin/roles/${roleId}`, data)
}

/**
 * 删除角色
 * @param {number} roleId
 */
export function deleteRoleApi(roleId) {
  return request.delete(`/admin/roles/${roleId}`)
}

/**
 * 分配角色权限
 * @param {number} roleId
 * @param {Object} data - { permission_codes: string[] }
 */
export function assignRolePermissionsApi(roleId, data) {
  return request.put(`/admin/roles/${roleId}/permissions`, data)
}

// ══════════════════════════════════════════════════════════════
// 三、权限管理
// ══════════════════════════════════════════════════════════════

/**
 * 获取所有权限列表（按模块分组）
 */
export function getPermissionListApi() {
  return request.get('/admin/permissions')
}
