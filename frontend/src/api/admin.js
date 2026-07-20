import request from '@/utils/request'

export function getUserListApi(params = {}) {
  return request.get('/admin/users', { params })
}

export function getUserDetailApi(userId) {
  return request.get(`/admin/users/${userId}`)
}

export function updateUserApi(userId, data) {
  return request.put(`/admin/users/${userId}`, data)
}

export function setUserRoleApi(userId, role) {
  return request.put(`/admin/users/${userId}/role`, { role })
}

export function toggleUserStatusApi(userId, isActive) {
  return request.put(`/admin/users/${userId}/status`, { is_active: isActive })
}

export function resetUserPasswordApi(userId, newPassword) {
  return request.post(`/admin/users/${userId}/reset-password`, {
    new_password: newPassword,
  })
}

export function deleteUserApi(userId) {
  return request.delete(`/admin/users/${userId}`)
}
