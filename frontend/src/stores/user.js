/**
 * 用户状态管理
 *
 * 使用 HttpOnly cookie 存储 JWT Token（更安全，防止 XSS 读取）
 * 用户信息仍存储在 localStorage 用于前端状态恢复
 */
import { defineStore } from 'pinia'
import { loginApi, getUserInfoApi, logoutApi } from '@/api/auth'
import { hasRole, isAdmin, isSuperAdmin } from '@/utils/permission'

const USER_KEY = 'visagent_user'

export const useUserStore = defineStore('user', {
  state: () => ({
    // 当前用户信息（从 localStorage 恢复）
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  }),

  getters: {
    /** 是否已登录（基于用户信息是否存在） */
    isLoggedIn: (state) => !!state.user,
    /** 用户名 */
    username: (state) => state.user?.username || '',
    /** 头像 */
    avatar: (state) => state.user?.avatar || '',
    /** 角色列表 */
    roles: (state) => state.user?.roles || [],
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
  },

  actions: {
    /**
     * 登录
     * @param {Object} credentials - { username, password }
     */
    async login(credentials) {
      const res = await loginApi(credentials)
      // Token 存储在 HttpOnly cookie 中，由后端设置，前端无需处理
      // 保存用户信息
      this.user = res.user
      localStorage.setItem(USER_KEY, JSON.stringify(res.user))
      return res
    },

    /**
     * 获取用户信息
     */
    async fetchUserInfo() {
      try {
        const user = await getUserInfoApi()
        this.user = user
        localStorage.setItem(USER_KEY, JSON.stringify(user))
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
