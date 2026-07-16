<template>
  <div class="dataset-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h3>数据集管理</h3>
      <div class="header-actions">
        <el-button @click="handleDiscover" :loading="discovering">
          <el-icon><Search /></el-icon>自动发现
        </el-button>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>注册数据集
        </el-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="statusFilter" size="default" @change="loadDatasets">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="active">有效</el-radio-button>
        <el-radio-button value="invalid">异常</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 数据集列表 -->
    <div class="table-wrapper">
      <el-table
        :data="datasets"
        v-loading="loading"
        stripe
        style="width: 100%"
        empty-text="暂无数据集"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="160">
          <template #default="{ row }">
            <div class="dataset-name">
              <span>{{ row.name }}</span>
              <span v-if="row.description" class="dataset-desc">{{ row.description }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="num_classes" label="类别数" width="80" align="center" />
        <el-table-column prop="num_images" label="图片数" width="90" align="center" />
        <el-table-column prop="format" label="格式" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.format }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="适用场景" width="140">
          <template #default="{ row }">
            <el-tag v-if="getSceneName(row.scene_id)" size="small" type="success">
              {{ getSceneName(row.scene_id) }}
            </el-tag>
            <span v-else class="text-muted">未指定</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">
              {{ row.status === 'active' ? '有效' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button type="primary" size="small" link @click="showDetail(row)">
                详情
              </el-button>
              <el-tag v-if="row.status === 'active'" type="success" size="small">已校验</el-tag>
              <el-button v-else type="warning" size="small" link @click="validateDataset(row)">
                校验
              </el-button>
              <el-button type="danger" size="small" link @click="deleteDataset(row)">
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 注册数据集对话框 -->
    <el-dialog v-model="showCreateDialog" title="注册数据集" width="680px" @close="resetBrowser">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="如：遥感目标检测数据集" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="数据集说明（可选）" />
        </el-form-item>

        <!-- 目录浏览器 -->
        <el-form-item label="数据集路径" required>
          <div class="dir-browser">
            <!-- 面包屑导航 -->
            <div class="breadcrumb-bar">
              <el-button
                v-if="browserState.currentPath"
                size="small"
                text
                @click="navigateUp"
              >
                <el-icon><ArrowUp /></el-icon>上级
              </el-button>
              <span class="current-path">{{ browserState.currentPath || '选择根目录' }}</span>
            </div>
            <!-- 目录列表 -->
            <div class="dir-list" v-loading="browserState.loading">
              <div
                v-for="dir in browserState.dirs"
                :key="dir.path"
                class="dir-item"
                :class="{ selected: createForm.path === dir.path }"
                @click="selectDir(dir)"
                @dblclick="navigateInto(dir)"
              >
                <el-icon class="dir-icon"><Folder /></el-icon>
                <span class="dir-name">{{ dir.name }}</span>
                <el-button
                  size="small"
                  text
                  class="enter-btn"
                  @click.stop="navigateInto(dir)"
                >
                  进入
                </el-button>
              </div>
              <div v-if="!browserState.dirs.length && !browserState.loading" class="empty-hint">
                无子目录
              </div>
            </div>
            <!-- 已选路径 -->
            <div class="selected-path" v-if="createForm.path">
              <el-tag closable @close="createForm.path = ''">
                {{ createForm.path }}
              </el-tag>
            </div>
          </div>
        </el-form-item>

        <!-- YAML 文件选择 -->
        <el-form-item label="配置文件" required>
          <div class="yaml-selector">
            <el-select
              v-model="createForm.yaml_path"
              placeholder="选择配置文件"
              :disabled="!browserState.yamlFiles.length"
              style="width: 100%"
            >
              <el-option
                v-for="f in browserState.yamlFiles"
                :key="f.path"
                :label="f.name"
                :value="f.path"
              />
            </el-select>
            <div class="yaml-hint" v-if="!createForm.path">
              请先选择数据集目录
            </div>
            <div class="yaml-hint" v-else-if="!browserState.yamlFiles.length">
              当前目录下未找到 YAML 配置文件
            </div>
          </div>
        </el-form-item>

        <el-form-item label="标注格式">
          <el-select v-model="createForm.format">
            <el-option label="YOLO" value="yolo" />
            <el-option label="VOC" value="voc" />
            <el-option label="COCO" value="coco" />
          </el-select>
        </el-form-item>

        <el-form-item label="检测场景">
          <el-select v-model="createForm.scene_id" placeholder="选择检测场景（可选）" clearable>
            <el-option
              v-for="scene in scenes"
              :key="scene.id"
              :label="scene.display_name"
              :value="scene.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createDataset" :loading="creating">注册</el-button>
      </template>
    </el-dialog>

    <!-- 自动发现对话框 -->
    <el-dialog v-model="showDiscoverDialog" title="发现的数据集" width="720px">
      <div class="discover-content">
        <div v-if="discoveredList.length" class="discover-list">
          <div
            v-for="item in discoveredList"
            :key="item.path"
            class="discover-item"
          >
            <div class="discover-info">
              <div class="discover-name">{{ item.name }}</div>
              <div class="discover-path">{{ item.path }}</div>
              <div class="discover-meta">
                <span v-if="item.num_classes">{{ item.num_classes }} 个类别</span>
                <span v-if="item.num_images">{{ item.num_images }} 张图片</span>
                <span v-if="item.error" class="error-text">{{ item.error }}</span>
              </div>
              <div class="class-tags" v-if="item.class_names && item.class_names.length">
                <el-tag
                  v-for="(name, idx) in item.class_names.slice(0, 5)"
                  :key="idx"
                  size="small"
                  class="class-tag"
                >
                  {{ name }}
                </el-tag>
                <el-tag v-if="item.class_names.length > 5" size="small" type="info">
                  +{{ item.class_names.length - 5 }}
                </el-tag>
              </div>
            </div>
            <el-button
              type="primary"
              size="small"
              @click="quickRegister(item)"
              :disabled="!!item.error"
            >
              注册
            </el-button>
          </div>
        </div>
        <el-empty v-else description="未发现未注册的数据集" />
      </div>
    </el-dialog>

    <!-- 数据集详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="数据集详情" width="600px">
      <template v-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ detailData.id }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ detailData.name }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ detailData.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="数据集路径" :span="2">{{ detailData.path }}</el-descriptions-item>
          <el-descriptions-item label="配置文件" :span="2">{{ detailData.yaml_path }}</el-descriptions-item>
          <el-descriptions-item label="图片数量">{{ detailData.num_images }}</el-descriptions-item>
          <el-descriptions-item label="类别数">{{ detailData.num_classes }}</el-descriptions-item>
          <el-descriptions-item label="标注格式">{{ detailData.format }}</el-descriptions-item>
          <el-descriptions-item label="适用场景">
            <el-tag v-if="getSceneName(detailData.scene_id)" type="success" size="small">
              {{ getSceneName(detailData.scene_id) }}
            </el-tag>
            <span v-else class="text-muted">未指定</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detailData.status === 'active' ? 'success' : 'danger'">
              {{ detailData.status === 'active' ? '有效' : '异常' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="关联训练任务">{{ detailData.task_count || 0 }} 个</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detailData.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="类别列表" :span="2">
            <div class="class-tags" v-if="detailData.class_names && detailData.class_names.length">
              <el-tag
                v-for="(name, idx) in detailData.class_names"
                :key="idx"
                size="small"
                class="class-tag"
              >
                {{ idx }}: {{ name }}
              </el-tag>
            </div>
            <span v-else class="text-muted">无</span>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { Plus, Search, ArrowUp, Folder } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getDatasetsApi,
  getDatasetApi,
  createDatasetApi,
  deleteDatasetApi,
  validateDatasetApi,
  browseDirectoryApi,
  discoverDatasetsApi,
} from '@/api/dataset'
import { getScenesApi } from '@/api/detection'

const datasets = ref([])
const statusFilter = ref('')
const loading = ref(false)

const showCreateDialog = ref(false)
const creating = ref(false)
const scenes = ref([])
const createForm = ref({
  name: '',
  description: '',
  path: '',
  yaml_path: '',
  format: 'yolo',
  scene_id: null
})

const showDetailDialog = ref(false)
const detailData = ref(null)

// 目录浏览器状态
const browserState = reactive({
  currentPath: null,
  dirs: [],
  yamlFiles: [],
  loading: false,
})

// 自动发现
const showDiscoverDialog = ref(false)
const discovering = ref(false)
const discoveredList = ref([])

async function loadDatasets() {
  loading.value = true
  try {
    const params = { page: 1, page_size: 100 }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res = await getDatasetsApi(params)
    datasets.value = res.data?.items || []
  } catch (error) {
    console.error('加载数据集失败:', error)
  } finally {
    loading.value = false
  }
}

// ========== 目录浏览器 ==========

async function browseDir(path) {
  browserState.loading = true
  try {
    const res = await browseDirectoryApi(path)
    const data = res.data
    browserState.currentPath = data.current_path
    browserState.dirs = data.dirs || []
    browserState.yamlFiles = data.yaml_files || []
  } catch (error) {
    const msg = error.response?.data?.detail || '浏览目录失败'
    ElMessage.error(msg)
  } finally {
    browserState.loading = false
  }
}

function selectDir(dir) {
  createForm.value.path = dir.path
  // 自动填充名称（如果为空）
  if (!createForm.value.name) {
    createForm.value.name = dir.name
  }
}

function navigateInto(dir) {
  browseDir(dir.path)
}

function navigateUp() {
  if (!browserState.currentPath) return
  const parentPath = browserState.currentPath.split('/').slice(0, -1).join('/') || '/'
  browseDir(parentPath)
}

function resetBrowser() {
  browserState.currentPath = null
  browserState.dirs = []
  browserState.yamlFiles = []
}

// 打开对话框时加载根目录
watch(showCreateDialog, (val) => {
  if (val) {
    browseDir() // 加载根目录
  }
})

// ========== 自动发现 ==========

async function handleDiscover() {
  discovering.value = true
  try {
    const res = await discoverDatasetsApi()
    discoveredList.value = res.data?.discovered || []
    showDiscoverDialog.value = true
    if (!discoveredList.value.length) {
      ElMessage.info('未发现未注册的数据集')
    }
  } catch (error) {
    const msg = error.response?.data?.detail || '自动发现失败'
    ElMessage.error(msg)
  } finally {
    discovering.value = false
  }
}

function quickRegister(item) {
  // 填充表单并打开注册对话框
  createForm.value = {
    name: item.name,
    description: '',
    path: item.path,
    yaml_path: item.yaml_path,
    format: 'yolo'
  }
  showDiscoverDialog.value = false
  showCreateDialog.value = true
  // 加载该目录的 yaml 文件列表
  browseDir(item.path)
}

// ========== 其他操作 ==========

async function createDataset() {
  if (!createForm.value.name || !createForm.value.path || !createForm.value.yaml_path) {
    ElMessage.warning('请填写必填项')
    return
  }
  creating.value = true
  try {
    await createDatasetApi(createForm.value)
    ElMessage.success('数据集注册成功')
    showCreateDialog.value = false
    createForm.value = { name: '', description: '', path: '', yaml_path: '', format: 'yolo', scene_id: null }
    resetBrowser()
    loadDatasets()
  } catch (error) {
    const msg = error.response?.data?.detail || '注册失败'
    ElMessage.error(msg)
  } finally {
    creating.value = false
  }
}

async function loadScenes() {
  try {
    const res = await getScenesApi()
    scenes.value = res.data || []
  } catch (error) {
    console.error('加载场景列表失败:', error)
  }
}

async function showDetail(row) {
  try {
    const res = await getDatasetApi(row.id)
    detailData.value = res.data
    showDetailDialog.value = true
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

async function validateDataset(row) {
  try {
    const res = await validateDatasetApi(row.id)
    const data = res.data
    if (data.status === 'active') {
      ElMessage.success('校验通过，数据集完整')
    } else {
      const issues = data.issues?.join('; ') || '未知问题'
      ElMessage.warning(`校验发现问题: ${issues}`)
    }
    loadDatasets()
  } catch (error) {
    ElMessage.error('校验失败')
  }
}

async function deleteDataset(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除数据集「${row.name}」吗？仅删除注册记录，不删除实际文件。`,
      '提示',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteDatasetApi(row.id)
    ElMessage.success('数据集已删除')
    loadDatasets()
  } catch (error) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.detail || '删除失败'
      ElMessage.error(msg)
    }
  }
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleString('zh-CN')
}

function getSceneName(sceneId) {
  if (!sceneId) return ''
  const scene = scenes.value.find(s => s.id === sceneId)
  return scene?.display_name || ''
}

onMounted(() => {
  loadDatasets()
  loadScenes()
})
</script>

<style lang="scss" scoped>
.dataset-page {
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
  margin-bottom: $spacing-md;
}

.table-wrapper {
  flex: 1;
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-md;
  overflow: auto;
}

.dataset-name {
  display: flex;
  flex-direction: column;

  .dataset-desc {
    font-size: 12px;
    color: $text-secondary;
    margin-top: 2px;
  }
}

.row-actions {
  display: flex;
  align-items: center;
  gap: $spacing-xs;
}

// ========== 目录浏览器 ==========
.dir-browser {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.breadcrumb-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;

  .current-path {
    font-size: 13px;
    color: #606266;
    word-break: break-all;
  }
}

.dir-list {
  min-height: 120px;
  max-height: 200px;
  overflow-y: auto;
  padding: 4px 0;
}

.dir-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: #f5f7fa;
  }

  &.selected {
    background: #ecf5ff;
  }

  .dir-icon {
    color: #e6a23c;
    margin-right: 8px;
  }

  .dir-name {
    flex: 1;
    font-size: 14px;
  }

  .enter-btn {
    opacity: 0;
    transition: opacity 0.2s;
  }

  &:hover .enter-btn {
    opacity: 1;
  }
}

.empty-hint {
  text-align: center;
  padding: 20px;
  color: #909399;
  font-size: 13px;
}

.selected-path {
  padding: 8px 12px;
  background: #f0f9eb;
  border-top: 1px solid #e1f3d8;
}

.yaml-selector {
  width: 100%;

  .yaml-hint {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
  }
}

// ========== 自动发现 ==========
.discover-content {
  max-height: 500px;
  overflow-y: auto;
}

.discover-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.discover-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 16px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }
}

.discover-info {
  flex: 1;
  min-width: 0;
}

.discover-name {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.discover-path {
  font-size: 12px;
  color: #909399;
  word-break: break-all;
  margin-bottom: 6px;
}

.discover-meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;

  .error-text {
    color: #f56c6c;
  }
}

.class-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  .class-tag {
    margin: 2px;
  }
}

.text-muted {
  color: $text-secondary;
  font-size: 13px;
}
</style>
