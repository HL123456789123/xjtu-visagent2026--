/**
 * 检测相关 API
 */
import request from '@/utils/request'

/**
 * 获取检测场景列表
 */
export function getScenesApi() {
  return request.get('/detection/scenes')
}

/**
 * 创建检测场景
 * @param {Object} data - 场景信息（name, display_name, description, category, class_names, class_names_cn）
 */
export function createSceneApi(data) {
  const formData = new FormData()
  formData.append('name', data.name)
  formData.append('display_name', data.display_name)
  formData.append('description', data.description || '')
  formData.append('category', data.category)
  formData.append('class_names', data.class_names)
  formData.append('class_names_cn', data.class_names_cn || '')
  return request.post('/detection/scenes', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 单图检测
 * @param {Object} data - { scene_id, image, conf_threshold, iou_threshold, image_size, model_version_id }
 */
export function detectSingleApi(data) {
  const formData = new FormData()
  formData.append('scene_id', data.scene_id)
  formData.append('image', data.image)
  formData.append('conf_threshold', data.conf_threshold || 0.25)
  formData.append('iou_threshold', data.iou_threshold || 0.45)
  formData.append('image_size', data.image_size || 640)
  if (data.model_version_id) {
    formData.append('model_version_id', data.model_version_id)
  }
  return request.post('/detection/single', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 批量检测
 * @param {Object} data - { scene_id, images[], conf_threshold, iou_threshold, image_size, model_version_id }
 */
export function detectBatchApi(data) {
  const formData = new FormData()
  formData.append('scene_id', data.scene_id)
  data.images.forEach(image => {
    formData.append('images', image)
  })
  formData.append('conf_threshold', data.conf_threshold || 0.25)
  formData.append('iou_threshold', data.iou_threshold || 0.45)
  formData.append('image_size', data.image_size || 640)
  if (data.model_version_id) {
    formData.append('model_version_id', data.model_version_id)
  }
  return request.post('/detection/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 视频检测
 * @param {Object} data - { scene_id, video, conf_threshold, iou_threshold, image_size, model_version_id }
 */
export function detectVideoApi(data) {
  const formData = new FormData()
  formData.append('scene_id', data.scene_id)
  formData.append('video', data.video)
  formData.append('conf_threshold', data.conf_threshold || 0.25)
  formData.append('iou_threshold', data.iou_threshold || 0.45)
  formData.append('image_size', data.image_size || 640)
  if (data.model_version_id) {
    formData.append('model_version_id', data.model_version_id)
  }
  return request.post('/detection/video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 获取检测任务列表
 * @param {Object} params - { scene_id, page, page_size }
 */
export function getDetectionTasksApi(params) {
  return request.get('/detection/tasks', { params })
}

/**
 * 获取检测任务详情
 * @param {number} taskId
 */
export function getDetectionTaskApi(taskId) {
  return request.get(`/detection/tasks/${taskId}`)
}

/**
 * 获取检测结果
 * @param {number} taskId
 * @param {Object} params - { page, page_size }
 */
export function getDetectionResultsApi(taskId, params) {
  return request.get(`/detection/tasks/${taskId}/results`, { params })
}
