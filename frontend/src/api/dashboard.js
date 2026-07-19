/**
 * Dashboard 统计数据 API
 */
import request from '@/utils/request'

/** 获取 Dashboard 聚合统计数据 */
export function getDashboardStatsApi() {
  return request.get('/dashboard/stats')
}

export function getFoodDashboardStatsApi() {
  return request.get('/dashboard/food-stats')
}

/** 获取当前用户统计数据 */
export function getUserStatsApi() {
  return request.get('/dashboard/user-stats')
}
