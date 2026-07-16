/**
 * 训练相关 API
 */
import request, { uploadRequest } from '@/utils/request'

/**
 * 获取可用训练设备列表
 */
export function getTrainingDevicesApi() {
  return request.get('/training/devices')
}

/**
 * 创建训练任务
 * @param {Object} data - 训练配置
 */
export function createTrainingTaskApi(data) {
  const formData = new FormData()
  Object.keys(data).forEach(key => {
    formData.append(key, data[key])
  })
  return request.post('/training/tasks', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 启动训练任务
 * @param {number} taskId
 */
export function startTrainingApi(taskId) {
  return request.post(`/training/tasks/${taskId}/start`)
}

/**
 * 暂停训练任务
 * @param {number} taskId
 */
export function pauseTrainingApi(taskId) {
  return request.post(`/training/tasks/${taskId}/pause`)
}

/**
 * 取消训练任务
 * @param {number} taskId
 */
export function cancelTrainingApi(taskId) {
  return request.post(`/training/tasks/${taskId}/cancel`)
}

/**
 * 删除训练任务
 * @param {number} taskId
 */
export function deleteTrainingTaskApi(taskId) {
  return request.delete(`/training/tasks/${taskId}`)
}

/**
 * 获取训练任务列表
 * @param {Object} params - { model_id, status, page, page_size }
 */
export function getTrainingTasksApi(params) {
  return request.get('/training/tasks', { params })
}

/**
 * 获取训练任务详情
 * @param {number} taskId
 */
export function getTrainingTaskApi(taskId) {
  return request.get(`/training/tasks/${taskId}`)
}

/**
 * 获取训练状态
 * @param {number} taskId
 */
export function getTrainingStatusApi(taskId) {
  return request.get(`/training/tasks/${taskId}/status`)
}

/**
 * 获取训练指标
 * @param {number} taskId
 */
export function getTrainingMetricsApi(taskId) {
  return request.get(`/training/tasks/${taskId}/metrics`)
}

/**
 * 验证数据集
 * @param {Object} data - { images_dir, labels_dir, class_names }
 */
export function validateDatasetApi(data) {
  const formData = new FormData()
  formData.append('images_dir', data.images_dir)
  formData.append('labels_dir', data.labels_dir)
  formData.append('class_names', data.class_names)
  return request.post('/training/datasets/validate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 划分数据集
 * @param {Object} data - { images_dir, labels_dir, output_dir, train_ratio, val_ratio, test_ratio }
 */
export function splitDatasetApi(data) {
  const formData = new FormData()
  Object.keys(data).forEach(key => {
    formData.append(key, data[key])
  })
  return request.post('/training/datasets/split', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 生成 data.yaml
 * @param {Object} data - { output_path, class_names, dataset_dir }
 */
export function generateDataYamlApi(data) {
  const formData = new FormData()
  formData.append('output_path', data.output_path)
  formData.append('class_names', data.class_names)
  formData.append('dataset_dir', data.dataset_dir)
  return request.post('/training/datasets/generate-yaml', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 上传训练好的模型文件
 * @param {Object} data - { model_id, model_file, version, description, is_default }
 */
export function uploadModelApi(data) {
  const formData = new FormData()
  formData.append('model_id', data.model_id)
  formData.append('model_file', data.model_file)
  formData.append('version', data.version)
  formData.append('description', data.description || '')
  formData.append('is_default', data.is_default ?? true)
  return uploadRequest.post('/training/models/upload', formData)
}

/**
 * VOC XML → YOLO TXT 格式转换
 * @param {Object} data - { voc_file, class_names }
 */
export function convertVocToYoloApi(data) {
  const formData = new FormData()
  formData.append('voc_file', data.voc_file)
  formData.append('class_names', data.class_names)
  return request.post('/training/datasets/convert/voc-to-yolo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * COCO JSON → YOLO TXT 格式转换
 * @param {Object} data - { coco_file, image_dir, output_dir }
 */
export function convertCocoToYoloApi(data) {
  const formData = new FormData()
  formData.append('coco_file', data.coco_file)
  formData.append('image_dir', data.image_dir)
  formData.append('output_dir', data.output_dir)
  return request.post('/training/datasets/convert/coco-to-yolo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * LabelMe JSON → YOLO TXT 格式转换
 * @param {Object} data - { labelme_file, class_names }
 */
export function convertLabelmeToYoloApi(data) {
  const formData = new FormData()
  formData.append('labelme_file', data.labelme_file)
  formData.append('class_names', data.class_names)
  return request.post('/training/datasets/convert/labelme-to-yolo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
