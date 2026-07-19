<template>
  <div class="dashboard-page">
    <div class="page-header">
      <div>
        <h2>食材数据看板</h2>
        <p>展示当前账号的识别、确认、菜谱与对话数据。</p>
      </div>
      <el-button type="primary" @click="$router.push('/history')">
        查看历史
        <el-icon class="el-icon--right"><ArrowRight /></el-icon>
      </el-button>
    </div>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      :closable="false"
      show-icon
      class="load-alert"
    />

    <div v-loading="loading" class="stats-grid">
      <article v-for="item in statItems" :key="item.label" class="stat-card">
        <div class="stat-icon" :class="item.tone">
          <el-icon :size="24"><component :is="item.icon" /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </article>
    </div>

    <div class="analysis-grid">
      <section class="panel">
        <div class="panel-heading">
          <h3>近 7 日识别批次</h3>
        </div>
        <div ref="trendChartRef" class="chart" aria-label="近 7 日识别趋势"></div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <h3>已确认食材分布</h3>
        </div>
        <div ref="ingredientChartRef" class="chart" aria-label="已确认食材分布"></div>
      </section>
    </div>

    <section class="panel activity-panel">
      <div class="panel-heading">
        <h3>最近活动</h3>
      </div>
      <el-table :data="recentActivity" v-loading="loading" empty-text="还没有可展示的食材活动">
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag :type="activityTagType(row.type)" size="small">{{ activityLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="内容" min-width="220" />
        <el-table-column label="时间" width="190">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ArrowRight, ChatDotRound, Dish, Food, List, Tickets } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getFoodDashboardStatsApi } from '@/api/dashboard'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const loadError = ref('')
const dashboard = ref({
  overview: {},
  trend: [],
  ingredient_distribution: [],
  recent_activity: []
})
const trendChartRef = ref(null)
const ingredientChartRef = ref(null)
let trendChart = null
let ingredientChart = null

const statItems = computed(() => {
  const overview = dashboard.value.overview || {}
  return [
    { label: '识别批次', value: overview.recognitions || 0, icon: List, tone: 'blue' },
    { label: '候选食材', value: overview.detected_items || 0, icon: Food, tone: 'green' },
    { label: '确认食材', value: overview.confirmed_ingredients || 0, icon: Dish, tone: 'amber' },
    { label: '菜谱', value: overview.recipes || 0, icon: Tickets, tone: 'rose' },
    { label: '对话会话', value: overview.chat_sessions || 0, icon: ChatDotRound, tone: 'indigo' }
  ]
})

const recentActivity = computed(() => dashboard.value.recent_activity || [])

async function loadDashboard() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getFoodDashboardStatsApi()
    dashboard.value = response.data || dashboard.value
    await nextTick()
    renderCharts()
  } catch (error) {
    loadError.value = '食材数据暂时无法加载，请稍后重试。'
    console.error('加载食材数据看板失败:', error)
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  renderTrendChart()
  renderIngredientChart()
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  trendChart?.dispose()
  trendChart = echarts.init(trendChartRef.value)
  const trend = dashboard.value.trend || []
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { top: 24, right: 20, bottom: 28, left: 38 },
    xAxis: {
      type: 'category',
      data: trend.map(item => item.date.slice(5)),
      boundaryGap: false
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name: '识别批次',
      type: 'line',
      smooth: true,
      data: trend.map(item => item.count),
      lineStyle: { color: '#3478f6', width: 3 },
      itemStyle: { color: '#3478f6' },
      areaStyle: { color: 'rgba(52, 120, 246, 0.12)' }
    }]
  })
}

function renderIngredientChart() {
  if (!ingredientChartRef.value) return
  ingredientChart?.dispose()
  ingredientChart = echarts.init(ingredientChartRef.value)
  const items = dashboard.value.ingredient_distribution || []
  ingredientChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [{
      type: 'pie',
      radius: ['36%', '64%'],
      data: items.map(item => ({ name: item.name, value: item.count })),
      label: { formatter: '{b}: {c}' },
      emptyCircleStyle: { color: '#edf0f5' }
    }],
    graphic: items.length
      ? []
      : [{ type: 'text', left: 'center', top: 'center', style: { text: '暂无确认食材', fill: '#8492a6', fontSize: 14 } }]
  })
}

function activityTagType(type) {
  return { recognition: 'primary', recipe: 'success', chat: 'warning' }[type] || 'info'
}

function activityLabel(type) {
  return { recognition: '识别', recipe: '菜谱', chat: '对话' }[type] || '活动'
}

function handleResize() {
  trendChart?.resize()
  ingredientChart?.resize()
}

onMounted(() => {
  loadDashboard()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  ingredientChart?.dispose()
})
</script>

<style lang="scss" scoped>
.dashboard-page {
  min-height: calc(100vh - #{$header-height} - 40px);
  padding: $spacing-lg;
  background: $bg-color;
}

.page-header,
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-header {
  margin-bottom: $spacing-lg;

  h2 {
    margin: 0;
    color: $text-primary;
    font-size: 20px;
  }

  p {
    margin: 6px 0 0;
    color: $text-secondary;
    font-size: 14px;
  }
}

.load-alert { margin-bottom: $spacing-lg; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: $spacing-md;
  margin-bottom: $spacing-lg;
}

.stat-card,
.panel {
  background: #fff;
  border: 1px solid #e8edf4;
  border-radius: 8px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  min-height: 94px;
  padding: $spacing-md;
}

.stat-icon {
  display: grid;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  place-items: center;

  &.blue { background: #eaf1ff; color: #3478f6; }
  &.green { background: #e8f7ef; color: #2c9a61; }
  &.amber { background: #fff4dc; color: #b87916; }
  &.rose { background: #fff0ef; color: #d25a54; }
  &.indigo { background: #eff0ff; color: #5859ba; }
}

.stat-value { color: $text-primary; font-size: 24px; font-weight: 600; }
.stat-label { margin-top: 4px; color: $text-secondary; font-size: 13px; }

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $spacing-lg;
  margin-bottom: $spacing-lg;
}

.panel { padding: $spacing-lg; }
.panel-heading { margin-bottom: $spacing-md; }
.panel-heading h3 { margin: 0; color: $text-primary; font-size: 16px; }
.chart { height: 290px; }
.activity-panel { margin-bottom: $spacing-lg; }

@media (max-width: 1200px) {
  .stats-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .dashboard-page { padding: $spacing-md; }
  .page-header { align-items: flex-start; gap: $spacing-sm; }
  .stats-grid, .analysis-grid { grid-template-columns: 1fr; }
  .chart { height: 250px; }
}
</style>
