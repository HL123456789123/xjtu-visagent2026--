<template>
  <div class="profile-page">
    <div class="profile-card">
      <!-- 头像区域 -->
      <div class="profile-header">
        <el-avatar :size="80" :src="userStore.avatar || undefined" class="profile-avatar">
          {{ userStore.username?.charAt(0)?.toUpperCase() }}
        </el-avatar>
        <div class="profile-name">
          <h2>{{ userStore.username }}</h2>
          <el-tag v-if="userStore.isSuperAdmin" type="danger" size="small">超级管理员</el-tag>
          <el-tag v-else-if="isAdministrator" type="warning" size="small">管理员</el-tag>
          <el-tag v-else type="info" size="small">普通用户</el-tag>
        </div>
      </div>

      <!-- 详细信息 -->
      <el-descriptions :column="2" border class="profile-info">
        <el-descriptions-item label="用户名">{{ userStore.user?.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ userStore.user?.email || '-' }}</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ userStore.user?.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag
            v-for="role in userStore.user?.roles || []"
            :key="role"
            size="small"
            class="role-tag"
          >
            {{ role }}
          </el-tag>
          <span v-if="!userStore.user?.roles?.length">-</span>
        </el-descriptions-item>
        <el-descriptions-item label="账号状态">
          <el-tag :type="userStore.user?.is_active ? 'success' : 'danger'" size="small">
            {{ userStore.user?.is_active ? '已激活' : '已禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="注册时间">
          {{ formatTime(userStore.user?.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="最后登录">
          {{ formatTime(userStore.user?.last_login_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="用户 ID">{{ userStore.user?.id || '-' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 刷新按钮 -->
      <div class="profile-actions">
        <el-button type="primary" :loading="loading" @click="refreshProfile">
          <el-icon><Refresh /></el-icon>刷新信息
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const isAdministrator = computed(() => userStore.isAdmin)

/** 刷新用户信息 */
async function refreshProfile() {
  loading.value = true
  try {
    await userStore.fetchUserInfo()
    ElMessage.success('个人信息已刷新')
  } catch (error) {
    ElMessage.error('刷新失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

/** 格式化时间 */
function formatTime(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(() => {
  // 页面加载时刷新一次用户信息
  refreshProfile()
})
</script>

<style lang="scss" scoped>
.profile-page {
  display: flex;
  justify-content: center;
  padding: $spacing-xl;
  background: $bg-color;
  min-height: calc(100vh - #{$header-height} - 40px);
}

.profile-card {
  width: 100%;
  max-width: 640px;
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-xl;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: $spacing-lg;
  margin-bottom: $spacing-xl;
  padding-bottom: $spacing-lg;
  border-bottom: 1px solid #ebeef5;
}

.profile-avatar {
  flex-shrink: 0;
}

.profile-name {
  h2 {
    margin: 0 0 $spacing-sm;
    font-size: 22px;
    color: $text-primary;
  }
}

.profile-info {
  margin-bottom: $spacing-lg;
}

.role-tag {
  margin-right: 4px;
}

.profile-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: $spacing-md;
}
</style>
