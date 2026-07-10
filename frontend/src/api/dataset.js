/**
 * 数据集管理 API
 */
import request from '@/utils/request'

/**
 * 获取数据集列表
 * @param {Object} params - { status, page, page_size }
 */
export function getDatasetsApi(params) {
  return request.get('/datasets', { params })
}

/**
 * 获取数据集详情
 * @param {number} id
 */
export function getDatasetApi(id) {
  return request.get(`/datasets/${id}`)
}

/**
 * 注册数据集
 * @param {Object} data - { name, description, path, yaml_path, format }
 */
export function createDatasetApi(data) {
  return request.post('/datasets/register', data)
}

/**
 * 删除数据集
 * @param {number} id
 */
export function deleteDatasetApi(id) {
  return request.delete(`/datasets/${id}`)
}

/**
 * 校验数据集
 * @param {number} id
 */
export function validateDatasetApi(id) {
  return request.post(`/datasets/${id}/validate`)
}
