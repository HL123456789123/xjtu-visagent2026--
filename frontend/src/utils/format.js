/**
 * 公共工具函数模块
 * 提供通用的格式化和处理函数
 */

/**
 * 格式化时间戳为本地时间字符串
 * @param {string|Date} timestamp - 时间戳或Date对象
 * @param {Object} options - 格式化选项
 * @param {boolean} options.showTime - 是否显示时间（默认true）
 * @param {boolean} options.showSeconds - 是否显示秒（默认false）
 * @returns {string} 格式化后的时间字符串
 */
export function formatTime(timestamp, options = {}) {
  if (!timestamp) return ''
  
  const { showTime = true, showSeconds = false } = options
  const date = new Date(timestamp)
  
  if (isNaN(date.getTime())) {
    return ''
  }
  
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  
  let result = `${year}-${month}-${day}`
  
  if (showTime) {
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    result += ` ${hours}:${minutes}`
    
    if (showSeconds) {
      const seconds = String(date.getSeconds()).padStart(2, '0')
      result += `:${seconds}`
    }
  }
  
  return result
}

/**
 * 格式化文件大小
 * @param {number} bytes - 文件大小（字节）
 * @param {number} decimals - 小数位数（默认2）
 * @returns {string} 格式化后的文件大小字符串
 */
export function formatFileSize(bytes, decimals = 2) {
  if (bytes === 0) return '0 Bytes'
  
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
  
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

/**
 * 格式化数字为百分比
 * @param {number} value - 数值（0-1之间）
 * @param {number} decimals - 小数位数（默认1）
 * @returns {string} 百分比字符串
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined) return '0%'
  return (value * 100).toFixed(decimals) + '%'
}

/**
 * 格式化数字为千分位分隔
 * @param {number} num - 数字
 * @returns {string} 格式化后的数字字符串
 */
export function formatNumber(num) {
  if (num === null || num === undefined) return '0'
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

/**
 * 格式化持续时间
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的时间字符串
 */
export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0秒'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  let result = ''
  if (hours > 0) result += `${hours}小时`
  if (minutes > 0) result += `${minutes}分钟`
  if (secs > 0 || result === '') result += `${secs}秒`
  
  return result
}

/**
 * 截断字符串
 * @param {string} str - 原始字符串
 * @param {number} maxLength - 最大长度
 * @param {string} suffix - 后缀（默认'...'）
 * @returns {string} 截断后的字符串
 */
export function truncateString(str, maxLength, suffix = '...') {
  if (!str || str.length <= maxLength) return str || ''
  return str.substring(0, maxLength) + suffix
}

/**
 * 格式化状态为中文
 * @param {string} status - 状态值
 * @returns {string} 中文状态
 */
export function formatStatus(status) {
  const statusMap = {
    pending: '待处理',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
    paused: '已暂停',
    active: '活跃',
    inactive: '停用',
  }
  return statusMap[status] || status
}

/**
 * 格式化进度条颜色
 * @param {number} progress - 进度值（0-100）
 * @returns {string} 颜色值
 */
export function getProgressColor(progress) {
  if (progress < 30) return '#F56C6C'
  if (progress < 70) return '#E6A23C'
  return '#67C23A'
}
