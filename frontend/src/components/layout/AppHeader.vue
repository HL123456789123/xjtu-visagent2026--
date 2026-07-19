<template>
  <header class="app-header">
    <router-link class="header-brand" to="/home" aria-label="FridgeChef 首页">
      <span class="brand-mark" aria-hidden="true">🍳</span>
      <span class="brand-title">FridgeChef</span>
    </router-link>

    <button
      class="nav-toggle"
      type="button"
      aria-label="展开导航菜单"
      :aria-expanded="menuOpen"
      data-testid="topnav-toggle"
      @click="menuOpen = !menuOpen"
    >
      <el-icon><Menu /></el-icon>
    </button>

    <nav :class="['top-nav', { 'top-nav--open': menuOpen }]" aria-label="主导航" data-testid="top-nav">
      <button
        v-for="item in visibleNavItems"
        :key="item.path"
        type="button"
        :class="['top-nav__item', { 'top-nav__item--active': isNavActive(item) }]"
        :data-testid="`nav-${item.id}`"
        @click="goTo(item.path)"
      >
        {{ item.label }}
      </button>
    </nav>

    <div class="header-right">
      <el-dropdown trigger="click" data-testid="user-menu" @command="handleCommand">
        <div class="user-info">
          <el-avatar :size="32" :src="userStore.avatar || undefined">
            {{ userStore.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <span class="username">{{ userStore.username }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>

        <template #dropdown>
          <el-dropdown-menu>
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
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Menu, User, SwitchButton } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const menuOpen = ref(false)

const navItems = [
  { id: 'home', label: '首页', path: '/home' },
  { id: 'food', label: '食材与菜谱', path: '/food-recipes' },
  { id: 'history', label: '历史记录', path: '/history' },
  { id: 'dashboard', label: '数据看板', path: '/dashboard' },
  { id: 'profile', label: '个人中心', path: '/profile' },
]

const visibleNavItems = computed(() => {
  const items = navItems.filter((item) => !item.permission || userStore.hasPermission(item.permission))

  if (['user:list', 'role:list', 'detection:task:view', 'training:task:view', 'dataset:view', 'model:view']
    .some((permission) => userStore.hasPermission(permission))) {
    items.push({ id: 'admin', label: '模型工作台', path: '/admin/workbench' })
  }

  return items
})

function isNavActive(item) {
  if (item.id === 'admin') return route.path.startsWith('/admin')
  return route.path === item.path || route.path.startsWith(`${item.path}/`)
}

function goTo(path) {
  menuOpen.value = false
  router.push(path)
}

async function handleCommand(command) {
  switch (command) {
    case 'profile':
      router.push('/profile')
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
        // 用户取消确认或退出接口失败时保持当前页面。
      }
      break
  }
}
</script>

<style lang="scss" scoped>
.app-header {
  min-height: $header-height;
  display: flex;
  align-items: center;
  gap: $spacing-lg;
  padding: 0 $spacing-lg;
  background: rgba(255, 253, 248, 0.92);
  border-bottom: 1px solid rgba(121, 82, 45, 0.12);
  box-shadow: 0 10px 30px rgba(102, 68, 35, 0.08);
  backdrop-filter: blur(18px);
  z-index: 100;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  color: inherit;
  flex-shrink: 0;
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

.top-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.top-nav__item {
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #76573f;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 750;
  padding: 8px 11px;
  transition: background 0.2s, color 0.2s;

  &:hover,
  &--active {
    background: #fff1d2;
    color: #c85b2b;
  }
}

.header-right {
  display: flex;
  align-items: center;
  margin-left: auto;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: 4px 8px;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: #fff1d2;
  }
}

.username {
  color: #4c3a2c;
  font-size: 14px;
  font-weight: 700;
}

.nav-toggle {
  display: none;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 10px;
  background: #fff3d8;
  color: #76573f;
  cursor: pointer;
  font-size: 18px;
  padding: 6px;
}

@media (max-width: 920px) {
  .app-header {
    flex-wrap: wrap;
    gap: $spacing-sm;
    padding: 10px $spacing-md;
  }

  .nav-toggle {
    display: inline-flex;
  }

  .top-nav {
    display: none;
    flex-basis: 100%;
    flex-wrap: wrap;
    order: 4;
  }

  .top-nav--open {
    display: flex;
  }
}

@media (max-width: 560px) {
  .brand-title,
  .username {
    display: none;
  }
}
</style>
