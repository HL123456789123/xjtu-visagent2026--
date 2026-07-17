<template>
  <div class="user-manage-page">
    <div class="page-header">
      <h2>用户管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>新增用户
        </el-button>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索用户名或邮箱"
          clearable
          style="width: 240px"
          @clear="searchUsers"
          @keyup.enter="searchUsers"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select
          v-model="filterActive"
          placeholder="状态筛选"
          clearable
          style="width: 120px"
          @change="searchUsers"
        >
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-button @click="searchUsers">
          <el-icon><Search /></el-icon>搜索
        </el-button>
      </div>
    </div>

    <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="email" label="邮箱" min-width="200" />
      <el-table-column prop="phone" label="手机号" width="140">
        <template #default="{ row }">
          {{ row.phone || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="身份" width="120">
        <template #default="{ row }">
          <el-tag :type="getRoleTagType(getUserRole(row))" size="small">
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
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEditDialog(row)">编辑</el-button>
          <el-button
            size="small"
            text
            :type="row.is_active ? 'warning' : 'success'"
            :disabled="!canManageAccount(row)"
            @click="toggleUserStatus(row)"
          >
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-button
            size="small"
            text
            type="danger"
            :disabled="!canManageAccount(row)"
            @click="deleteUser(row)"
          >
            删除
          </el-button>
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

    <el-dialog v-model="showCreateDialog" title="新增用户" width="500px">
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="90px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="3-50 个字符" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="createForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            placeholder="至少 6 个字符"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">
          创建
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEditDialog" title="编辑用户" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input :value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="editForm.phone" placeholder="请输入手机号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEdit">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import {
  createUserApi,
  deleteUserApi,
  getUserListApi,
  toggleUserStatusApi,
  updateUserApi,
} from '@/api/admin'

const userStore = useUserStore()
const users = ref([])
const loading = ref(false)
const submitting = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const filterActive = ref(null)

const showCreateDialog = ref(false)
const createFormRef = ref(null)
const createForm = ref({ username: '', email: '', password: '' })
const createRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度为 3-50 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    { min: 6, max: 100, message: '密码长度为 6-100 个字符', trigger: 'blur' },
  ],
}

const showEditDialog = ref(false)
const editForm = ref({ id: null, username: '', email: '', phone: '' })

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

function canManageAccount(user) {
  if (user.id === userStore.user?.id) return false
  if (isAdminUser(user) && !userStore.isSuperAdmin) return false
  return true
}

function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function loadUsers() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchKeyword.value.trim()) params.keyword = searchKeyword.value.trim()
    if (filterActive.value !== null) params.is_active = filterActive.value
    const response = await getUserListApi(params)
    users.value = response.data?.items || []
    total.value = response.data?.total || 0
  } catch (error) {
    console.error('加载用户列表失败:', error)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

function searchUsers() {
  currentPage.value = 1
  loadUsers()
}

function openCreateDialog() {
  createForm.value = { username: '', email: '', password: '' }
  showCreateDialog.value = true
}

async function submitCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await createUserApi(createForm.value)
    ElMessage.success('用户创建成功')
    showCreateDialog.value = false
    searchUsers()
  } catch (error) {
    console.error('创建用户失败:', error)
    ElMessage.error(error.response?.data?.message || '创建用户失败')
  } finally {
    submitting.value = false
  }
}

function openEditDialog(user) {
  editForm.value = {
    id: user.id,
    username: user.username,
    email: user.email,
    phone: user.phone || '',
  }
  showEditDialog.value = true
}

async function submitEdit() {
  submitting.value = true
  try {
    await updateUserApi(editForm.value.id, {
      email: editForm.value.email,
      phone: editForm.value.phone || null,
    })
    ElMessage.success('用户信息更新成功')
    showEditDialog.value = false
    loadUsers()
  } catch (error) {
    console.error('更新用户失败:', error)
    ElMessage.error(error.response?.data?.message || '更新用户失败')
  } finally {
    submitting.value = false
  }
}

async function toggleUserStatus(user) {
  if (!canManageAccount(user)) return
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}用户“${user.username}”吗？`, '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await toggleUserStatusApi(user.id, { is_active: !user.is_active })
    ElMessage.success(`用户已${action}`)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error(`${action}用户失败:`, error)
      ElMessage.error(error.response?.data?.message || `${action}用户失败`)
    }
  }
}

async function deleteUser(user) {
  if (!canManageAccount(user)) return
  try {
    await ElMessageBox.confirm(`确定要删除用户“${user.username}”吗？此操作不可恢复。`, '确认删除', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'error',
    })
    await deleteUserApi(user.id)
    ElMessage.success('用户已删除')
    if (users.value.length === 1 && currentPage.value > 1) currentPage.value -= 1
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除用户失败:', error)
      ElMessage.error(error.response?.data?.message || '删除用户失败')
    }
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.user-manage-page {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

@media (max-width: 900px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    justify-content: flex-start;
  }
}
</style>
