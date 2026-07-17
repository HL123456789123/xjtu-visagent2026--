<template>
  <header class="app-header">
    <div class="header-left">
      <span class="brand-mark" aria-hidden="true">🍳</span>
      <span class="brand-title">FridgeChef</span>
    </div>

    <!-- 用户信息 + 下拉菜单 -->
    <div class="header-right">
      <el-dropdown trigger="click" @command="handleCommand">
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
import { useRouter } from 'vue-router'
import { ArrowDown, User, SwitchButton } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

/** 处理下拉菜单命令 */
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
        // 用户取消确认框或 logout 出错，不做处理
      }
      break
  }
}
</script>

<style lang="scss" scoped>
.app-header {
  height: $header-height;
  background: rgba(255, 253, 248, 0.92);
  border-bottom: 1px solid rgba(121, 82, 45, 0.12);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-lg;
  box-shadow: 0 10px 30px rgba(102, 68, 35, 0.08);
  backdrop-filter: blur(18px);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
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

.header-right {
  display: flex;
  align-items: center;
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

@media (max-width: 560px) {
  .brand-title,
  .username {
    display: none;
  }
}
</style>
