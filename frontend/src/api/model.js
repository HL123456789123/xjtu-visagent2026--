/**
 * 模型管理相关 API
 */
import request from '@/utils/request'

/**
 * 获取模型列表
 * @param {Object} params - { category, status, page, page_size }
 */
export function getModelsApi(params) {
  return request.get('/models', { params })
}

/**
 * 创建模型
 * @param {Object} data - { name, description, base_architecture, category, class_names, class_names_cn }
 */
export function createModelApi(data) {
  const formData = new FormData()
  Object.keys(data).forEach(key => {
    if (data[key] !== undefined && data[key] !== null) {
      formData.append(key, typeof data[key] === 'object' ? JSON.stringify(data[key]) : data[key])
    }
  })
  return request.post('/models', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 获取模型详情（含版本列表和关联场景）
 * @param {number} modelId
 */
export function getModelApi(modelId) {
  return request.get(`/models/${modelId}`)
}

/**
 * 更新模型
 * @param {number} modelId
 * @param {Object} data
 */
export function updateModelApi(modelId, data) {
  const formData = new FormData()
  Object.keys(data).forEach(key => {
    if (data[key] !== undefined && data[key] !== null) {
      formData.append(key, typeof data[key] === 'object' ? JSON.stringify(data[key]) : data[key])
    }
  })
  return request.put(`/models/${modelId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 归档模型（软删除）
 * @param {number} modelId
 */
export function deleteModelApi(modelId) {
  return request.delete(`/models/${modelId}`)
}

/**
 * 切换模型启用/禁用状态
 * @param {number} modelId
 */
export function toggleModelApi(modelId) {
  return request.put(`/models/${modelId}/toggle`)
}

/**
 * 获取模型版本列表
 * @param {number} modelId
 * @param {Object} params - { page, page_size }
 */
export function getModelVersionsApi(modelId, params) {
  return request.get(`/models/${modelId}/versions`, { params })
}

/**
 * 设为默认版本
 * @param {number} modelId
 * @param {number} versionId
 */
export function setDefaultVersionApi(modelId, versionId) {
  return request.put(`/models/${modelId}/versions/${versionId}/default`)
}

/**
 * 归档模型版本
 * @param {number} modelId
 * @param {number} versionId
 */
export function deleteVersionApi(modelId, versionId) {
  return request.delete(`/models/${modelId}/versions/${versionId}`)
}

/**
 * 导出模型 ZIP
 * @param {number} modelId
 * @param {number} versionId
 */
export function exportModelApi(modelId, versionId) {
  return request.get(`/models/${modelId}/versions/${versionId}/export`, {
    responseType: 'blob'
  })
}

/**
 * 导入模型 ZIP
 * @param {number} modelId
 * @param {Object} data - { zip_file, description }
 */
export function importModelApi(modelId, data) {
  const formData = new FormData()
  formData.append('zip_file', data.zip_file)
  formData.append('description', data.description || '')
  return request.post(`/models/${modelId}/import`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 获取场景关联的模型列表
 * @param {number} sceneId
 */
export function getSceneModelsApi(sceneId) {
  return request.get(`/models/scenes/${sceneId}/models`)
}

/**
 * 绑定模型到场景
 * @param {number} sceneId
 * @param {Object} data - { model_id, is_default }
 */
export function bindModelToSceneApi(sceneId, data) {
  const formData = new FormData()
  formData.append('model_id', data.model_id)
  formData.append('is_default', data.is_default ?? false)
  return request.post(`/models/scenes/${sceneId}/bindmodel`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 解绑模型与场景
 * @param {number} sceneId
 * @param {number} modelId
 */
export function unbindModelFromSceneApi(sceneId, modelId) {
  return request.delete(`/models/scenes/${sceneId}/bindmodel/${modelId}`)
}
