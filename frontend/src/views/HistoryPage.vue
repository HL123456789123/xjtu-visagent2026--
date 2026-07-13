<template>
  <div class="history-page">
    <!-- 顶部筛选栏 -->
    <div class="filter-bar">
      <div class="filter-left">
        <el-radio-group v-model="historyType" @change="loadHistory">
          <el-radio-button value="detection">检测记录</el-radio-button>
          <el-radio-button value="training">训练记录</el-radio-button>
        </el-radio-group>
        
        <el-select v-model="sceneFilter" placeholder="所有场景" clearable @change="loadHistory" class="scene-select">
          <el-option
            v-for="scene in scenes"
            :key="scene.id"
            :label="scene.display_name"
            :value="scene.id"
          />
        </el-select>
      </div>
      
      <div class="filter-right">
        <el-input
          v-model="searchText"
          placeholder="搜索..."
          clearable
          @clear="loadHistory"
          @keyup.enter="loadHistory"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 检测记录列表 -->
    <div v-if="historyType === 'detection'" class="record-list">
      <el-table :data="records" stripe @row-click="viewDetectionDetail">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="task_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getTaskTypeText(row.task_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="scene_id" label="场景" width="120">
          <template #default="{ row }">
            {{ getSceneName(row.scene_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_images" label="图像数" width="100" />
        <el-table-column prop="total_objects" label="目标数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="conf_threshold" label="置信度" width="100">
          <template #default="{ row }">
            {{ row.conf_threshold?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewDetectionDetail(row)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 训练记录列表 -->
    <div v-else class="record-list">
      <el-table :data="records" stripe @row-click="viewTrainingDetail">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="model_name" label="模型" width="120" />
        <el-table-column prop="scene_id" label="场景" width="120">
          <template #default="{ row }">
            {{ getSceneName(row.scene_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="epochs" label="轮数" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="{ row }">
            <el-progress
              v-if="row.status === 'running'"
              :percentage="row.progress || 0"
              :stroke-width="6"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewTrainingDetail(row)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadHistory"
        @current-change="loadHistory"
      />
    </div>

    <!-- 检测详情对话框 -->
    <el-dialog v-model="showDetectionDetail" title="检测详情" width="800px">
      <template v-if="selectedDetection">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务ID">{{ selectedDetection.id }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ getTaskTypeText(selectedDetection.task_type) }}</el-descriptions-item>
          <el-descriptions-item label="场景">{{ getSceneName(selectedDetection.scene_id) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(selectedDetection.status)">
              {{ getStatusText(selectedDetection.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="图像数">{{ selectedDetection.total_images }}</el-descriptions-item>
          <el-descriptions-item label="目标数">{{ selectedDetection.total_objects }}</el-descriptions-item>
          <el-descriptions-item label="置信度阈值">{{ selectedDetection.conf_threshold?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="IoU阈值">{{ selectedDetection.iou_threshold?.toFixed(2) }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-results" v-if="detectionResults.length > 0">
          <h4>检测结果</h4>
          <el-table :data="detectionResults" stripe max-height="300">
            <el-table-column prop="class_name" label="类别" width="120" />
            <el-table-column prop="confidence" label="置信度" width="100">
              <template #default="{ row }">
                {{ (row.confidence * 100).toFixed(1) }}%
              </template>
            </el-table-column>
            <el-table-column label="位置">
              <template #default="{ row }">
                {{ row.bbox?.map(v => v.toFixed(0)).join(', ') }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getDetectionTasksApi, getDetectionResultsApi } from '@/api/detection'
import { getTrainingTasksApi } from '@/api/training'
import { getScenesApi } from '@/api/detection'
import { useRouter } from 'vue-router'
import { formatTime } from '@/utils/format'

const router = useRouter()

// 历史记录类型
const historyType = ref('detection')
const records = ref([])
const scenes = ref([])
const sceneFilter = ref(null)
const searchText = ref('')

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 详情对话框
const showDetectionDetail = ref(false)
const selectedDetection = ref(null)
const detectionResults = ref([])

// 加载场景列表
async function loadScenes() {
  try {
    const res = await getScenesApi()
    scenes.value = res.data || []
  } catch (error) {
    console.error('加载场景失败:', error)
  }
}

// 加载历史记录
async function loadHistory() {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (sceneFilter.value) {
      params.scene_id = sceneFilter.value
    }

    let res
    if (historyType.value === 'detection') {
      res = await getDetectionTasksApi(params)
    } else {
      res = await getTrainingTasksApi(params)
    }
    
    records.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (error) {
    console.error('加载历史记录失败:', error)
  }
}

// 查看检测详情
async function viewDetectionDetail(row) {
  selectedDetection.value = row
  showDetectionDetail.value = true
  
  try {
    const res = await getDetectionResultsApi(row.id, { page: 1, page_size: 100 })
    detectionResults.value = res.data?.items || []
  } catch (error) {
    console.error('加载检测结果失败:', error)
  }
}

// 查看训练详情
function viewTrainingDetail(row) {
  router.push({
    path: '/training',
    query: { task_id: row.id }
  })
}

// 获取场景名称
function getSceneName(sceneId) {
  const scene = scenes.value.find(s => s.id === sceneId)
  return scene?.display_name || `场景 #${sceneId}`
}

// 任务类型文本
function getTaskTypeText(type) {
  const map = {
    single: '单图检测',
    batch: '批量检测',
    video: '视频检测'
  }
  return map[type] || type
}

// 状态类型
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

// 状态文本
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

onMounted(async () => {
  await loadScenes()
  await loadHistory()
})
</script>

<style lang="scss" scoped>
.history-page {
  padding: $spacing-lg;
  background: $bg-color;
  min-height: calc(100vh - #{$header-height} - 40px);
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  padding: $spacing-md;
  border-radius: $border-radius-lg;
  margin-bottom: $spacing-lg;

  .filter-left {
    display: flex;
    gap: $spacing-md;
    align-items: center;

    .scene-select {
      width: 200px;
    }
  }

  .filter-right {
    .el-input {
      width: 250px;
    }
  }
}

.record-list {
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-md;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: $spacing-lg;
}

.detail-results {
  margin-top: $spacing-lg;

  h4 {
    margin: 0 0 $spacing-md;
    font-size: 16px;
    color: $text-primary;
  }
}
</style>
