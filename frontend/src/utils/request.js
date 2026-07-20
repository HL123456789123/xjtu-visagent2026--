/**
 * Axios 请求封装
 * - 统一 baseURL
 * - JWT Token 自动注入
 * - 统一错误处理（Token 过期自动跳转登录）
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

// 创建 Axios 实例
const request = axios.create({
  baseURL: '/api',        // 使用 Vite proxy 转发
  timeout: 30000,         // 30 秒超时
  withCredentials: true,  // 自动发送 cookie
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    // Token 存储在 HttpOnly cookie 中，浏览器会自动携带，无需手动注入
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

function responseMessage(response) {
  const message = response.data?.message
  const detail = response.data?.detail
  const detailMessage = Array.isArray(detail) ? detail[0]?.msg : detail
  return { message, detailMessage }
}

function handleResponseError(error) {
  const { response, config } = error

  if (!response) {
    ElMessage.error('网络连接失败，请检查网络')
    return Promise.reject(error)
  }

  const { message, detailMessage } = responseMessage(response)
  const fallbackMessage = message || detailMessage

  switch (response.status) {
    case 401:
      if (config?.url?.includes('/auth/login')) {
        ElMessage.error(fallbackMessage || '用户名或密码错误')
      } else {
        ElMessage.error('登录已过期，请重新登录')
        useUserStore().logout()
        router.push('/login')
      }
      break
    case 403:
      ElMessage.error(fallbackMessage || '没有权限访问该资源')
      break
    case 404:
      ElMessage.error(fallbackMessage || '请求的资源不存在')
      break
    case 413:
      ElMessage.error(fallbackMessage || '上传图片总大小超过限制')
      break
    case 415:
      ElMessage.error(fallbackMessage || '图片格式不受支持')
      break
    case 422:
      ElMessage.error(fallbackMessage || '请求参数错误')
      break
    case 500:
      ElMessage.error(fallbackMessage || '服务器内部错误')
      break
    case 503:
      ElMessage.error(fallbackMessage || '服务暂时不可用')
      break
    default:
      ElMessage.error(fallbackMessage || `请求错误 (${response.status})`)
  }

  return Promise.reject(error)
}

function registerResponseInterceptor(client) {
  client.interceptors.response.use((response) => response.data, handleResponseError)
}

registerResponseInterceptor(request)

export default request

// 文件上传专用 Axios 实例（10 分钟超时）
const uploadRequest = axios.create({
  baseURL: '/api',
  timeout: 600000,        // 10 分钟超时，适用于大文件上传
  withCredentials: true,
  headers: {
    'Content-Type': 'multipart/form-data',
  },
})

registerResponseInterceptor(uploadRequest)

export { uploadRequest }
