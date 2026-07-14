<template>
  <aside class="app-sidebar">
    <el-menu
      :default-active="activeMenu"
      :router="true"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409eff"
    >
      <!-- 普通菜单项 -->
      <el-menu-item
        v-for="item in visibleMenuItems"
        :key="item.path"
        :index="item.path"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <span>{{ item.title }}</span>
      </el-menu-item>

      <!-- 系统管理菜单组（按权限显示） -->
      <el-sub-menu v-if="showAdminMenu" index="/admin">
        <template #title>
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </template>
        <el-menu-item
          v-for="item in visibleAdminMenuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-sub-menu>
    </el-menu>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  ChatDotRound,
  Camera,
  Cpu,
  Clock,
  DataAnalysis,
  User,
  Goods,
  Setting,
  UserFilled,
  Key,
  FolderOpened,
} from '@element-plus/icons-vue'

const route = useRoute()
const userStore = useUserStore()

/** 当前激活的菜单项 */
const activeMenu = computed(() => {
  const path = route.path
  // 处理管理员子菜单激活状态
  if (path.startsWith('/admin')) {
    return path
  }
  return '/' + path.split('/')[1]
})

/** 普通菜单项（含权限标识） */
const menuItems = [
  { path: '/food-recipes', title: '食物菜谱', icon: Goods },
  { path: '/dashboard', title: '仪表盘', icon: DataAnalysis, permission: 'system:dashboard' },
  { path: '/chat', title: '智能对话', icon: ChatDotRound, permission: 'agent:chat' },
  { path: '/detection', title: '目标检测', icon: Camera, permission: 'detection:task:view' },
  { path: '/models', title: '模型管理', icon: Goods, permission: 'model:view' },
  { path: '/training', title: '模型训练', icon: Cpu, permission: 'training:task:view' },
  { path: '/datasets', title: '数据集管理', icon: FolderOpened, permission: 'dataset:view' },
  { path: '/history', title: '历史记录', icon: Clock, permission: 'detection:task:view' },
]

/** 管理员菜单项（含权限标识） */
const adminMenuItems = [
  { path: '/admin/users', title: '用户管理', icon: UserFilled, permission: 'user:list' },
  { path: '/admin/roles', title: '角色管理', icon: Key, permission: 'role:list' },
]

function canSeeMenuItem(item) {
  return !item.permission || userStore.hasPermission(item.permission)
}

/** 可见的普通菜单项（根据用户权限过滤） */
const visibleMenuItems = computed(() =>
  menuItems.filter(canSeeMenuItem)
)

/** 可见的管理员菜单项（根据用户权限过滤） */
const visibleAdminMenuItems = computed(() =>
  adminMenuItems.filter(canSeeMenuItem)
)

/** 是否显示系统管理菜单组（有任一子权限时显示） */
const showAdminMenu = computed(() => visibleAdminMenuItems.value.length > 0)
</script>

<style lang="scss" scoped>
.app-sidebar {
  width: $sidebar-width;
  height: 100%;
  background: $sidebar-bg;
  overflow-y: auto;

  .el-menu {
    border-right: none;
    height: 100%;
  }

  .el-menu-item {
    height: 50px;
    line-height: 50px;

    &.is-active {
      background-color: rgba(64, 158, 255, 0.15) !important;
    }

    &:hover {
      background-color: rgba(255, 255, 255, 0.05) !important;
    }
  }
}
</style>
