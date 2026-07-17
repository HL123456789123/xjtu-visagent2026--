<template>
  <div class="dashboard-page">
    <!-- 统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card">
        <div class="stat-icon" style="background: #409eff20; color: #409eff">
          <el-icon :size="32"><Aim /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.totalDetections }}</div>
          <div class="stat-label">检测次数</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon" style="background: #67c23a20; color: #67c23a">
          <el-icon :size="32"><Box /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.totalObjects }}</div>
          <div class="stat-label">检测目标</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon" style="background: #e6a23c20; color: #e6a23c">
          <el-icon :size="32"><Cpu /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.totalModels }}</div>
          <div class="stat-label">训练模型</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon" style="background: #f56c6c20; color: #f56c6c">
          <el-icon :size="32"><ChatDotRound /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.totalChats }}</div>
          <div class="stat-label">对话次数</div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-row">
      <!-- 检测趋势图 -->
      <div class="chart-card">
        <div class="card-header">
          <h3>检测趋势</h3>
          <el-radio-group v-model="trendPeriod" size="small" @change="loadTrendData">
            <el-radio-button value="week">近7天</el-radio-button>
            <el-radio-button value="month">近30天</el-radio-button>
          </el-radio-group>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>

      <!-- 目标类别分布 -->
      <div class="chart-card">
        <div class="card-header">
          <h3>目标类别分布</h3>
        </div>
        <div ref="categoryChartRef" class="chart-container"></div>
      </div>
    </div>

    <div class="charts-row">
      <!-- 场景检测统计 -->
      <div class="chart-card">
        <div class="card-header">
          <h3>场景检测统计</h3>
        </div>
        <div ref="sceneChartRef" class="chart-container"></div>
      </div>

      <!-- 模型性能对比 -->
      <div class="chart-card">
        <div class="card-header">
          <h3>模型性能对比</h3>
        </div>
        <div ref="modelChartRef" class="chart-container"></div>
      </div>
    </div>

    <!-- 最近活动 -->
    <div class="recent-activities">
      <div class="card-header">
        <h3>最近活动</h3>
        <el-button type="primary" link @click="$router.push('/history')">
          查看全部<el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </div>
      <el-table :data="recentActivities" stripe>
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getActivityType(row.type)" size="small">
              {{ getActivityText(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="time" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.time) }}
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Aim, Box, Cpu, ChatDotRound, ArrowRight } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDashboardStatsApi } from '@/api/dashboard'

// 统计数据
const stats = ref({
  totalDetections: 0,
  totalObjects: 0,
  totalModels: 0,
  totalChats: 0
})

// 趋势周期
const trendPeriod = ref('week')

// 图表引用
const trendChartRef = ref(null)
const categoryChartRef = ref(null)
const sceneChartRef = ref(null)
const modelChartRef = ref(null)

// 图表实例
let trendChart = null
let categoryChart = null
let sceneChart = null
let modelChart = null

// 最近活动
const recentActivities = ref([])

// 后端原始数据缓存
let _statsData = null

// 加载统计数据
async function loadStats() {
  try {
    const res = await getDashboardStatsApi()
    const data = res.data
    _statsData = data

    // 概览统计
    stats.value.totalDetections = data.overview.total_detections || 0
    stats.value.totalObjects = 0 // 后端暂未聚合，可后续扩展
    stats.value.totalModels = data.overview.total_models || 0
    stats.value.totalChats = data.overview.total_sessions || 0

    // 最近活动
    recentActivities.value = (data.recent_detections || []).map(d => ({
      type: 'detection',
      description: `完成${d.task_type === 'single' ? '单图' : d.task_type === 'batch' ? '批量' : '视频'}检测，发现 ${d.total_objects || 0} 个目标`,
      time: d.created_at
    }))
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

// 加载趋势数据
async function loadTrendData() {
  await loadStats()
  await nextTick()
  renderTrendChart()
}

// 渲染趋势图
function renderTrendChart() {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.dispose()
  }
  trendChart = echarts.init(trendChartRef.value)

  const trend = _statsData?.trend || []
  const dates = trend.map(t => {
    const d = new Date(t.date)
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  })
  const values = trend.map(t => t.count)

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '检测次数' },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      },
      lineStyle: { color: '#409eff' },
      itemStyle: { color: '#409eff' }
    }]
  })
}

// 渲染类别分布图
function renderCategoryChart() {
  if (!categoryChartRef.value) return
  
  if (categoryChart) categoryChart.dispose()
  categoryChart = echarts.init(categoryChartRef.value)

  const classDist = _statsData?.class_distribution || []
  const pieData = classDist.map(c => ({ value: c.count, name: c.name }))

  categoryChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: '60%',
      center: ['50%', '50%'],
      data: pieData.length > 0 ? pieData : [{ value: 0, name: '暂无数据' }],
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

// 渲染场景统计图
function renderSceneChart() {
  if (!sceneChartRef.value) return
  
  if (sceneChart) sceneChart.dispose()
  sceneChart = echarts.init(sceneChartRef.value)

  const sceneStats = _statsData?.scene_stats || []
  const names = sceneStats.map(s => s.name)
  const counts = sceneStats.map(s => s.count)

  sceneChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: names.length > 0 ? names : ['暂无'] },
    yAxis: { type: 'value', name: '检测次数' },
    series: [{
      type: 'bar',
      data: counts.length > 0 ? counts : [0],
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#409eff' },
          { offset: 1, color: '#79bbff' }
        ])
      }
    }]
  })
}

// 渲染模型对比图（使用训练任务状态分布代替）
function renderModelChart() {
  if (!modelChartRef.value) return
  
  if (modelChart) modelChart.dispose()
  modelChart = echarts.init(modelChartRef.value)

  const trainingStatus = _statsData?.training_status || []
  const statusMap = { pending: '等待中', running: '运行中', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' }
  const names = trainingStatus.map(s => statusMap[s.status] || s.status)
  const counts = trainingStatus.map(s => s.count)

  modelChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: names.length > 0 ? names : ['暂无'] },
    yAxis: { type: 'value', name: '任务数' },
    series: [{
      type: 'bar',
      data: counts.length > 0 ? counts : [0],
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#67c23a' },
          { offset: 1, color: '#95d475' }
        ])
      }
    }]
  })
}

// 活动类型
function getActivityType(type) {
  const map = {
    detection: 'primary',
    training: 'warning',
    chat: 'success'
  }
  return map[type] || 'info'
}

function getActivityText(type) {
  const map = {
    detection: '检测',
    training: '训练',
    chat: '对话'
  }
  return map[type] || type
}

// 格式化时间
function formatTime(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleString('zh-CN')
}

// 窗口大小变化
function handleResize() {
  trendChart?.resize()
  categoryChart?.resize()
  sceneChart?.resize()
  modelChart?.resize()
}

onMounted(async () => {
  await loadStats()
  await nextTick()
  renderTrendChart()
  renderCategoryChart()
  renderSceneChart()
  renderModelChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  categoryChart?.dispose()
  sceneChart?.dispose()
  modelChart?.dispose()
})
</script>

<style lang="scss" scoped>
.dashboard-page {
  padding: $spacing-lg;
  min-height: calc(100vh - #{$header-height} - 40px);
  background:
    radial-gradient(circle at 12% 10%, rgba(255, 213, 118, 0.34), transparent 28%),
    radial-gradient(circle at 86% 8%, rgba(137, 169, 79, 0.18), transparent 26%),
    linear-gradient(180deg, #fff8ea 0%, #fffdf7 48%, #f8efe3 100%);
  color: #3a2a1d;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: $spacing-lg;
  margin-bottom: $spacing-lg;
}

.stat-card {
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-lg;
  display: flex;
  align-items: center;
  gap: $spacing-md;
  box-shadow: $shadow-sm;

  .stat-icon {
    width: 64px;
    height: 64px;
    border-radius: $border-radius-md;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .stat-info {
    .stat-value {
      font-size: 28px;
      font-weight: 600;
      color: $text-primary;
    }

    .stat-label {
      font-size: 14px;
      color: $text-secondary;
      margin-top: $spacing-xs;
    }
  }
}

.charts-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: $spacing-lg;
  margin-bottom: $spacing-lg;
}

.chart-card {
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-lg;
  box-shadow: $shadow-sm;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-md;

    h3 {
      margin: 0;
      font-size: 16px;
      color: $text-primary;
    }
  }

  .chart-container {
    height: 300px;
  }
}

.recent-activities {
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-lg;
  box-shadow: $shadow-sm;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-md;

    h3 {
      margin: 0;
      font-size: 16px;
      color: $text-primary;
    }
  }
}
</style>
