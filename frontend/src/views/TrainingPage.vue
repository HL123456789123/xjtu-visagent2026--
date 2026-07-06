<template>
  <div class="training-page">
    <!-- 左侧任务列表 -->
    <div class="task-list-panel">
      <div class="panel-header">
        <h3>训练任务</h3>
        <div class="header-actions">
          <el-button type="primary" size="small" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>新建任务
          </el-button>
          <el-button type="success" size="small" @click="showUploadDialog = true">
            <el-icon><Upload /></el-icon>上传模型
          </el-button>
        </div>
      </div>
      
      <!-- 任务状态筛选 -->
      <div class="status-filter">
        <el-radio-group v-model="statusFilter" size="small" @change="loadTasks">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending">等待中</el-radio-button>
          <el-radio-button value="running">运行中</el-radio-button>
          <el-radio-button value="paused">已暂停</el-radio-button>
          <el-radio-button value="completed">已完成</el-radio-button>
          <el-radio-button value="failed">失败</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 任务列表 -->
      <div class="task-items">
        <div
          v-for="task in tasks"
          :key="task.id"
          :class="['task-item', { active: currentTask?.id === task.id, running: task.status === 'running' }]"
          @click="selectTask(task)"
        >
          <div class="task-info">
            <div class="task-name">{{ task.base_architecture }} - 模型 #{{ task.model_id }}</div>
            <div class="task-meta">
              <el-tag :type="getStatusType(task.status)" size="small">
                {{ getStatusText(task.status) }}
              </el-tag>
              <span class="task-time">{{ formatTime(task.created_at) }}</span>
            </div>
          </div>
          <el-progress
            v-if="task.status === 'running'"
            :percentage="task.progress || 0"
            :stroke-width="4"
            :show-text="false"
          />
        </div>
        <div v-if="tasks.length === 0" class="empty-tasks">
          <el-icon :size="48"><Cpu /></el-icon>
          <p>暂无训练任务</p>
        </div>
      </div>
    </div>

    <!-- 右侧详情面板 -->
    <div class="detail-panel">
      <template v-if="currentTask">
        <!-- 任务信息 -->
        <div class="task-detail-card">
          <div class="card-header">
            <h3>任务详情</h3>
            <div class="task-actions">
              <el-button
                v-if="currentTask.status === 'pending'"
                type="success"
                size="small"
                @click="startTask"
              >
                <el-icon><VideoPlay /></el-icon>启动
              </el-button>
              <el-button
                v-if="currentTask.status === 'running'"
                type="warning"
                size="small"
                @click="pauseTask"
              >
                <el-icon><VideoPause /></el-icon>暂停
              </el-button>
              <el-button
                v-if="currentTask.status === 'paused'"
                type="success"
                size="small"
                @click="resumeTask"
              >
                <el-icon><VideoPlay /></el-icon>恢复训练
              </el-button>
              <el-button
                v-if="['pending', 'running', 'paused'].includes(currentTask.status)"
                type="danger"
                size="small"
                @click="cancelTask"
              >
                <el-icon><Close /></el-icon>取消
              </el-button>
            </div>
          </div>

          <el-descriptions :column="2" border>
            <el-descriptions-item label="任务ID">{{ currentTask.id }}</el-descriptions-item>
            <el-descriptions-item label="基础架构">{{ currentTask.base_architecture }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentTask.status)">
                {{ getStatusText(currentTask.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="模型ID">{{ currentTask.model_id }}</el-descriptions-item>
            <el-descriptions-item label="训练轮数">{{ currentTask.epochs }}</el-descriptions-item>
            <el-descriptions-item label="批次大小">{{ currentTask.batch_size }}</el-descriptions-item>
            <el-descriptions-item label="学习率">{{ currentTask.lr0 }}</el-descriptions-item>
            <el-descriptions-item label="设备">{{ currentTask.device }}</el-descriptions-item>
            <el-descriptions-item label="创建时间" :span="2">
              {{ formatTime(currentTask.created_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 训练指标图表 -->
        <div v-if="metrics && metrics.length > 0" class="metrics-card">
          <div class="card-header">
            <h3>训练指标</h3>
            <el-button size="small" @click="refreshMetrics">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
          </div>
          
          <div class="charts-container">
            <div class="chart-item">
              <h4>损失函数 (Loss)</h4>
              <div ref="lossChartRef" class="chart"></div>
            </div>
            <div class="chart-item">
              <h4>mAP 指标</h4>
              <div ref="mapChartRef" class="chart"></div>
            </div>
          </div>
        </div>

        <!-- 训练日志 -->
        <div class="log-card">
          <div class="card-header">
            <h3>训练日志</h3>
          </div>
          <div class="log-content">
            <pre>{{ currentTask.logs || '暂无日志' }}</pre>
          </div>
        </div>
      </template>

      <!-- 空状态 -->
      <div v-else class="empty-detail">
        <el-icon :size="64"><Cpu /></el-icon>
        <p>选择任务查看详情</p>
      </div>
    </div>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建训练任务" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="模型" required>
          <el-select v-model="createForm.model_id" placeholder="选择模型">
            <el-option
              v-for="model in models"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="基础模型">
          <el-select v-model="createForm.model_name">
            <el-option label="YOLOv11n (轻量)" value="yolov11n" />
            <el-option label="YOLOv11s (小型)" value="yolov11s" />
            <el-option label="YOLOv11m (中型)" value="yolov11m" />
            <el-option label="YOLOv11l (大型)" value="yolov11l" />
            <el-option label="YOLOv11x (超大)" value="yolov11x" />
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
          <el-select v-model="createForm.device">
            <el-option label="CPU" value="cpu" />
            <el-option label="GPU 0" value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据集路径" required>
          <el-input v-model="createForm.dataset_path" placeholder="数据集根目录路径" />
        </el-form-item>
        <el-form-item label="配置文件" required>
          <el-input v-model="createForm.data_yaml" placeholder="data.yaml 文件路径" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 上传模型对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传训练模型" width="500px">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="模型" required>
          <el-select v-model="uploadForm.model_id" placeholder="选择模型">
            <el-option
              v-for="model in models"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型文件" required>
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".pt"
            :on-change="handleModelFileChange"
            :file-list="uploadForm.model_file ? [{ name: uploadForm.model_file.name }] : []"
          >
            <el-button type="primary" size="small">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .pt 格式的 YOLO 模型文件</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="版本号" required>
          <el-input v-model="uploadForm.version" placeholder="如 v1.0.0" />
        </el-form-item>
        <el-form-item label="模型描述">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" placeholder="模型说明（可选）" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="uploadForm.is_default" />
          <span class="form-tip">开启后检测时将使用此模型</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="uploadModel" :loading="uploading">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Plus, Cpu, VideoPlay, VideoPause, Close, Refresh, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  getTrainingTasksApi,
  createTrainingTaskApi,
  startTrainingApi,
  pauseTrainingApi,
  cancelTrainingApi,
  getTrainingMetricsApi,
  uploadModelApi
} from '@/api/training'
import { getModelsApi } from '@/api/model'

// 任务列表
const tasks = ref([])
const currentTask = ref(null)
const statusFilter = ref('')
const pollingTimer = ref(null)

// 创建任务
const showCreateDialog = ref(false)
const creating = ref(false)
const models = ref([])
const createForm = ref({
  model_id: null,
  model_name: 'yolov11n',
  epochs: 100,
  batch_size: 16,
  lr0: 0.01,
  device: 'cpu',
  dataset_path: '',
  data_yaml: ''
})

// 上传模型
const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadForm = ref({
  model_id: null,
  model_file: null,
  version: 'v1.0.0',
  description: '',
  is_default: true
})

// 训练指标
const metrics = ref([])
const lossChartRef = ref(null)
const mapChartRef = ref(null)
let lossChart = null
let mapChart = null

// 加载任务列表
async function loadTasks() {
  try {
    const params = { page: 1, page_size: 100 }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res = await getTrainingTasksApi(params)
    tasks.value = res.data?.items || []
  } catch (error) {
    console.error('加载任务失败:', error)
  }
}

// 加载模型列表
async function loadModels() {
  try {
    const res = await getModelsApi({ page: 1, page_size: 100, status: 'active' })
    models.value = res.data?.items || []
  } catch (error) {
    console.error('加载模型列表失败:', error)
  }
}

// 选择任务
async function selectTask(task) {
  currentTask.value = task
  await loadMetrics()
}

// 创建任务
async function createTask() {
  if (!createForm.value.model_id || !createForm.value.dataset_path || !createForm.value.data_yaml) {
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

// 启动任务
async function startTask() {
  try {
    await startTrainingApi(currentTask.value.id)
    ElMessage.success('任务已启动')
    loadTasks()
  } catch (error) {
    ElMessage.error('启动任务失败')
  }
}

// 暂停任务
async function pauseTask() {
  try {
    await pauseTrainingApi(currentTask.value.id)
    ElMessage.success('任务已暂停')
    loadTasks()
  } catch (error) {
    ElMessage.error('暂停任务失败')
  }
}

// 恢复训练
async function resumeTask() {
  try {
    await startTrainingApi(currentTask.value.id)
    ElMessage.success('任务已恢复')
    loadTasks()
  } catch (error) {
    ElMessage.error('恢复任务失败')
  }
}

// 取消任务
async function cancelTask() {
  try {
    await ElMessageBox.confirm('确定取消此训练任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await cancelTrainingApi(currentTask.value.id)
    ElMessage.success('任务已取消')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消任务失败')
    }
  }
}

// 处理模型文件选择
function handleModelFileChange(file) {
  uploadForm.value.model_file = file.raw
}

// 上传模型
async function uploadModel() {
  if (!uploadForm.value.model_id || !uploadForm.value.model_file || !uploadForm.value.version) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  uploading.value = true
  try {
    const res = await uploadModelApi(uploadForm.value)
    ElMessage.success(`模型上传成功：${res.data?.version}`)
    showUploadDialog.value = false
    // 重置表单
    uploadForm.value = {
      model_id: null,
      model_file: null,
      version: 'v1.0.0',
      description: '',
      is_default: true
    }
  } catch (error) {
    ElMessage.error('上传模型失败')
  } finally {
    uploading.value = false
  }
}

// 加载训练指标
async function loadMetrics() {
  if (!currentTask.value) return
  
  try {
    const res = await getTrainingMetricsApi(currentTask.value.id)
    metrics.value = res.data || []
    await nextTick()
    renderCharts()
  } catch (error) {
    console.error('加载指标失败:', error)
  }
}

// 刷新指标
function refreshMetrics() {
  loadMetrics()
}

// 渲染图表
function renderCharts() {
  if (!metrics.value.length) return

  // 损失函数图表
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

  // mAP 图表
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

// 状态文本
function getStatusType(status) {
  const map = {
    pending: 'info',
    running: 'warning',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return map[status] || 'info'
}

function getStatusText(status) {
  const map = {
    pending: '等待中',
    running: '运行中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return map[status] || status
}

// 格式化时间
function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleString('zh-CN')
}

// 轮询运行中的任务
function startPolling() {
  pollingTimer.value = setInterval(() => {
    const hasRunning = tasks.value.some(t => t.status === 'running')
    if (hasRunning) {
      loadTasks()
      if (currentTask.value?.status === 'running') {
        loadMetrics()
      }
    }
  }, 5000)
}

// 监听窗口大小变化，重绘图表
function handleResize() {
  lossChart?.resize()
  mapChart?.resize()
}

onMounted(() => {
  loadTasks()
  loadModels()
  startPolling()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
  }
  window.removeEventListener('resize', handleResize)
  lossChart?.dispose()
  mapChart?.dispose()
})
</script>

<style lang="scss" scoped>
.training-page {
  display: flex;
  height: calc(100vh - #{$header-height} - 40px);
  background: $bg-color;
}

.task-list-panel {
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

    .header-actions {
      display: flex;
      gap: $spacing-sm;
    }
  }

  .status-filter {
    padding: $spacing-sm $spacing-md;
    border-bottom: 1px solid #ebeef5;
  }

  .task-items {
    flex: 1;
    overflow-y: auto;
    padding: $spacing-sm;
  }

  .task-item {
    padding: $spacing-md;
    border-radius: $border-radius-md;
    cursor: pointer;
    transition: background 0.2s;
    margin-bottom: $spacing-sm;

    &:hover {
      background: #f5f7fa;
    }

    &.active {
      background: #ecf5ff;
    }

    &.running {
      border-left: 3px solid $warning-color;
    }

    .task-info {
      .task-name {
        font-size: 14px;
        color: $text-primary;
        margin-bottom: $spacing-xs;
      }

      .task-meta {
        display: flex;
        align-items: center;
        gap: $spacing-sm;

        .task-time {
          font-size: 12px;
          color: $text-secondary;
        }
      }
    }

    .el-progress {
      margin-top: $spacing-sm;
    }
  }

  .empty-tasks {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: $text-secondary;

    p {
      margin: $spacing-md 0 0;
    }
  }
}

.detail-panel {
  flex: 1;
  padding: $spacing-lg;
  overflow-y: auto;
}

.task-detail-card,
.metrics-card,
.log-card {
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

    .task-actions {
      display: flex;
      gap: $spacing-sm;
    }
  }
}

.metrics-card {
  .charts-container {
    display: flex;
    gap: $spacing-lg;

    .chart-item {
      flex: 1;

      h4 {
        margin: 0 0 $spacing-md;
        font-size: 14px;
        color: $text-regular;
        text-align: center;
      }

      .chart {
        height: 300px;
      }
    }
  }
}

.log-card {
  .log-content {
    background: #1e1e1e;
    border-radius: $border-radius-md;
    padding: $spacing-md;
    max-height: 300px;
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

.form-tip {
  margin-left: $spacing-sm;
  font-size: 12px;
  color: $text-secondary;
}
</style>
