<template>
  <div class="model-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h3>模型管理</h3>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>新建模型
        </el-button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <el-select v-model="filterCategory" placeholder="分类筛选" clearable @change="loadModels">
        <el-option label="通用" value="general" />
        <el-option label="工业" value="industrial" />
        <el-option label="安防" value="security" />
        <el-option label="交通" value="traffic" />
        <el-option label="农业" value="agriculture" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="状态筛选" clearable @change="loadModels">
        <el-option label="活跃" value="active" />
        <el-option label="已归档" value="archived" />
        <el-option label="已启用" value="enabled" />
        <el-option label="已禁用" value="disabled" />
      </el-select>
    </div>

    <!-- 模型列表 -->
    <div class="model-table-wrapper">
      <el-table
        :data="models"
        v-loading="loading"
        stripe
        style="width: 100%"
        empty-text="暂无模型"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="模型名称" min-width="160">
          <template #default="{ row }">
            <span>{{ row.name }}</span>
            <el-tag v-if="row.is_enabled === false" size="small" type="danger" style="margin-left: 6px">已禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="base_architecture" label="基础架构" width="110" />
        <el-table-column label="版本数" width="80">
          <template #default="{ row }">{{ row.version_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="适用场景" min-width="160">
          <template #default="{ row }">
            <template v-if="row.scene_names && row.scene_names.length">
              <el-tag v-for="name in row.scene_names" :key="name" type="success" size="small" style="margin-right: 4px">
                {{ name }}
              </el-tag>
            </template>
            <span v-else class="text-muted">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : '已归档' }}
            </el-tag>
            <el-tag :type="row.is_enabled !== false ? 'success' : 'danger'" size="small" style="margin-left: 4px">
              {{ row.is_enabled !== false ? '已启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button type="primary" size="small" link @click="showDetail(row)">详情</el-button>
              <el-button
                :type="row.is_enabled === false ? 'success' : 'warning'"
                size="small"
                link
                @click="toggleModel(row)"
              >
                {{ row.is_enabled === false ? '启用' : '禁用' }}
              </el-button>
              <el-button type="primary" size="small" link @click="openEditDialog(row)">编辑</el-button>
              <el-button type="primary" size="small" link @click="openExportDialog(row)">导出</el-button>
              <el-button type="danger" size="small" link @click="archiveModel(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 模型详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      title="模型详情"
      width="800px"
      destroy-on-close
    >
      <template v-if="currentModel">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="模型ID">{{ currentModel.id }}</el-descriptions-item>
          <el-descriptions-item label="模型名称">{{ currentModel.name }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ currentModel.category }}</el-descriptions-item>
          <el-descriptions-item label="基础架构">{{ currentModel.base_architecture }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="currentModel.status === 'active' ? 'success' : 'info'">
              {{ currentModel.status === 'active' ? '活跃' : '已归档' }}
            </el-tag>
            <el-tag :type="currentModel.is_enabled !== false ? 'success' : 'danger'" style="margin-left: 8px">
              {{ currentModel.is_enabled !== false ? '已启用' : '已禁用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentModel.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ currentModel.description || '无' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 版本列表 -->
        <div class="detail-section">
          <div class="section-header">
            <h4>模型版本</h4>
            <el-button size="small" @click="showImportDialog = true">
              <el-icon><Upload /></el-icon>导入
            </el-button>
          </div>
          <el-table :data="versions" stripe>
            <el-table-column prop="version" label="版本号" width="120" />
            <el-table-column prop="source" label="来源" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.source === 'training' ? 'success' : 'info'">
                  {{ row.source === 'training' ? '训练' : '上传' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="默认" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
                <el-button v-else size="small" text @click="setDefaultVersion(row.id)">设为默认</el-button>
              </template>
            </el-table-column>
            <el-table-column label="mAP50" width="100">
              <template #default="{ row }">
                {{ row.map50 ? row.map50.toFixed(3) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">
                  {{ row.status === 'active' ? '活跃' : '归档' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" min-width="140">
              <template #default="{ row }">
                <el-button size="small" text @click="exportVersion(row.id)">导出</el-button>
                <el-button
                  v-if="row.status === 'active'"
                  size="small"
                  text
                  type="danger"
                  @click="archiveVersion(row.id)"
                >归档</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 关联场景 -->
        <div class="detail-section">
          <div class="section-header">
            <h4>关联场景</h4>
            <el-button size="small" @click="showBindDialog = true">
              <el-icon><Link /></el-icon>绑定场景
            </el-button>
          </div>
          <el-table :data="boundScenes" stripe>
            <el-table-column prop="scene_id" label="场景ID" width="80" />
            <el-table-column prop="scene_name" label="场景名称" />
            <el-table-column label="默认" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" text type="danger" @click="unbindScene(row.scene_id)">解绑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="boundScenes.length === 0" class="empty-scenes">
            暂未关联任何场景
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 导出模型对话框 -->
    <el-dialog v-model="showExportDialog" title="导出模型" width="400px">
      <p>选择要导出的模型版本：</p>
      <el-select v-model="exportVersionId" placeholder="选择版本" style="width: 100%">
        <el-option
          v-for="v in versions"
          :key="v.id"
          :label="`${v.version}${v.is_default ? ' (默认)' : ''}`"
          :value="v.id"
        />
      </el-select>
      <template #footer>
        <el-button @click="showExportDialog = false">取消</el-button>
        <el-button type="primary" @click="doExportVersion" :loading="exporting">导出</el-button>
      </template>
    </el-dialog>

    <!-- 创建模型对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建模型" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="模型名称" required>
          <el-input v-model="createForm.name" placeholder="模型名称" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="createForm.category">
            <el-option label="通用" value="general" />
            <el-option label="工业" value="industrial" />
            <el-option label="安防" value="security" />
            <el-option label="交通" value="traffic" />
            <el-option label="农业" value="agriculture" />
          </el-select>
        </el-form-item>
        <el-form-item label="基础架构">
          <el-select v-model="createForm.base_architecture">
            <el-option label="YOLO26n (轻量)" value="yolo26n" />
            <el-option label="YOLO26s (小型)" value="yolo26s" />
            <el-option label="YOLO26m (中型)" value="yolo26m" />
            <el-option label="YOLO26l (大型)" value="yolo26l" />
            <el-option label="YOLO26x (超大)" value="yolo26x" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="模型描述（可选）" />
        </el-form-item>
        <el-form-item label="关联场景">
          <el-select v-model="createForm.scene_id" placeholder="选择场景（可选）" clearable>
            <el-option
              v-for="scene in allScenes"
              :key="scene.id"
              :label="scene.display_name"
              :value="scene.id"
            />
          </el-select>
          <div class="form-tip">可选，绑定后可在目标检测页面直接使用</div>
        </el-form-item>
        <el-form-item label="权重文件">
          <el-upload
            ref="createUploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".pt"
            :on-change="handleCreateFileChange"
            :on-remove="handleCreateFileRemove"
          >
            <el-button type="primary" size="small">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">可选，支持 .pt 格式权重文件；不选则仅创建模型元数据</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createModel" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑模型对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑模型" width="500px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="模型名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category">
            <el-option label="通用" value="general" />
            <el-option label="工业" value="industrial" />
            <el-option label="安防" value="security" />
            <el-option label="交通" value="traffic" />
            <el-option label="农业" value="agriculture" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="updateModel" :loading="updating">保存</el-button>
      </template>
    </el-dialog>

    <!-- 导入模型对话框 -->
    <el-dialog v-model="showImportDialog" title="导入模型版本" width="500px">
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="ZIP 文件" required>
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".zip"
            :on-change="handleImportFileChange"
          >
            <el-button type="primary" size="small">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持导出的 ZIP 格式模型包</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="版本说明">
          <el-input v-model="importForm.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="importModel" :loading="importing">导入</el-button>
      </template>
    </el-dialog>

    <!-- 绑定场景对话框 -->
    <el-dialog v-model="showBindDialog" title="绑定场景" width="400px">
      <el-form label-width="100px">
        <el-form-item label="选择场景">
          <el-select v-model="bindSceneId" placeholder="选择场景">
            <el-option
              v-for="scene in allScenes"
              :key="scene.id"
              :label="scene.display_name"
              :value="scene.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="bindIsDefault" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBindDialog = false">取消</el-button>
        <el-button type="primary" @click="bindScene" :loading="binding">绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Plus, Goods, Edit, Delete, Upload, Link } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getModelsApi,
  createModelApi,
  getModelApi,
  updateModelApi,
  deleteModelApi,
  toggleModelApi,
  setDefaultVersionApi,
  deleteVersionApi,
  exportModelApi,
  importModelApi,
  bindModelToSceneApi,
  unbindModelFromSceneApi
} from '@/api/model'
import { getScenesApi } from '@/api/detection'

// 模型列表
const models = ref([])
const loading = ref(false)
const currentModel = ref(null)
const filterCategory = ref('')
const filterStatus = ref('')

// 版本和场景
const versions = ref([])
const boundScenes = ref([])
const allScenes = ref([])

// 详情对话框
const showDetailDialog = ref(false)

// 导出对话框
const showExportDialog = ref(false)
const exportVersionId = ref(null)
const exporting = ref(false)

// 创建对话框
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  category: 'general',
  base_architecture: 'yolo26n',
  description: '',
  scene_id: null
})
const createWeightFile = ref(null)
const createUploadRef = ref(null)

// 编辑对话框
const showEditDialog = ref(false)
const updating = ref(false)
const editForm = ref({ name: '', description: '', category: '' })

// 导入对话框
const showImportDialog = ref(false)
const importing = ref(false)
const importForm = ref({ file: null, description: '' })

// 绑定场景对话框
const showBindDialog = ref(false)
const binding = ref(false)
const bindSceneId = ref(null)
const bindIsDefault = ref(false)

// 加载模型列表
async function loadModels() {
  loading.value = true
  try {
    const params = { page: 1, page_size: 100 }
    if (filterCategory.value) params.category = filterCategory.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getModelsApi(params)
    models.value = res.data?.items || []
  } catch (error) {
    console.error('加载模型列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 显示详情对话框
async function showDetail(model) {
  currentModel.value = model
  await loadModelDetail()
  showDetailDialog.value = true
}

// 加载模型详情
async function loadModelDetail() {
  if (!currentModel.value) return
  try {
    const res = await getModelApi(currentModel.value.id)
    currentModel.value = res.data
    versions.value = res.data?.versions || []
    boundScenes.value = res.data?.scenes || []
  } catch (error) {
    console.error('加载模型详情失败:', error)
  }
}

// 处理创建时的文件选择
function handleCreateFileChange(file) {
  createWeightFile.value = file.raw
}

// 处理创建时的文件移除
function handleCreateFileRemove() {
  createWeightFile.value = null
}

// 创建模型
async function createModel() {
  if (!createForm.value.name) {
    ElMessage.warning('请填写模型名称')
    return
  }
  creating.value = true
  try {
    // 构建请求数据，包含权重文件
    const requestData = { ...createForm.value }
    if (createWeightFile.value) {
      requestData.weight_file = createWeightFile.value
    }
    
    const res = await createModelApi(requestData)
    ElMessage.success('模型创建成功')
    
    showCreateDialog.value = false
    createForm.value = { name: '', category: 'general', base_architecture: 'yolo26n', description: '', scene_id: null }
    createWeightFile.value = null
    if (createUploadRef.value) {
      createUploadRef.value.clearFiles()
    }
    loadModels()
  } catch (error) {
    ElMessage.error('创建模型失败')
  } finally {
    creating.value = false
  }
}

// 打开编辑对话框
function openEditDialog(model) {
  currentModel.value = model
  editForm.value = {
    name: model.name,
    description: model.description || '',
    category: model.category
  }
  showEditDialog.value = true
}

// 更新模型
async function updateModel() {
  updating.value = true
  try {
    await updateModelApi(currentModel.value.id, editForm.value)
    ElMessage.success('模型更新成功')
    showEditDialog.value = false
    loadModels()
    if (showDetailDialog.value) {
      loadModelDetail()
    }
  } catch (error) {
    ElMessage.error('更新模型失败')
  } finally {
    updating.value = false
  }
}

// 删除模型
async function archiveModel(model) {
  try {
    await ElMessageBox.confirm(`确定删除模型 "${model.name}" 吗？删除后不可恢复。`, '警告', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'error'
    })
    await deleteModelApi(model.id)
    ElMessage.success('模型已删除')
    loadModels()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

// 切换模型启用/禁用
async function toggleModel(model) {
  try {
    await toggleModelApi(model.id)
    const action = model.is_enabled === false ? '启用' : '禁用'
    ElMessage.success(`模型已${action}`)
    loadModels()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 打开导出对话框
function openExportDialog(model) {
  currentModel.value = model
  // 加载该模型的版本列表
  versions.value = model.default_version ? [{ id: model.default_version.id, version: model.default_version.version, is_default: true }] : []
  exportVersionId.value = model.default_version?.id || null
  showExportDialog.value = true
  // 异步加载完整版本列表
  getModelApi(model.id).then(res => {
    versions.value = res.data?.versions || []
    if (!exportVersionId.value && versions.value.length > 0) {
      const defaultV = versions.value.find(v => v.is_default)
      exportVersionId.value = defaultV?.id || versions.value[0].id
    }
  }).catch(() => {})
}

// 执行导出
async function doExportVersion() {
  if (!exportVersionId.value) {
    ElMessage.warning('请选择版本')
    return
  }
  exporting.value = true
  try {
    const res = await exportModelApi(currentModel.value.id, exportVersionId.value)
    const blob = new Blob([res], { type: 'application/zip' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentModel.value.name}_v${exportVersionId.value}.zip`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
    showExportDialog.value = false
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 设为默认版本
async function setDefaultVersion(versionId) {
  try {
    await setDefaultVersionApi(currentModel.value.id, versionId)
    ElMessage.success('已设为默认版本')
    loadModelDetail()
  } catch (error) {
    ElMessage.error('设置默认版本失败')
  }
}

// 归档版本
async function archiveVersion(versionId) {
  try {
    await ElMessageBox.confirm('确定归档此版本吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteVersionApi(currentModel.value.id, versionId)
    ElMessage.success('版本已归档')
    loadModelDetail()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('归档版本失败')
  }
}

// 导出模型版本（从详情对话框内调用）
async function exportVersion(versionId) {
  try {
    const res = await exportModelApi(currentModel.value.id, versionId)
    const blob = new Blob([res], { type: 'application/zip' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentModel.value.name}_v${versionId}.zip`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

// 处理导入文件
function handleImportFileChange(file) {
  importForm.value.file = file.raw
}

// 导入模型
async function importModel() {
  if (!importForm.value.file) {
    ElMessage.warning('请选择 ZIP 文件')
    return
  }
  importing.value = true
  try {
    await importModelApi(currentModel.value.id, { zip_file: importForm.value.file, description: importForm.value.description })
    ElMessage.success('导入成功')
    showImportDialog.value = false
    importForm.value = { file: null, description: '' }
    loadModelDetail()
  } catch (error) {
    // 错误信息已由 request 拦截器统一处理
  } finally {
    importing.value = false
  }
}

// 加载所有场景
async function loadAllScenes() {
  try {
    const res = await getScenesApi()
    allScenes.value = res.data || []
  } catch (error) {
    console.error('加载场景列表失败:', error)
  }
}

// 绑定场景
async function bindScene() {
  if (!bindSceneId.value) {
    ElMessage.warning('请选择场景')
    return
  }
  binding.value = true
  try {
    await bindModelToSceneApi(bindSceneId.value, { model_id: currentModel.value.id, is_default: bindIsDefault.value })
    ElMessage.success('绑定成功')
    showBindDialog.value = false
    bindSceneId.value = null
    bindIsDefault.value = false
    loadModelDetail()
  } catch (error) {
    ElMessage.error('绑定失败')
  } finally {
    binding.value = false
  }
}

// 解绑场景
async function unbindScene(sceneId) {
  try {
    await ElMessageBox.confirm('确定解绑此场景吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await unbindModelFromSceneApi(sceneId, currentModel.value.id)
    ElMessage.success('已解绑')
    loadModelDetail()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('解绑失败')
  }
}

// 格式化时间
function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(() => {
  loadModels()
  loadAllScenes()
})
</script>

<style lang="scss" scoped>
.model-page {
  padding: $spacing-lg;
  height: calc(100vh - #{$header-height} - 40px);
  background: $bg-color;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $spacing-md;

  h3 {
    margin: 0;
    font-size: 18px;
    color: $text-primary;
  }

  .header-actions {
    display: flex;
    gap: $spacing-sm;
  }
}

.filter-bar {
  display: flex;
  gap: $spacing-sm;
  margin-bottom: $spacing-md;

  .el-select {
    width: 160px;
  }
}

.model-table-wrapper {
  flex: 1;
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-md;
  overflow: auto;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
}

.detail-section {
  margin-top: $spacing-lg;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-md;

    h4 {
      margin: 0;
      font-size: 15px;
      color: $text-primary;
    }
  }

  .empty-scenes {
    text-align: center;
    padding: $spacing-md;
    color: $text-secondary;
  }
}

.form-tip {
  font-size: 12px;
  color: $text-secondary;
  margin-top: 4px;
}
</style>
