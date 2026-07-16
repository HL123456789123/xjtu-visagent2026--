<template>
  <div class="user-manage-page">
    <div class="page-header">
      <h2>用户管理</h2>
      <div class="header-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索用户名或邮箱"
          clearable
          style="width: 240px"
          @clear="loadUsers"
          @keyup.enter="loadUsers"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="filterActive" placeholder="状态筛选" clearable style="width: 120px" @change="loadUsers">
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-button type="primary" @click="loadUsers">
          <el-icon><Search /></el-icon>搜索
        </el-button>
      </div>
    </div>

    <!-- 用户列表表格 -->
    <el-table :data="users" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column prop="phone" label="手机号" width="120">
        <template #default="{ row }">
          {{ row.phone || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="角色" min-width="150">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="getRoleTagType(getUserRole(row))"
          >
            {{ getRoleDisplayName(getUserRole(row)) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" width="160">
        <template #default="{ row }">
          {{ row.last_login_at ? formatTime(row.last_login_at) : '从未登录' }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEditDialog(row)">编辑</el-button>
          <el-button
            size="small"
            text
            :disabled="row.id === userStore.user?.id"
            @click="openRoleDialog(row)"
          >
            更改身份
          </el-button>
          <el-button
            size="small"
            text
            :type="row.is_active ? 'warning' : 'success'"
            @click="toggleUserStatus(row)"
          >
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-button size="small" text type="danger" @click="deleteUser(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
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

    <!-- 编辑用户弹窗 -->
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
        <el-button type="primary" @click="submitEdit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 更改身份弹窗 -->
    <el-dialog v-model="showRoleDialog" title="更改身份" width="500px">
      <div class="role-assign-info">
        <p>设置用户 <strong>{{ currentUser?.username }}</strong> 的身份：</p>
      </div>
      <el-radio-group v-model="selectedRole" class="role-options">
        <el-radio value="user">普通用户</el-radio>
        <el-radio value="admin">管理员</el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="showRoleDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRoleUpdate" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import {
  getUserListApi,
  updateUserApi,
  updateUserRoleApi,
  toggleUserStatusApi,
  deleteUserApi,
} from '@/api/admin'

const userStore = useUserStore()

// 列表数据
const users = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const filterActive = ref(null)

// 编辑弹窗
const showEditDialog = ref(false)
const editForm = ref({
  id: null,
  username: '',
  email: '',
  phone: '',
})

// 身份设置弹窗
const showRoleDialog = ref(false)
const currentUser = ref(null)
const selectedRole = ref('user')
const submitting = ref(false)

// 角色显示名映射
const roleDisplayNames = {
  admin: '管理员',
  user: '普通用户',
}

// 兼容旧数据中的历史角色，对外统一收敛为管理员/普通用户两种身份。
function getUserRole(user) {
  return user.roles?.some((role) => role === 'admin' || role === 'super_admin')
    ? 'admin'
    : 'user'
}

// 获取角色显示名
function getRoleDisplayName(roleName) {
  return roleDisplayNames[roleName] || roleName
}

// 获取角色标签类型
function getRoleTagType(roleName) {
  const typeMap = {
    admin: 'warning',
    user: 'info',
  }
  return typeMap[roleName] || 'info'
}

// 格式化时间
function formatTime(timeStr) {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 加载用户列表
async function loadUsers() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    if (filterActive.value !== null) {
      params.is_active = filterActive.value
    }
    const res = await getUserListApi(params)
    users.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (error) {
    console.error('加载用户列表失败:', error)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

// 打开编辑弹窗
function openEditDialog(user) {
  editForm.value = {
    id: user.id,
    username: user.username,
    email: user.email,
    phone: user.phone || '',
  }
  showEditDialog.value = true
}

// 提交编辑
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
    ElMessage.error(error.response?.data?.detail || '更新用户失败')
  } finally {
    submitting.value = false
  }
}

// 打开身份设置弹窗
function openRoleDialog(user) {
  if (user.id === userStore.user?.id) {
    ElMessage.warning('不能修改自身身份')
    return
  }
  currentUser.value = user
  selectedRole.value = getUserRole(user)
  showRoleDialog.value = true
}

// 提交身份更新
async function submitRoleUpdate() {
  submitting.value = true
  try {
    await updateUserRoleApi(currentUser.value.id, {
      role: selectedRole.value,
    })
    ElMessage.success('用户身份更新成功')
    showRoleDialog.value = false
    loadUsers()
  } catch (error) {
    console.error('更新用户身份失败:', error)
    ElMessage.error(error.response?.data?.message || '更新用户身份失败')
  } finally {
    submitting.value = false
  }
}

// 启用/禁用用户
async function toggleUserStatus(user) {
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}用户 "${user.username}" 吗？`, '确认操作', {
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
      ElMessage.error(error.response?.data?.detail || `${action}用户失败`)
    }
  }
}

// 删除用户
async function deleteUser(user) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.username}" 吗？此操作不可恢复！`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'error',
      }
    )
    await deleteUserApi(user.id)
    ElMessage.success('用户已删除')
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除用户失败:', error)
      ElMessage.error(error.response?.data?.detail || '删除用户失败')
    }
  }
}

// 初始化
onMounted(() => {
  loadUsers()
})
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
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.text-muted {
  color: #909399;
  font-size: 12px;
}

.role-assign-info {
  margin-bottom: 16px;
  color: #606266;
}

.role-options {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
</style>
