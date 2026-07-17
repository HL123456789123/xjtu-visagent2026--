<template>
  <div class="role-manage-page">
    <div class="page-header">
      <div>
        <h2>角色管理</h2>
        <p>管理员可以升级普通用户；只有超级管理员可以降级管理员。</p>
      </div>
      <div class="search-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索用户名或邮箱"
          clearable
          style="width: 260px"
          @clear="searchUsers"
          @keyup.enter="searchUsers"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="searchUsers">
          <el-icon><Search /></el-icon>搜索
        </el-button>
      </div>
    </div>

    <el-alert
      title="权限规则"
      type="info"
      :closable="false"
      show-icon
      class="permission-alert"
    >
      <template #default>
        普通管理员可以将普通用户升级为管理员，但不能降级、禁用或删除管理员；超级管理员
        可以管理其他管理员，但不能修改自身身份。
      </template>
    </el-alert>

    <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="160" />
      <el-table-column prop="email" label="邮箱" min-width="220" />
      <el-table-column label="当前身份" width="140">
        <template #default="{ row }">
          <el-tag :type="getRoleTagType(getUserRole(row))">
            {{ getRoleDisplayName(getUserRole(row)) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="!isAdminUser(row)"
            size="small"
            type="primary"
            plain
            @click="changeRole(row, 'admin')"
          >
            升级为管理员
          </el-button>
          <el-button
          v-else-if="isAdminUser(row) && !isSuperAdminUser(row)"
            size="small"
            type="warning"
            plain
            :disabled="!canDemote(row)"
            @click="changeRole(row, 'user')"
          >
            降为普通用户
          </el-button>
          <span v-else class="protected-text">超级管理员不可调整</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadUsers"
        @current-change="loadUsers"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getUserListApi, updateUserRoleApi } from '@/api/admin'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const users = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')

function isAdminUser(user) {
  return Boolean(user.is_superuser)
    || user.roles?.some((role) => role === 'admin' || role === 'super_admin')
}

function isSuperAdminUser(user) {
  return Boolean(user.is_superuser) || user.roles?.includes('super_admin')
}

function getUserRole(user) {
  if (isSuperAdminUser(user)) return 'super_admin'
  return isAdminUser(user) ? 'admin' : 'user'
}

function getRoleDisplayName(role) {
  return {
    super_admin: '超级管理员',
    admin: '管理员',
    user: '普通用户',
  }[role]
}

function getRoleTagType(role) {
  return { super_admin: 'danger', admin: 'warning', user: 'info' }[role] || 'info'
}

function canDemote(user) {
  return userStore.isSuperAdmin
    && user.id !== userStore.user?.id
    && !isSuperAdminUser(user)
}

async function loadUsers() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchKeyword.value.trim()) params.keyword = searchKeyword.value.trim()
    const response = await getUserListApi(params)
    users.value = response.data?.items || []
    total.value = response.data?.total || 0
  } catch (error) {
    console.error('加载用户角色失败:', error)
    ElMessage.error('加载用户角色失败')
  } finally {
    loading.value = false
  }
}

function searchUsers() {
  currentPage.value = 1
  loadUsers()
}

async function changeRole(user, role) {
  const action = role === 'admin' ? '升级为管理员' : '降为普通用户'
  try {
    await ElMessageBox.confirm(`确定将“${user.username}”${action}吗？`, '确认身份变更', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: role === 'admin' ? 'warning' : 'error',
    })
    await updateUserRoleApi(user.id, { role })
    ElMessage.success(`已将“${user.username}”${action}`)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('更新用户身份失败:', error)
      ElMessage.error(error.response?.data?.message || '更新用户身份失败')
    }
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.role-manage-page {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
  font-size: 20px;
}

.page-header p {
  margin: 8px 0 0;
  color: #909399;
  font-size: 13px;
}

.search-actions {
  display: flex;
  gap: 12px;
}

.permission-alert {
  margin-bottom: 20px;
}

.protected-text {
  color: #909399;
  font-size: 13px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

@media (max-width: 760px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
