/**
 * 用户状态管理
 *
 * 安全存储策略：
 * - JWT Token：存储在 HttpOnly cookie 中（防止 XSS 读取）
 * - 非敏感信息（用户名、头像）：存储在 localStorage 用于前端状态恢复
 * - 敏感信息（权限、角色）：仅存储在内存中，页面刷新后重新获取
 */
import { defineStore } from 'pinia'
import { loginApi, getUserInfoApi, logoutApi } from '@/api/auth'
import { hasRole, isAdmin, isSuperAdmin, hasPermission } from '@/utils/permission'

const USER_KEY = 'visagent_user'

/**
 * 从用户对象中提取非敏感信息用于 localStorage 存储
 * @param {Object} user - 完整用户对象
 * @returns {Object} - 仅包含非敏感字段的对象
 */
function extractSafeFields(user) {
  if (!user) return null
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    avatar: user.avatar,
    is_active: user.is_active,
  }
}

export const useUserStore = defineStore('user', {
  state: () => {
    // 从 localStorage 恢复非敏感信息
    const savedUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    return {
      // 当前用户信息（敏感字段如 roles/permissions 仅在内存中）
      user: savedUser,
    }
  },

  getters: {
    /** 是否已登录（基于用户信息是否存在） */
    isLoggedIn: (state) => !!state.user,
    /** 用户名 */
    username: (state) => state.user?.username || '',
    /** 头像 */
    avatar: (state) => state.user?.avatar || '',
    /** 角色列表 */
    roles: (state) => state.user?.roles || [],
    /** 权限列表 */
    permissions: (state) => state.user?.permissions || [],
    /** 是否为管理员（admin 或 super_admin） */
    isAdmin: (state) => isAdmin(state.user),
    /** 是否为超级管理员（通过角色判断） */
    isSuperAdmin: (state) => isSuperAdmin(state.user),
    /**
     * 返回一个函数，用于判断用户是否拥有指定角色
     * 用法：const userStore = useUserStore()
     *       userStore.hasRole('admin')
     */
    hasRole: (state) => (roleName) => hasRole(state.user, roleName),
    /**
     * 判断是否拥有指定权限
     * 用法：userStore.hasPermission('user:list')
     */
    hasPermission: (state) => (code) => hasPermission(state.user, code),
  },

  actions: {
    /**
     * 登录
     * @param {Object} credentials - { username, password }
     */
    async login(credentials) {
      const res = await loginApi(credentials)
      // Token 存储在 HttpOnly cookie 中，由后端设置，前端无需处理
      // 保存用户信息（完整信息在内存，非敏感信息持久化到 localStorage）
      this.user = res.user
      localStorage.setItem(USER_KEY, JSON.stringify(extractSafeFields(res.user)))
      return res
    },

    /**
     * 获取用户信息
     */
    async fetchUserInfo() {
      try {
        const user = await getUserInfoApi()
        this.user = user
        localStorage.setItem(USER_KEY, JSON.stringify(extractSafeFields(user)))
      } catch (error) {
        // 401 已由请求拦截器处理（跳转登录页），此处不重复 logout
        // 其他错误（网络抖动、服务端临时错误）保留当前用户状态
        console.error('获取用户信息失败:', error)
        throw error
      }
    },

    /**
     * 登出
     */
    async logout() {
      try {
        // 调用后端接口清除 HttpOnly cookie
        await logoutApi()
      } catch {
        // 忽略登出接口错误
      }
      this.user = null
      localStorage.removeItem(USER_KEY)
    },
  },
})
