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

// 响应拦截器 —— 统一错误处理
request.interceptors.response.use(
  (response) => {
    // 直接返回 data
    return response.data
  },
  (error) => {
    const { response, config } = error
    if (response) {
      const msg = response.data?.message
      const detail = response.data?.detail
      switch (response.status) {
        case 401:
          // 登录接口的 401 表示用户名或密码错误，不做 token 过期处理
          if (config?.url?.includes('/auth/login')) {
            ElMessage.error(msg || detail || '用户名或密码错误')
          } else {
            // 其他接口的 401 表示 Token 过期或无效
            ElMessage.error('登录已过期，请重新登录')
            const userStore = useUserStore()
            userStore.logout()
            router.push('/login')
          }
          break
        case 403:
          ElMessage.error(msg || '没有权限访问该资源')
          break
        case 404:
          ElMessage.error(msg || '请求的资源不存在')
          break
        case 413:
          ElMessage.error(msg || detail || '图片超过 10 MB')
          break
        case 415:
          ElMessage.error(msg || detail || '仅支持 JPG、JPEG 或 PNG 图片')
          break
        case 422:
          // Pydantic 验证错误
          if (Array.isArray(detail)) {
            ElMessage.error(detail[0]?.msg || msg || '请求参数错误')
          } else {
            ElMessage.error(msg || detail || '请求参数错误')
          }
          break
        case 500:
          ElMessage.error(msg || '服务器内部错误')
          break
        default:
          ElMessage.error(msg || detail || `请求错误 (${response.status})`)
      }
    } else {
      // 网络错误
      ElMessage.error('网络连接失败，请检查网络')
    }
    return Promise.reject(error)
  }
)

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

// 复用主实例的响应拦截器逻辑
uploadRequest.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const { response } = error
    if (response) {
      const msg = response.data?.message
      const detail = response.data?.detail
      switch (response.status) {
        case 401:
          ElMessage.error('登录已过期，请重新登录')
          useUserStore().logout()
          router.push('/login')
          break
        case 403:
          ElMessage.error(msg || '没有权限访问该资源')
          break
        case 413:
          ElMessage.error(msg || detail || '图片超过 10 MB')
          break
        case 415:
          ElMessage.error(msg || detail || '仅支持 JPG、JPEG 或 PNG 图片')
          break
        case 422:
          if (Array.isArray(detail)) {
            ElMessage.error(detail[0]?.msg || msg || '请求参数错误')
          } else {
            ElMessage.error(msg || detail || '请求参数错误')
          }
          break
        default:
          ElMessage.error(msg || detail || `请求错误 (${response.status})`)
      }
    } else {
      ElMessage.error('网络连接失败，请检查网络')
    }
    return Promise.reject(error)
  }
)

export { uploadRequest }
