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

      <!-- 管理员菜单组 -->
      <el-sub-menu v-if="isAdmin" index="/admin">
        <template #title>
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </template>
        <el-menu-item
          v-for="item in adminMenuItems"
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

/** 是否为管理员 */
const isAdmin = computed(() => userStore.isAdmin)

/** 普通菜单项 */
const menuItems = [
  { path: '/chat', title: '智能对话', icon: ChatDotRound },
  { path: '/detection', title: '目标检测', icon: Camera },
  { path: '/training', title: '模型训练', icon: Cpu },
  { path: '/models', title: '模型管理', icon: Goods },
  { path: '/history', title: '历史记录', icon: Clock },
  { path: '/dashboard', title: '仪表盘', icon: DataAnalysis },
  { path: '/profile', title: '个人信息', icon: User },
]

/** 管理员菜单项 */
const adminMenuItems = [
  { path: '/admin/users', title: '用户管理', icon: UserFilled },
  { path: '/admin/roles', title: '角色管理', icon: Key },
]

/** 可见的普通菜单项（所有登录用户都可见） */
const visibleMenuItems = computed(() => menuItems)
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
