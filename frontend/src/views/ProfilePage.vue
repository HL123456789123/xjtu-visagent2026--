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
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)

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
  padding: clamp(22px, 5vw, 58px);
  background:
    radial-gradient(circle at 12% 10%, rgba(255, 213, 118, 0.34), transparent 28%),
    radial-gradient(circle at 86% 8%, rgba(137, 169, 79, 0.18), transparent 26%),
    linear-gradient(180deg, #fff8ea 0%, #fffdf7 48%, #f8efe3 100%);
  min-height: calc(100vh - #{$header-height});
  color: #3a2a1d;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
}

.profile-card {
  width: 100%;
  max-width: 780px;
  border: 1px solid rgba(121, 82, 45, 0.12);
  background:
    radial-gradient(circle at 100% 0, rgba(246, 190, 74, 0.2), transparent 28%),
    rgba(255, 255, 255, 0.82);
  border-radius: 32px;
  padding: clamp(24px, 4vw, 40px);
  box-shadow: 0 26px 76px rgba(102, 68, 35, 0.14);
  backdrop-filter: blur(18px);
}

.profile-header {
  display: flex;
  align-items: center;
  gap: $spacing-lg;
  margin-bottom: $spacing-xl;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(121, 82, 45, 0.12);
}

.profile-avatar {
  flex-shrink: 0;
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  color: #fffaf0;
  box-shadow: 0 16px 34px rgba(229, 104, 52, 0.22);
}

.profile-name {
  h2 {
    margin: 0 0 $spacing-sm;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 36px;
    font-weight: 500;
  }

  :deep(.el-tag) {
    border: 0;
    border-radius: 999px;
    background: #fff1d2;
    color: #d76626;
    font-weight: 800;
  }
}

.profile-info {
  margin-bottom: $spacing-lg;

  :deep(.el-descriptions__label) {
    background: #fff1d2;
    color: #6f5038;
    font-weight: 900;
  }

  :deep(.el-descriptions__content) {
    color: #3a2a1d;
    background: rgba(255, 252, 245, 0.78);
  }

  :deep(.el-descriptions__cell) {
    border-color: rgba(121, 82, 45, 0.12) !important;
  }
}

.role-tag {
  margin-right: 4px;
}

.profile-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: $spacing-md;

  :deep(.el-button) {
    border: 0;
    border-radius: 16px;
    background: linear-gradient(135deg, #f1a93b, #e96d3b);
    color: #fffaf0;
    font-weight: 900;
    box-shadow: 0 14px 30px rgba(229, 104, 52, 0.22);
  }
}

@media (max-width: 560px) {
  .profile-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
