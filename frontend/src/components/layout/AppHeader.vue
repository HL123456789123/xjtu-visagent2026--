<template>
  <header class="app-header">
    <div class="header-left">
      <router-link class="brand" to="/start" aria-label="返回开始页">
        <span class="brand-mark">🍳</span>
        <span class="brand-title">FridgeChef</span>
      </router-link>
    </div>

    <nav class="header-nav" aria-label="主导航">
      <router-link
        v-for="item in visibleMenuItems"
        :key="item.path"
        class="header-nav__item"
        :class="{ active: activeMenu === item.path }"
        :to="item.path"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <span>{{ item.title }}</span>
      </router-link>

      <el-dropdown v-if="showAdminMenu" trigger="click" class="header-nav__admin">
        <button class="header-nav__item header-nav__item--button" type="button">
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="item in visibleAdminMenuItems"
              :key="item.path"
              @click="router.push(item.path)"
            >
              <el-icon>
                <component :is="item.icon" />
              </el-icon>
              {{ item.title }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </nav>

    <div class="header-right">
      <el-dropdown trigger="click" @command="handleCommand">
        <div class="user-info">
          <span class="mode-badge">{{ userStore.isAdminMode ? '管理端' : '用户端' }}</span>
          <el-avatar :size="32" :src="userStore.avatar || undefined">
            {{ userStore.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <span class="username">{{ userStore.username }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>

        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="switch">
              <el-icon><Switch /></el-icon>切换入口
            </el-dropdown-item>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon>个人信息
            </el-dropdown-item>
            <el-dropdown-item command="logout" divided>
              <el-icon><SwitchButton /></el-icon>退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  ChatDotRound,
  Clock,
  Cpu,
  DataAnalysis,
  Goods,
  Key,
  Setting,
  Switch,
  SwitchButton,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menuItems = [
  { path: '/start', title: '首页', icon: Goods },
  { path: '/food-recipes', title: '食物识别', icon: Goods },
  { path: '/chat', title: '智能对话', icon: ChatDotRound },
  { path: '/history', title: '历史记录', icon: Clock },
  { path: '/training', title: '模型训练', icon: Cpu, permission: 'training:task:view', managerOnly: true },
  { path: '/dashboard', title: '数据看板', icon: DataAnalysis, permission: 'system:dashboard', managerOnly: true },
]

const adminMenuItems = [
  { path: '/admin/users', title: '用户管理', icon: UserFilled, permission: 'user:list' },
  { path: '/admin/roles', title: '角色管理', icon: Key, permission: 'role:list' },
]

const activeMenu = computed(() => {
  if (route.path.startsWith('/admin')) return '/admin'
  return '/' + route.path.split('/')[1]
})

function canSeeMenuItem(item) {
  if (item.managerOnly && !userStore.isAdminMode) return false
  return !item.permission || userStore.hasPermission(item.permission)
}

const visibleMenuItems = computed(() => menuItems.filter(canSeeMenuItem))
const visibleAdminMenuItems = computed(() => userStore.isAdminMode ? adminMenuItems.filter(canSeeMenuItem) : [])
const showAdminMenu = computed(() => visibleAdminMenuItems.value.length > 0)

async function handleCommand(command) {
  switch (command) {
    case 'profile':
      router.push('/profile')
      break
    case 'switch':
      router.push('/login')
      break
    case 'logout':
      try {
        await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        })
        await userStore.logout()
        router.push('/login')
      } catch {
        // 用户取消确认框或 logout 出错，不做处理
      }
      break
  }
}
</script>

<style lang="scss" scoped>
.app-header {
  height: $header-height;
  position: sticky;
  top: 0;
  background: rgba(255, 253, 248, 0.92);
  border-bottom: 1px solid rgba(121, 82, 45, 0.12);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 0 clamp(18px, 4vw, 54px);
  box-shadow: 0 10px 30px rgba(102, 68, 35, 0.08);
  backdrop-filter: blur(18px);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  flex: 0 0 auto;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #31512f;
  text-decoration: none;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: #fff3d8;
  box-shadow: inset 0 0 0 1px rgba(233, 109, 59, 0.14);
  font-size: 19px;
}

.brand-title {
  color: #31512f;
  font-size: 21px;
  font-weight: 900;
  letter-spacing: -0.03em;
}

.header-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.header-nav__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #4c3a2c;
  padding: 0 13px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 800;
  text-decoration: none;
  transition: background-color 0.2s ease, color 0.2s ease, transform 0.2s ease;

  &:hover,
  &.active,
  &.router-link-active {
    background: #fff1d2;
    color: #d76626;
  }

  &:hover {
    transform: translateY(-1px);
  }
}

.header-nav__item--button {
  font-family: inherit;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 0 auto;
}

.user-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 999px;
  transition: background 0.2s;

  &:hover {
    background: #fff1d2;
  }
}

.username {
  font-size: 14px;
  color: #4c3a2c;
  font-weight: 700;
}

.mode-badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 8px;
  background: #fff1d2;
  color: #d76626;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 900;
}

@media (max-width: 1080px) {
  .header-nav__item {
    padding: 0 9px;
  }
}

@media (max-width: 920px) {
  .app-header {
    height: auto;
    min-height: $header-height;
    align-items: stretch;
    flex-wrap: wrap;
    padding: 12px 18px;
  }

  .header-nav {
    order: 3;
    justify-content: flex-start;
    width: 100%;
    overflow-x: auto;
    padding-bottom: 2px;
  }
}

@media (max-width: 560px) {
  .brand-title,
  .mode-badge,
  .username {
    display: none;
  }
}
</style>
