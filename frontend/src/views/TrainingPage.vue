<template>
  <div class="training-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h3>训练任务</h3>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>新建任务
        </el-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="statusFilter" size="default" @change="loadTasks">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="pending">等待中</el-radio-button>
        <el-radio-button value="running">运行中</el-radio-button>
        <el-radio-button value="paused">已暂停</el-radio-button>
        <el-radio-button value="completed">已完成</el-radio-button>
        <el-radio-button value="failed">失败</el-radio-button>
        <el-radio-button value="cancelled">已取消</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 任务列表 -->
    <div class="task-table-wrapper">
      <el-table
        :data="tasks"
        v-loading="loading"
        stripe
        style="width: 100%"
        empty-text="暂无训练任务"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="base_architecture" label="基础架构" width="120" />
        <el-table-column prop="epochs" label="轮数" width="70" />
        <el-table-column prop="batch_size" label="批次" width="70" />
        <el-table-column prop="device" label="设备" width="70" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="140">
          <template #default="{ row }">
            <el-progress
              v-if="row.status === 'running'"
              :percentage="row.progress || 0"
              :stroke-width="6"
              :width="100"
            />
            <span v-else-if="row.status === 'completed'">100%</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="260" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button
                v-if="row.status === 'pending'"
                type="success"
                size="small"
                link
                @click="startTask(row)"
              >
                <el-icon><VideoPlay /></el-icon>启动
              </el-button>
              <el-button
                v-if="row.status === 'running'"
                type="warning"
                size="small"
                link
                @click="pauseTask(row)"
              >
                <el-icon><VideoPause /></el-icon>暂停
              </el-button>
              <el-button
                v-if="row.status === 'paused'"
                type="success"
                size="small"
                link
                @click="resumeTask(row)"
              >
                <el-icon><VideoPlay /></el-icon>恢复
              </el-button>
              <el-button
                v-if="['pending', 'running', 'paused'].includes(row.status)"
                type="warning"
                size="small"
                link
                @click="cancelTask(row)"
              >
                取消
              </el-button>
              <el-button
                v-if="row.status !== 'running'"
                type="danger"
                size="small"
                link
                @click="deleteTask(row)"
              >
                删除
              </el-button>
              <el-button
                type="primary"
                size="small"
                link
                @click="showDetail(row)"
              >
                详情
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 任务详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      title="任务详情"
      width="800px"
      destroy-on-close
      @closed="onDetailClosed"
    >
      <div v-if="detailTask">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ detailTask.id }}</el-descriptions-item>
          <el-descriptions-item label="基础架构">{{ detailTask.base_architecture }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(detailTask.status)">
              {{ getStatusText(detailTask.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="训练轮数">{{ detailTask.epochs }}</el-descriptions-item>
          <el-descriptions-item label="批次大小">{{ detailTask.batch_size }}</el-descriptions-item>
          <el-descriptions-item label="学习率">{{ detailTask.lr0 }}</el-descriptions-item>
          <el-descriptions-item label="设备">{{ detailTask.device }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">
            {{ formatTime(detailTask.created_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="metrics && metrics.length > 0" class="detail-metrics">
          <h4>训练指标</h4>
          <div class="charts-container">
            <div class="chart-item">
              <h5>损失函数 (Loss)</h5>
              <div ref="lossChartRef" class="chart"></div>
            </div>
            <div class="chart-item">
              <h5>mAP 指标</h5>
              <div ref="mapChartRef" class="chart"></div>
            </div>
          </div>
        </div>

        <div class="detail-logs">
          <h4>训练日志</h4>
          <div class="log-content">
            <pre>{{ detailTask.logs || '暂无日志' }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建训练任务" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="基础模型">
          <el-select v-model="createForm.model_name">
            <el-option label="YOLO26n (轻量)" value="yolo26n" />
            <el-option label="YOLO26s (小型)" value="yolo26s" />
            <el-option label="YOLO26m (中型)" value="yolo26m" />
            <el-option label="YOLO26l (大型)" value="yolo26l" />
            <el-option label="YOLO26x (超大)" value="yolo26x" />
          </el-select>
        </el-form-item>
        <el-form-item label="训练轮数">
          <el-input-number v-model="createForm.epochs" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="批次大小">
          <el-input-number v-model="createForm.batch_size" :min="1" :max="128" />
        </el-form-item>
        <el-form-item label="学习率">
          <el-input-number v-model="createForm.lr0" :min="0.0001" :max="0.1" :step="0.001" :precision="4" />
        </el-form-item>
        <el-form-item label="训练设备">
          <el-select v-model="createForm.device" placeholder="选择训练设备">
            <el-option
              v-for="d in devices"
              :key="d.value"
              :label="d.label"
              :value="d.value"
            >
              <span>{{ d.label }}</span>
              <span style="color: #999; font-size: 12px; margin-left: 8px">{{ d.description }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="数据集" required>
          <el-select
            v-model="createForm.dataset_id"
            placeholder="选择已注册的数据集"
            filterable
            @change="onDatasetSelected"
          >
            <el-option
              v-for="ds in datasets"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            >
              <span>{{ ds.name }}</span>
              <span style="color: #999; font-size: 12px; margin-left: 8px">{{ ds.num_images }}张 / {{ ds.num_classes }}类</span>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="creating">创建</el-button>
      </template>
    </el-dialog>


  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Plus, VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  getTrainingTasksApi,
  createTrainingTaskApi,
  startTrainingApi,
  pauseTrainingApi,
  cancelTrainingApi,
  deleteTrainingTaskApi,
  getTrainingMetricsApi,
  getTrainingDevicesApi
} from '@/api/training'
import { getDatasetsApi } from '@/api/dataset'

const tasks = ref([])
const statusFilter = ref('')
const loading = ref(false)
const pollingTimer = ref(null)

const showDetailDialog = ref(false)
const detailTask = ref(null)
const metrics = ref([])
const lossChartRef = ref(null)
const mapChartRef = ref(null)
let lossChart = null
let mapChart = null

const showCreateDialog = ref(false)
const creating = ref(false)
const devices = ref([])
const datasets = ref([])
const createForm = ref({
  model_name: 'yolo26n',
  epochs: 100,
  batch_size: 16,
  lr0: 0.01,
  device: 'cpu',
  dataset_id: null,
  dataset_path: '',
  data_yaml: ''
})



async function loadTasks() {
  loading.value = true
  try {
    const params = { page: 1, page_size: 100 }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res = await getTrainingTasksApi(params)
    tasks.value = res.data?.items || []
  } catch (error) {
    console.error('加载任务失败:', error)
  } finally {
    loading.value = false
  }
}

async function loadDevices() {
  try {
    const res = await getTrainingDevicesApi()
    devices.value = res.data || []
    // 默认选择第一个 GPU，没有则选 CPU
    if (!createForm.value.device && devices.value.length > 0) {
      const gpu = devices.value.find(d => d.value !== 'cpu')
      createForm.value.device = gpu ? gpu.value : devices.value[0].value
    }
  } catch (error) {
    console.error('加载设备列表失败:', error)
    devices.value = [{ value: 'cpu', label: 'CPU', description: '使用处理器训练' }]
  }
}

async function loadDatasets() {
  try {
    const res = await getDatasetsApi({ page: 1, page_size: 100, status: 'active' })
    datasets.value = res.data?.items || []
  } catch (error) {
    console.error('加载数据集列表失败:', error)
  }
}

function onDatasetSelected(datasetId) {
  const ds = datasets.value.find(d => d.id === datasetId)
  if (ds) {
    createForm.value.dataset_path = ds.path
    createForm.value.data_yaml = ds.yaml_path
  }
}

async function showDetail(task) {
  detailTask.value = task
  showDetailDialog.value = true
  await loadMetrics()
}

function onDetailClosed() {
  lossChart?.dispose()
  lossChart = null
  mapChart?.dispose()
  mapChart = null
  metrics.value = []
}

async function startTask(task) {
  try {
    await startTrainingApi(task.id)
    ElMessage.success('任务已启动')
    loadTasks()
  } catch (error) {
    ElMessage.error('启动任务失败')
  }
}

async function pauseTask(task) {
  try {
    await pauseTrainingApi(task.id)
    ElMessage.success('任务已暂停')
    loadTasks()
  } catch (error) {
    ElMessage.error('暂停任务失败')
  }
}

async function resumeTask(task) {
  try {
    await startTrainingApi(task.id)
    ElMessage.success('任务已恢复')
    loadTasks()
  } catch (error) {
    ElMessage.error('恢复任务失败')
  }
}

async function cancelTask(task) {
  try {
    await ElMessageBox.confirm('确定取消此训练任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await cancelTrainingApi(task.id)
    ElMessage.success('任务已取消')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消任务失败')
    }
  }
}

async function deleteTask(task) {
  try {
    await ElMessageBox.confirm('确定删除此训练任务吗？此操作不可恢复。', '警告', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'error'
    })
    await deleteTrainingTaskApi(task.id)
    ElMessage.success('任务已删除')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除任务失败')
    }
  }
}

async function createTask() {
  if (!createForm.value.dataset_id) {
    ElMessage.warning('请填写必填项')
    return
  }
  creating.value = true
  try {
    await createTrainingTaskApi(createForm.value)
    ElMessage.success('任务创建成功')
    showCreateDialog.value = false
    loadTasks()
  } catch (error) {
    ElMessage.error('创建任务失败')
  } finally {
    creating.value = false
  }
}



async function loadMetrics() {
  if (!detailTask.value) return
  try {
    const res = await getTrainingMetricsApi(detailTask.value.id)
    metrics.value = res.data || []
    await nextTick()
    renderCharts()
  } catch (error) {
    console.error('加载指标失败:', error)
  }
}

function renderCharts() {
  if (!metrics.value.length) return
  if (lossChartRef.value) {
    if (lossChart) lossChart.dispose()
    lossChart = echarts.init(lossChartRef.value)
    const epochs = metrics.value.map(m => m.epoch)
    const trainLoss = metrics.value.map(m => m.train_loss)
    const valLoss = metrics.value.map(m => m.val_loss)
    lossChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['训练损失', '验证损失'] },
      xAxis: { type: 'category', data: epochs, name: 'Epoch' },
      yAxis: { type: 'value', name: 'Loss' },
      series: [
        { name: '训练损失', type: 'line', data: trainLoss, smooth: true },
        { name: '验证损失', type: 'line', data: valLoss, smooth: true }
      ]
    })
  }
  if (mapChartRef.value) {
    if (mapChart) mapChart.dispose()
    mapChart = echarts.init(mapChartRef.value)
    const epochs = metrics.value.map(m => m.epoch)
    const map50 = metrics.value.map(m => m.mAP50)
    const map5095 = metrics.value.map(m => m.mAP50_95)
    mapChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['mAP@0.5', 'mAP@0.5:0.95'] },
      xAxis: { type: 'category', data: epochs, name: 'Epoch' },
      yAxis: { type: 'value', name: 'mAP', max: 1 },
      series: [
        { name: 'mAP@0.5', type: 'line', data: map50, smooth: true },
        { name: 'mAP@0.5:0.95', type: 'line', data: map5095, smooth: true }
      ]
    })
  }
}

function getStatusType(status) {
  const map = { pending: 'info', running: 'warning', paused: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' }
  return map[status] || 'info'
}

function getStatusText(status) {
  const map = { pending: '等待中', running: '运行中', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' }
  return map[status] || status
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleString('zh-CN')
}

function startPolling() {
  pollingTimer.value = setInterval(() => {
    const hasRunning = tasks.value.some(t => t.status === 'running')
    if (hasRunning) {
      loadTasks()
      if (showDetailDialog.value && detailTask.value?.status === 'running') {
        loadMetrics()
      }
    }
  }, 5000)
}

function handleResize() {
  lossChart?.resize()
  mapChart?.resize()
}

onMounted(() => {
  loadTasks()
  loadDevices()
  loadDatasets()
  startPolling()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (pollingTimer.value) clearInterval(pollingTimer.value)
  window.removeEventListener('resize', handleResize)
  lossChart?.dispose()
  mapChart?.dispose()
})
</script>

<style lang="scss" scoped>
.training-page {
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

.task-table-wrapper {
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
  flex-wrap: wrap;
}

.text-muted {
  color: $text-secondary;
  font-size: 13px;
}

.detail-metrics {
  margin-top: $spacing-lg;

  h4 {
    margin: 0 0 $spacing-md;
    font-size: 15px;
    color: $text-primary;
  }

  .charts-container {
    display: flex;
    gap: $spacing-lg;

    .chart-item {
      flex: 1;

      h5 {
        margin: 0 0 $spacing-sm;
        font-size: 13px;
        color: $text-regular;
        text-align: center;
      }

      .chart {
        height: 250px;
      }
    }
  }
}

.detail-logs {
  margin-top: $spacing-lg;

  h4 {
    margin: 0 0 $spacing-md;
    font-size: 15px;
    color: $text-primary;
  }

  .log-content {
    background: #1e1e1e;
    border-radius: $border-radius-md;
    padding: $spacing-md;
    max-height: 250px;
    overflow-y: auto;

    pre {
      margin: 0;
      color: #d4d4d4;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-all;
    }
  }
}

.form-tip {
  margin-left: $spacing-sm;
  font-size: 12px;
  color: $text-secondary;
}
</style>
