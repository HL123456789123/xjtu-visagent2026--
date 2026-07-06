<template>
  <aside class="app-sidebar">
    <el-menu
      :default-active="activeMenu"
      :router="true"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409eff"
    >
      <el-menu-item
        v-for="item in menuItems"
        :key="item.path"
        :index="item.path"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <span>{{ item.title }}</span>
      </el-menu-item>
    </el-menu>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  ChatDotRound,
  Camera,
  Cpu,
  Clock,
  DataAnalysis,
  User,
  Goods,
} from '@element-plus/icons-vue'

const route = useRoute()

/** 当前激活的菜单项 */
const activeMenu = computed(() => {
  return '/' + route.path.split('/')[1]
})

/** 侧边栏菜单项 */
const menuItems = [
  { path: '/chat', title: '智能对话', icon: ChatDotRound },
  { path: '/detection', title: '目标检测', icon: Camera },
  { path: '/training', title: '模型训练', icon: Cpu },
  { path: '/models', title: '模型管理', icon: Goods },
  { path: '/history', title: '历史记录', icon: Clock },
  { path: '/dashboard', title: '仪表盘', icon: DataAnalysis },
  { path: '/profile', title: '个人信息', icon: User },
]
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
