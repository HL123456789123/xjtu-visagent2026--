/**
 * Vue Router 路由配置
 * - / → MainLayout (需登录) → 子路由
 * - /login → 登录页
 * - /register → 注册页
 */
import { createRouter, createWebHistory } from 'vue-router'
import { getActivePinia } from 'pinia'
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
    redirect: '/food-recipes',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'food-recipes',
        name: 'FoodRecipe',
        component: () => import('@/views/FoodRecipePage.vue'),
        meta: { title: '食物菜谱', icon: 'Goods' },
      },
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
        meta: { title: '目标检测', icon: 'Camera', permission: 'detection:task:view' },
      },
      {
        path: 'training',
        name: 'Training',
        component: () => import('@/views/TrainingPage.vue'),
        meta: { title: '模型训练', icon: 'Cpu', permission: 'training:task:view' },
      },
      {
        path: 'datasets',
        name: 'Datasets',
        component: () => import('@/views/DatasetPage.vue'),
        meta: { title: '数据集', icon: 'FolderOpened', permission: 'dataset:view' },
      },
      {
        path: 'models',
        name: 'Models',
        component: () => import('@/views/ModelPage.vue'),
        meta: { title: '模型管理', icon: 'Goods', permission: 'model:view' },
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
        meta: { title: '仪表盘', icon: 'DataAnalysis', permission: 'system:dashboard' },
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
      // 404 页面（已登录用户在 MainLayout 主内容区内显示）
      {
        path: ':pathMatch(.*)*',
        name: 'NotFound',
        component: () => import('@/views/NotFoundPage.vue'),
        meta: { title: '页面未找到' },
      },
    ],
  },
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局前置守卫 —— 登录状态检查 + 首次加载验证
// 使用 sessionStorage 存储验证状态，支持多标签页共享
const VERIFIED_KEY = 'visagent_verified'

function getVerified() {
  return sessionStorage.getItem(VERIFIED_KEY) === 'true'
}

function setVerified(val) {
  sessionStorage.setItem(VERIFIED_KEY, val ? 'true' : 'false')
}

router.beforeEach(async (to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title
    ? `${to.meta.title} - visagent`
    : 'visagent'

  // 防御性检查：确保 Pinia 已激活（Vite 8 模块时序可能导致 install 阶段 Pinia 上下文丢失）
  if (!getActivePinia()) {
    next()
    return
  }

  // 从 store 获取登录状态（基于 HttpOnly cookie，不再依赖 localStorage token）
  const userStore = useUserStore()
  const isLoggedIn = userStore.isLoggedIn
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth !== false)

  // 页面刷新后 permissions 丢失（仅存在内存中），需重新获取
  // 判断依据：sessionStorage 未验证 或 用户无权限列表
  const needsPermissions = !userStore.permissions || userStore.permissions.length === 0
  if (requiresAuth && isLoggedIn && (!getVerified() || needsPermissions)) {
    try {
      await userStore.fetchUserInfo()
      setVerified(true)
    } catch {
      // fetchUserInfo 失败（如 token 过期），重置验证标记并清除用户状态
      setVerified(false)
      userStore.user = null
      // 用户状态已失效，直接跳转登录页，避免后续权限检查误判为 404
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
  }

  // 登出后重置验证标记
  if (!userStore.isLoggedIn) {
    setVerified(false)
  }

  if (requiresAuth && !userStore.isLoggedIn) {
    // 未登录，跳转到登录页
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if ((to.path === '/login' || to.path === '/register') && userStore.isLoggedIn) {
    // 已登录则跳转到首页
    next('/')
  } else if (to.meta.permission) {
    // 需要特定权限的路由，使用细粒度权限判断
    const hasPerm = userStore.hasPermission(to.meta.permission)
    if (!hasPerm) {
      next({ name: 'NotFound' })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
