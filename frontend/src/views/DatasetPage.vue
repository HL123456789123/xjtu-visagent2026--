<template>
  <div class="dataset-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h3>数据集管理</h3>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>注册数据集
      </el-button>
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
              <el-button type="warning" size="small" link @click="validateDataset(row)">
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
    <el-dialog v-model="showCreateDialog" title="注册数据集" width="520px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="如：遥感目标检测数据集" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="数据集说明（可选）" />
        </el-form-item>
        <el-form-item label="数据集路径" required>
          <el-input v-model="createForm.path" placeholder="数据集根目录路径，如 /data/my_dataset" />
        </el-form-item>
        <el-form-item label="配置文件" required>
          <el-input v-model="createForm.yaml_path" placeholder="data.yaml 文件路径" />
        </el-form-item>
        <el-form-item label="标注格式">
          <el-select v-model="createForm.format">
            <el-option label="YOLO" value="yolo" />
            <el-option label="VOC" value="voc" />
            <el-option label="COCO" value="coco" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createDataset" :loading="creating">注册</el-button>
      </template>
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
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getDatasetsApi,
  getDatasetApi,
  createDatasetApi,
  deleteDatasetApi,
  validateDatasetApi
} from '@/api/dataset'

const datasets = ref([])
const statusFilter = ref('')
const loading = ref(false)

const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  description: '',
  path: '',
  yaml_path: '',
  format: 'yolo'
})

const showDetailDialog = ref(false)
const detailData = ref(null)

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
    createForm.value = { name: '', description: '', path: '', yaml_path: '', format: 'yolo' }
    loadDatasets()
  } catch (error) {
    const msg = error.response?.data?.detail || '注册失败'
    ElMessage.error(msg)
  } finally {
    creating.value = false
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

onMounted(() => {
  loadDatasets()
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
