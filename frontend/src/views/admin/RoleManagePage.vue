<template>
  <div class="role-manage-page">
    <div class="page-header">
      <h2>角色管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>新建角色
      </el-button>
    </div>

    <!-- 角色列表表格 -->
    <el-table :data="roles" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="角色标识" width="120" />
      <el-table-column prop="display_name" label="显示名称" width="120" />
      <el-table-column prop="description" label="描述" min-width="180">
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="系统角色" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_system" type="info" size="small">系统内置</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="权限数" width="80">
        <template #default="{ row }">
          {{ row.permissions?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column label="用户数" width="80">
        <template #default="{ row }">
          {{ row.user_count || 0 }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" text @click="openPermissionDialog(row)">分配权限</el-button>
          <el-button
            size="small"
            text
            type="danger"
            :disabled="row.is_system"
            @click="deleteRole(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建/编辑角色弹窗 -->
    <el-dialog
      v-model="showFormDialog"
      :title="isEditing ? '编辑角色' : '新建角色'"
      width="500px"
    >
      <el-form :model="roleForm" :rules="formRules" ref="formRef" label-width="100px">
        <el-form-item label="角色标识" prop="name">
          <el-input
            v-model="roleForm.name"
            placeholder="如：editor"
            :disabled="isEditing"
          />
        </el-form-item>
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="roleForm.display_name" placeholder="如：编辑者" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="roleForm.description"
            type="textarea"
            :rows="3"
            placeholder="角色描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFormDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRoleForm" :loading="submitting">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 权限分配弹窗 -->
    <el-dialog v-model="showPermissionDialog" title="分配权限" width="600px">
      <div class="permission-assign-info">
        <p>为角色 <strong>{{ currentRole?.display_name }}</strong> 分配权限：</p>
        <span>已选择 {{ selectedPermissionCount }} / {{ totalPermissionCount }} 项权限</span>
      </div>
      <div v-loading="loadingPermissions" class="permission-groups">
        <div v-for="group in permissionGroups" :key="group.module" class="permission-group">
          <div class="group-header">
            <el-checkbox
              :model-value="isModuleAllSelected(group.module)"
              :indeterminate="isModuleIndeterminate(group.module)"
              @change="(val) => toggleModuleAll(group.module, val)"
            >
              <strong>{{ getModuleName(group.module) }}</strong>
              <span class="group-count">{{ getModuleSelectedCount(group.module) }} / {{ group.permissions.length }}</span>
            </el-checkbox>
          </div>
          <div class="group-items">
            <el-checkbox-group v-model="selectedPermissionCodes">
              <el-checkbox
                v-for="perm in group.permissions"
                :key="perm.code"
                :value="perm.code"
              >
                {{ perm.name }}
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showPermissionDialog = false">取消</el-button>
        <el-button type="primary" @click="submitPermissionAssign" :loading="submitting">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getRoleListApi,
  getRoleDetailApi,
  createRoleApi,
  updateRoleApi,
  deleteRoleApi,
  assignRolePermissionsApi,
  getPermissionListApi,
} from '@/api/admin'

// 角色列表
const roles = ref([])
const loading = ref(false)

// 表单弹窗
const showFormDialog = ref(false)
const isEditing = ref(false)
const formRef = ref(null)
const roleForm = ref({
  id: null,
  name: '',
  display_name: '',
  description: '',
})
const formRules = {
  name: [
    { required: true, message: '请输入角色标识', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' },
    { pattern: /^[a-z_]+$/, message: '只能包含小写字母和下划线', trigger: 'blur' },
  ],
  display_name: [
    { required: true, message: '请输入显示名称', trigger: 'blur' },
  ],
}

// 权限分配弹窗
const showPermissionDialog = ref(false)
const currentRole = ref(null)
const permissionGroups = ref([])
const selectedPermissionCodes = ref([])
const loadingPermissions = ref(false)
const submitting = ref(false)

const totalPermissionCount = computed(() =>
  permissionGroups.value.reduce((sum, group) => sum + group.permissions.length, 0)
)

const selectedPermissionCount = computed(() => selectedPermissionCodes.value.length)

// 模块显示名映射
const moduleNames = {
  auth: '用户与权限',
  detection: '检测模块',
  training: '训练模块',
  model: '模型管理',
  agent: '智能对话',
  knowledge: '知识库',
  system: '系统管理',
}

// 获取模块显示名
function getModuleName(module) {
  return moduleNames[module] || module
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

// 加载角色列表
async function loadRoles() {
  loading.value = true
  try {
    const res = await getRoleListApi()
    roles.value = res.data || []
  } catch (error) {
    console.error('加载角色列表失败:', error)
    ElMessage.error('加载角色列表失败')
  } finally {
    loading.value = false
  }
}

// 加载权限列表
async function loadPermissions() {
  loadingPermissions.value = true
  try {
    const res = await getPermissionListApi()
    permissionGroups.value = res.data || []
  } catch (error) {
    console.error('加载权限列表失败:', error)
    ElMessage.error('加载权限列表失败')
  } finally {
    loadingPermissions.value = false
  }
}

// 打开创建弹窗
function openCreateDialog() {
  isEditing.value = false
  roleForm.value = {
    id: null,
    name: '',
    display_name: '',
    description: '',
  }
  showFormDialog.value = true
}

// 打开编辑弹窗
function openEditDialog(role) {
  isEditing.value = true
  roleForm.value = {
    id: role.id,
    name: role.name,
    display_name: role.display_name,
    description: role.description || '',
  }
  showFormDialog.value = true
}

// 提交角色表单
async function submitRoleForm() {
  const form = formRef.value
  if (form) {
    try {
      await form.validate()
    } catch {
      return
    }
  }

  submitting.value = true
  try {
    if (isEditing.value) {
      await updateRoleApi(roleForm.value.id, {
        display_name: roleForm.value.display_name,
        description: roleForm.value.description,
      })
      ElMessage.success('角色更新成功')
    } else {
      await createRoleApi({
        name: roleForm.value.name,
        display_name: roleForm.value.display_name,
        description: roleForm.value.description,
      })
      ElMessage.success('角色创建成功')
    }
    showFormDialog.value = false
    loadRoles()
  } catch (error) {
    console.error('保存角色失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存角色失败')
  } finally {
    submitting.value = false
  }
}

// 打开权限分配弹窗
async function openPermissionDialog(role) {
  currentRole.value = role
  selectedPermissionCodes.value = [...(role.permissions || [])]
  showPermissionDialog.value = true
  loadingPermissions.value = true
  try {
    const [detailRes] = await Promise.all([
      getRoleDetailApi(role.id),
      loadPermissions(),
    ])
    currentRole.value = detailRes.data || role
    selectedPermissionCodes.value = [...(currentRole.value.permissions || [])]
  } catch (error) {
    console.error('加载角色权限详情失败:', error)
    ElMessage.error('加载角色权限详情失败')
  } finally {
    loadingPermissions.value = false
  }
}

// 判断模块是否全选
function isModuleAllSelected(module) {
  const group = permissionGroups.value.find((g) => g.module === module)
  if (!group) return false
  return group.permissions.every((p) => selectedPermissionCodes.value.includes(p.code))
}

// 判断模块是否半选
function isModuleIndeterminate(module) {
  const group = permissionGroups.value.find((g) => g.module === module)
  if (!group) return false
  const selectedCount = group.permissions.filter((p) =>
    selectedPermissionCodes.value.includes(p.code)
  ).length
  return selectedCount > 0 && selectedCount < group.permissions.length
}

function getModuleSelectedCount(module) {
  const group = permissionGroups.value.find((g) => g.module === module)
  if (!group) return 0
  return group.permissions.filter((p) => selectedPermissionCodes.value.includes(p.code)).length
}

// 切换模块全选
function toggleModuleAll(module, checked) {
  const group = permissionGroups.value.find((g) => g.module === module)
  if (!group) return
  const moduleCodes = group.permissions.map((p) => p.code)
  if (checked) {
    // 添加模块所有权限
    const newCodes = [...new Set([...selectedPermissionCodes.value, ...moduleCodes])]
    selectedPermissionCodes.value = newCodes
  } else {
    // 移除模块所有权限
    selectedPermissionCodes.value = selectedPermissionCodes.value.filter(
      (code) => !moduleCodes.includes(code)
    )
  }
}

// 提交权限分配
async function submitPermissionAssign() {
  submitting.value = true
  try {
    await assignRolePermissionsApi(currentRole.value.id, {
      permission_codes: selectedPermissionCodes.value,
    })
    ElMessage.success('权限分配成功')
    showPermissionDialog.value = false
    loadRoles()
  } catch (error) {
    console.error('分配权限失败:', error)
    ElMessage.error(error.response?.data?.detail || '分配权限失败')
  } finally {
    submitting.value = false
  }
}

// 删除角色
async function deleteRole(role) {
  if (role.is_system) {
    ElMessage.warning('系统内置角色不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除角色 "${role.display_name}" 吗？此操作不可恢复！`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'error',
      }
    )
    await deleteRoleApi(role.id)
    ElMessage.success('角色已删除')
    loadRoles()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除角色失败:', error)
      ElMessage.error(error.response?.data?.detail || '删除角色失败')
    }
  }
}

// 初始化
onMounted(() => {
  loadRoles()
})
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
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.permission-assign-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  color: #606266;
}

.permission-assign-info p {
  margin: 0;
}

.permission-assign-info span {
  color: #409eff;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.permission-groups {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
}

.permission-group {
  margin-bottom: 16px;
}

.permission-group:last-child {
  margin-bottom: 0;
}

.group-header {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.group-count {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
  font-weight: 500;
}

.group-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding-left: 24px;
}
</style>
