/**
 * Vue Router 路由配置
 * - / → MainLayout (需登录) → 子路由
 * - /login → 登录页
 * - /register → 注册页
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

// 路由表
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginPage.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterPage.vue'),
    meta: { title: '注册', requiresAuth: false },
  },
  // MainLayout 包裹的需要登录的页面
  {
    path: '/',
    component: () => import('@/components/layout/MainLayout.vue'),
    redirect: '/chat',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/ChatPage.vue'),
        meta: { title: '智能对话', icon: 'ChatDotRound' },
      },
      {
        path: 'detection',
        name: 'Detection',
        component: () => import('@/views/DetectionPage.vue'),
        meta: { title: '目标检测', icon: 'Camera' },
      },
      {
        path: 'training',
        name: 'Training',
        component: () => import('@/views/TrainingPage.vue'),
        meta: { title: '模型训练', icon: 'Cpu' },
      },
      {
        path: 'models',
        name: 'Models',
        component: () => import('@/views/ModelPage.vue'),
        meta: { title: '模型管理', icon: 'Goods' },
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/HistoryPage.vue'),
        meta: { title: '历史记录', icon: 'Clock' },
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardPage.vue'),
        meta: { title: '仪表盘', icon: 'DataAnalysis' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/ProfilePage.vue'),
        meta: { title: '个人信息', icon: 'User' },
      },
      // 管理员路由
      {
        path: 'admin/users',
        name: 'UserManage',
        component: () => import('@/views/admin/UserManagePage.vue'),
        meta: { title: '用户管理', icon: 'UserFilled', permission: 'user:list' },
      },
      {
        path: 'admin/roles',
        name: 'RoleManage',
        component: () => import('@/views/admin/RoleManagePage.vue'),
        meta: { title: '角色管理', icon: 'Key', permission: 'role:list' },
      },
    ],
  },
  // 404 页面
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundPage.vue'),
    meta: { title: '页面未找到', requiresAuth: false },
  },
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局前置守卫 —— 登录状态检查 + 首次加载验证
let _verified = false

router.beforeEach(async (to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title
    ? `${to.meta.title} - visagent`
    : 'visagent'

  // 从 store 获取登录状态（基于 HttpOnly cookie，不再依赖 localStorage token）
  const userStore = useUserStore()
  const isLoggedIn = userStore.isLoggedIn
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth !== false)

  // 首次加载时验证 cookie 是否仍有效
  if (requiresAuth && isLoggedIn && !_verified) {
    try {
      await userStore.fetchUserInfo()
      _verified = true
    } catch {
      // fetchUserInfo 失败时拦截器已处理跳转，此处直接 return
      return
    }
  }

  // 登出后重置验证标记
  if (!isLoggedIn) {
    _verified = false
  }

  if (requiresAuth && !isLoggedIn) {
    // 未登录，跳转到登录页
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if ((to.path === '/login' || to.path === '/register') && isLoggedIn) {
    // 已登录则跳转到首页
    next('/')
  } else if (to.meta.permission) {
    // 需要特定权限的路由，检查用户是否为管理员
    // 当前后端仅返回 roles，使用角色判断
    const isAdmin = userStore.isAdmin
    if (!isAdmin) {
      next({ path: '/404' })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
