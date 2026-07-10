<template>
  <div class="model-page">
    <!-- 左侧模型列表 -->
    <div class="model-list-panel">
      <div class="panel-header">
        <h3>模型管理</h3>
        <el-button type="primary" size="small" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>新建模型
        </el-button>
      </div>

      <!-- 筛选 -->
      <div class="filter-section">
        <el-select v-model="filterCategory" placeholder="分类筛选" clearable size="small" @change="loadModels">
          <el-option label="通用" value="general" />
          <el-option label="工业" value="industrial" />
          <el-option label="安防" value="security" />
          <el-option label="交通" value="traffic" />
          <el-option label="农业" value="agriculture" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态筛选" clearable size="small" @change="loadModels">
          <el-option label="活跃" value="active" />
          <el-option label="已归档" value="archived" />
        </el-select>
      </div>

      <!-- 模型列表 -->
      <div class="model-items">
        <div
          v-for="model in models"
          :key="model.id"
          :class="['model-item', { active: currentModel?.id === model.id }]"
          @click="selectModel(model)"
        >
          <div class="model-info">
            <div class="model-name">{{ model.name }}</div>
            <div class="model-meta">
              <el-tag size="small" :type="model.status === 'active' ? 'success' : 'info'">
                {{ model.status === 'active' ? '活跃' : '已归档' }}
              </el-tag>
              <span class="model-category">{{ model.category }}</span>
              <span class="version-count">{{ model.version_count || 0 }} 个版本</span>
            </div>
          </div>
        </div>
        <div v-if="models.length === 0" class="empty-models">
          <el-icon :size="48"><Goods /></el-icon>
          <p>暂无模型</p>
        </div>
      </div>
    </div>

    <!-- 右侧详情面板 -->
    <div class="detail-panel">
      <template v-if="currentModel">
        <!-- 基本信息 -->
        <div class="detail-card">
          <div class="card-header">
            <h3>{{ currentModel.name }}</h3>
            <div class="card-actions">
              <el-button size="small" @click="showEditDialog = true">
                <el-icon><Edit /></el-icon>编辑
              </el-button>
              <el-button
                v-if="currentModel.status === 'active'"
                type="danger"
                size="small"
                @click="archiveModel"
              >
                <el-icon><Delete /></el-icon>归档
              </el-button>
            </div>
          </div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="模型ID">{{ currentModel.id }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ currentModel.category }}</el-descriptions-item>
            <el-descriptions-item label="基础架构">{{ currentModel.base_architecture }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="currentModel.status === 'active' ? 'success' : 'info'">
                {{ currentModel.status === 'active' ? '活跃' : '已归档' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ currentModel.description || '无' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间" :span="2">{{ formatTime(currentModel.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 版本列表 -->
        <div class="detail-card">
          <div class="card-header">
            <h3>模型版本</h3>
            <div class="card-actions">
              <el-button size="small" @click="showImportDialog = true">
                <el-icon><Upload /></el-icon>导入
              </el-button>
            </div>
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
            <el-table-column label="默认" width="80">
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
            <el-table-column label="操作" width="160">
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
        <div class="detail-card">
          <div class="card-header">
            <h3>关联场景</h3>
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
            <p>暂未关联任何场景</p>
          </div>
        </div>
      </template>

      <!-- 空状态 -->
      <div v-else class="empty-detail">
        <el-icon :size="64"><Goods /></el-icon>
        <p>选择模型查看详情</p>
      </div>
    </div>

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
import { ref, onMounted, watch } from 'vue'
import { Plus, Goods, Edit, Delete, Upload, Link } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getModelsApi,
  createModelApi,
  getModelApi,
  updateModelApi,
  deleteModelApi,
  getModelVersionsApi,
  setDefaultVersionApi,
  deleteVersionApi,
  exportModelApi,
  importModelApi,
  getSceneModelsApi,
  bindModelToSceneApi,
  unbindModelFromSceneApi
} from '@/api/model'
import { getScenesApi } from '@/api/detection'

// 模型列表
const models = ref([])
const currentModel = ref(null)
const filterCategory = ref('')
const filterStatus = ref('')

// 版本和场景
const versions = ref([])
const boundScenes = ref([])
const allScenes = ref([])

// 创建对话框
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  category: 'general',
  base_architecture: 'yolo26n',
  description: ''
})

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
  try {
    const params = { page: 1, page_size: 100 }
    if (filterCategory.value) params.category = filterCategory.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getModelsApi(params)
    models.value = res.data?.items || []
  } catch (error) {
    console.error('加载模型列表失败:', error)
  }
}

// 选择模型
async function selectModel(model) {
  currentModel.value = model
  await loadModelDetail()
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

// 创建模型
async function createModel() {
  if (!createForm.value.name) {
    ElMessage.warning('请填写模型名称')
    return
  }
  creating.value = true
  try {
    await createModelApi(createForm.value)
    ElMessage.success('模型创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', category: 'general', base_architecture: 'yolo26n', description: '' }
    loadModels()
  } catch (error) {
    ElMessage.error('创建模型失败')
  } finally {
    creating.value = false
  }
}

// 打开编辑对话框时填充数据
watch(showEditDialog, (val) => {
  if (val && currentModel.value) {
    editForm.value = {
      name: currentModel.value.name,
      description: currentModel.value.description || '',
      category: currentModel.value.category
    }
  }
})

// 更新模型
async function updateModel() {
  updating.value = true
  try {
    await updateModelApi(currentModel.value.id, editForm.value)
    ElMessage.success('模型更新成功')
    showEditDialog.value = false
    loadModels()
    loadModelDetail()
  } catch (error) {
    ElMessage.error('更新模型失败')
  } finally {
    updating.value = false
  }
}

// 归档模型
async function archiveModel() {
  try {
    await ElMessageBox.confirm(`确定归档模型 "${currentModel.value.name}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteModelApi(currentModel.value.id)
    ElMessage.success('模型已归档')
    currentModel.value = null
    loadModels()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('归档失败')
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

// 导出模型版本
async function exportVersion(versionId) {
  try {
    const res = await exportModelApi(currentModel.value.id, versionId)
    // 下载文件
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
    ElMessage.error('导入失败')
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
  display: flex;
  height: calc(100vh - #{$header-height} - 40px);
  background: $bg-color;
}

.model-list-panel {
  width: 320px;
  background: #fff;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;

  .panel-header {
    padding: $spacing-md;
    border-bottom: 1px solid #ebeef5;
    display: flex;
    justify-content: space-between;
    align-items: center;

    h3 {
      margin: 0;
      font-size: 16px;
      color: $text-primary;
    }
  }

  .filter-section {
    padding: $spacing-sm $spacing-md;
    border-bottom: 1px solid #ebeef5;
    display: flex;
    gap: $spacing-sm;

    .el-select {
      flex: 1;
    }
  }

  .model-items {
    flex: 1;
    overflow-y: auto;
    padding: $spacing-sm;
  }

  .model-item {
    padding: $spacing-md;
    border-radius: $border-radius-md;
    cursor: pointer;
    transition: background 0.2s;
    margin-bottom: $spacing-sm;

    &:hover { background: #f5f7fa; }
    &.active { background: #ecf5ff; }

    .model-name {
      font-size: 14px;
      color: $text-primary;
      margin-bottom: $spacing-xs;
      font-weight: 500;
    }

    .model-meta {
      display: flex;
      align-items: center;
      gap: $spacing-sm;

      .model-category, .version-count {
        font-size: 12px;
        color: $text-secondary;
      }
    }
  }

  .empty-models {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: $text-secondary;

    p { margin: $spacing-md 0 0; }
  }
}

.detail-panel {
  flex: 1;
  padding: $spacing-lg;
  overflow-y: auto;
}

.detail-card {
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-lg;
  margin-bottom: $spacing-lg;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-lg;

    h3 {
      margin: 0;
      font-size: 16px;
      color: $text-primary;
    }

    .card-actions {
      display: flex;
      gap: $spacing-sm;
    }
  }

  .empty-scenes {
    text-align: center;
    padding: $spacing-lg;
    color: $text-secondary;
  }
}

.empty-detail {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: #fff;
  border-radius: $border-radius-lg;
  color: $text-secondary;

  p {
    margin: $spacing-md 0 0;
    font-size: 16px;
  }
}
</style>
