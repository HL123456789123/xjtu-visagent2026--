<template>
  <main class="user-manage-page">
    <header class="page-heading">
      <div>
        <h1>用户管理</h1>
        <p>管理员可管理普通用户并晋升管理员；管理员账号的危险操作仅限超级管理员。</p>
      </div>
    </header>

    <section class="user-toolbar" aria-label="用户筛选">
      <el-input
        v-model="keyword"
        clearable
        placeholder="搜索用户名或邮箱"
        :prefix-icon="Search"
        @keyup.enter="loadUsers"
        @clear="loadUsers"
      />
      <el-select v-model="activeFilter" clearable placeholder="全部状态" @change="loadUsers">
        <el-option label="已启用" :value="true" />
        <el-option label="已禁用" :value="false" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="loadUsers">查询</el-button>
    </section>

    <section class="user-table" v-loading="loading">
      <el-table :data="users" stripe>
        <el-table-column prop="username" label="用户名" min-width="130" />
        <el-table-column prop="email" label="邮箱" min-width="210" />
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            <el-tag :type="roleTagType(productRole(row))">{{ roleLabel(productRole(row)) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '已启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="320" fixed="right">
          <template #default="{ row }">
            <div v-if="canManage(row)" class="row-actions">
              <el-button
                v-if="productRole(row) === 'user'"
                size="small"
                :icon="Promotion"
                @click="changeRole(row, 'admin')"
              >设为管理员</el-button>
              <el-button
                v-if="userStore.isSuperAdmin && productRole(row) === 'admin'"
                size="small"
                @click="changeRole(row, 'user')"
              >降为普通用户</el-button>
              <el-button size="small" :icon="Lock" @click="openPasswordDialog(row)">重置密码</el-button>
              <el-button
                size="small"
                :type="row.is_active ? 'warning' : 'success'"
                @click="toggleStatus(row)"
              >{{ row.is_active ? '禁用' : '启用' }}</el-button>
              <el-button size="small" type="danger" :icon="Delete" @click="removeUser(row)">删除</el-button>
            </div>
            <span v-else class="protected-text">受保护账号</span>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadUsers"
        @size-change="loadUsers"
      />
    </section>

    <el-dialog v-model="passwordDialog" title="重置密码" width="420px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="新密码">
          <el-input
            v-model="newPassword"
            type="password"
            show-password
            maxlength="72"
            autocomplete="new-password"
          />
        </el-form-item>
        <p class="dialog-tip">密码至少 8 位，不会写入操作日志。</p>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialog = false">取消</el-button>
        <el-button type="primary" :disabled="newPassword.length < 8" @click="resetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Delete, Lock, Promotion, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteUserApi,
  getUserListApi,
  resetUserPasswordApi,
  setUserRoleApi,
  toggleUserStatusApi,
} from '@/api/admin'
import { useUserStore } from '@/stores/user'
import { formatTime } from '@/utils/format'

const userStore = useUserStore()
const users = ref([])
const loading = ref(false)
const keyword = ref('')
const activeFilter = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const passwordDialog = ref(false)
const passwordTarget = ref(null)
const newPassword = ref('')

function productRole(row) {
  const roles = row.roles || []
  if (roles.includes('super_admin')) return 'super_admin'
  if (roles.includes('admin')) return 'admin'
  return 'user'
}

function roleLabel(role) {
  return { super_admin: '超级管理员', admin: '管理员', user: '普通用户' }[role]
}

function roleTagType(role) {
  return { super_admin: 'danger', admin: 'warning', user: 'info' }[role]
}

function canManage(row) {
  if (row.id === userStore.user?.id || productRole(row) === 'super_admin') return false
  return productRole(row) === 'user' || userStore.isSuperAdmin
}

async function loadUsers() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (typeof activeFilter.value === 'boolean') params.is_active = activeFilter.value
    const response = await getUserListApi(params)
    users.value = response.data?.items || []
    total.value = response.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function changeRole(row, role) {
  const action = role === 'admin' ? '设为管理员' : '降为普通用户'
  await ElMessageBox.confirm(`确定将“${row.username}”${action}吗？`, '确认角色调整')
  await setUserRoleApi(row.id, role)
  ElMessage.success('角色已更新')
  await loadUsers()
}

async function toggleStatus(row) {
  const next = !row.is_active
  await ElMessageBox.confirm(`确定${next ? '启用' : '禁用'}“${row.username}”吗？`, '确认状态调整')
  await toggleUserStatusApi(row.id, next)
  ElMessage.success(next ? '用户已启用' : '用户已禁用')
  await loadUsers()
}

function openPasswordDialog(row) {
  passwordTarget.value = row
  newPassword.value = ''
  passwordDialog.value = true
}

async function resetPassword() {
  if (!passwordTarget.value || newPassword.value.length < 8) return
  await resetUserPasswordApi(passwordTarget.value.id, newPassword.value)
  passwordDialog.value = false
  newPassword.value = ''
  ElMessage.success('密码已重置')
}

async function removeUser(row) {
  await ElMessageBox.confirm(
    `确定删除“${row.username}”吗？已有业务数据的账号不会被直接删除。`,
    '确认删除',
    { type: 'warning' },
  )
  await deleteUserApi(row.id)
  ElMessage.success('用户已删除')
  await loadUsers()
}

onMounted(loadUsers)
</script>

<style lang="scss" scoped>
.user-manage-page { min-height: calc(100vh - #{$header-height}); background: #f7f6f2; padding: 24px; }
.page-heading h1 { margin: 0; color: #302a24; font-size: 24px; }
.page-heading p { margin: 6px 0 0; color: #766d64; font-size: 14px; }
.user-toolbar { display: grid; grid-template-columns: minmax(240px, 1fr) 160px auto; gap: 12px; margin: 20px 0 14px; }
.user-table { padding: 16px; border: 1px solid #e7e3dc; border-radius: 8px; background: #fff; }
.row-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.protected-text, .dialog-tip { color: #8a8178; font-size: 13px; }
.el-pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 720px) { .user-toolbar { grid-template-columns: 1fr; } .user-manage-page { padding: 14px; } }
</style>
