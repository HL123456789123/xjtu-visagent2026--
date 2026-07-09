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
            v-for="role in row.roles"
            :key="role"
            size="small"
            :type="getRoleTagType(role)"
            style="margin-right: 4px"
          >
            {{ getRoleDisplayName(role) }}
          </el-tag>
          <span v-if="!row.roles?.length" class="text-muted">无角色</span>
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
          <el-button size="small" text @click="openRoleDialog(row)">分配角色</el-button>
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

    <!-- 分配角色弹窗 -->
    <el-dialog v-model="showRoleDialog" title="分配角色" width="500px">
      <div class="role-assign-info">
        <p>为用户 <strong>{{ currentUser?.username }}</strong> 分配角色：</p>
      </div>
      <el-checkbox-group v-model="selectedRoleIds">
        <el-checkbox
          v-for="role in allRoles"
          :key="role.id"
          :value="role.id"
          style="display: block; margin-bottom: 8px"
        >
          <span>{{ role.display_name }}</span>
          <span class="role-desc">（{{ role.description || role.name }}）</span>
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="showRoleDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRoleAssign" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import {
  getUserListApi,
  updateUserApi,
  assignUserRolesApi,
  toggleUserStatusApi,
  deleteUserApi,
  getRoleListApi,
} from '@/api/admin'

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

// 角色分配弹窗
const showRoleDialog = ref(false)
const currentUser = ref(null)
const allRoles = ref([])
const selectedRoleIds = ref([])
const submitting = ref(false)

// 角色显示名映射
const roleDisplayNames = {
  super_admin: '超级管理员',
  admin: '管理员',
  operator: '操作员',
  user: '普通用户',
  viewer: '访客',
}

// 获取角色显示名
function getRoleDisplayName(roleName) {
  return roleDisplayNames[roleName] || roleName
}

// 获取角色标签类型
function getRoleTagType(roleName) {
  const typeMap = {
    super_admin: 'danger',
    admin: 'warning',
    operator: 'info',
    user: 'info',
    viewer: 'info',
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

// 加载角色列表
async function loadRoles() {
  try {
    const res = await getRoleListApi()
    allRoles.value = res.data || []
  } catch (error) {
    console.error('加载角色列表失败:', error)
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

// 打开角色分配弹窗
function openRoleDialog(user) {
  currentUser.value = user
  // 根据当前用户角色名匹配角色ID
  const userRoleNames = user.roles || []
  const matchedRoles = allRoles.value.filter((r) => userRoleNames.includes(r.name))
  selectedRoleIds.value = matchedRoles.map((r) => r.id)
  showRoleDialog.value = true
}

// 提交角色分配
async function submitRoleAssign() {
  submitting.value = true
  try {
    await assignUserRolesApi(currentUser.value.id, {
      role_ids: selectedRoleIds.value,
    })
    ElMessage.success('角色分配成功')
    showRoleDialog.value = false
    loadUsers()
  } catch (error) {
    console.error('分配角色失败:', error)
    ElMessage.error(error.response?.data?.detail || '分配角色失败')
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
  loadRoles()
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

.role-desc {
  color: #909399;
  font-size: 12px;
}
</style>
