<template>
  <div class="history-page">
    <div class="filter-bar">
      <el-radio-group v-model="historyType" @change="changeHistoryType">
        <el-radio-button v-for="item in historyTabs" :key="item.value" :value="item.value">
          {{ item.label }}
        </el-radio-button>
      </el-radio-group>
      <el-select
        v-if="historyType === 'detection'"
        v-model="sceneFilter"
        clearable
        placeholder="所有场景"
        class="scene-select"
        @change="loadHistory"
      >
        <el-option v-for="scene in scenes" :key="scene.id" :label="scene.display_name" :value="scene.id" />
      </el-select>
    </div>

    <section v-if="historyType === 'food'" class="record-list" v-loading="loading">
      <el-empty v-if="records.length === 0" description="还没有食材识别和菜谱记录" />
      <div v-else class="food-history-list">
        <article v-for="item in records" :key="item.recipe_id" class="food-history-card">
          <div class="food-history-card__title">
            <div>
              <span class="food-history-card__eyebrow">Recipe v{{ item.version }}</span>
              <h3>{{ item.title }}</h3>
            </div>
            <el-tag type="success" effect="light">{{ item.provider }} · {{ item.model_version }}</el-tag>
          </div>
          <p class="food-history-card__ingredients">
            {{ ingredientText(item.confirmed_ingredients) || '尚未确认食材' }}
          </p>
          <div class="food-history-card__meta">
            <span>{{ item.image_count }} 张图片</span>
            <span>{{ formatTime(item.updated_at) }}</span>
            <span v-if="item.latest_session">{{ item.latest_session.message_count }} 条对话消息</span>
          </div>
          <div class="food-history-card__actions">
            <el-button type="primary" @click="viewRecipe(item)">查看菜谱</el-button>
            <el-button @click="continueChat(item)">继续对话</el-button>
          </div>
        </article>
      </div>
    </section>

    <section v-else class="record-list" v-loading="loading">
      <el-table v-if="historyType === 'detection'" :data="records" stripe @row-click="viewDetectionDetail">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="task_type" label="类型" width="110" />
        <el-table-column prop="total_images" label="图像数" width="100" />
        <el-table-column prop="total_objects" label="目标数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-table v-else :data="records" stripe @row-click="viewTrainingDetail">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="model_name" label="模型" min-width="140" />
        <el-table-column prop="epochs" label="轮数" width="90" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </section>

    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadHistory"
        @current-change="loadHistory"
      />
    </div>

    <el-dialog v-model="showDetectionDetail" title="检测详情" width="760px">
      <el-table :data="detectionResults" stripe>
        <el-table-column prop="class_name" label="类别" />
        <el-table-column prop="confidence" label="置信度">
          <template #default="{ row }">{{ Number(row.confidence || 0).toFixed(2) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getDetectionResultsApi, getDetectionTasksApi, getScenesApi } from '@/api/detection'
import { getRecipeHistory } from '@/api/recipe'
import { getTrainingTasksApi } from '@/api/training'
import { formatTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const historyType = ref('food')
const records = ref([])
const scenes = ref([])
const sceneFilter = ref(null)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const showDetectionDetail = ref(false)
const detectionResults = ref([])

const historyTabs = computed(() => {
  const tabs = [{ value: 'food', label: '食材与菜谱' }]
  if (userStore.hasPermission('detection:task:view')) tabs.push({ value: 'detection', label: '检测记录' })
  if (userStore.hasPermission('training:task:view')) tabs.push({ value: 'training', label: '训练记录' })
  return tabs
})

async function loadScenes() {
  try {
    const response = await getScenesApi()
    scenes.value = response.data || []
  } catch (error) {
    console.error('加载场景失败:', error)
  }
}

async function loadHistory() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    let response
    if (historyType.value === 'food') response = await getRecipeHistory(params)
    else if (historyType.value === 'detection') {
      if (sceneFilter.value) params.scene_id = sceneFilter.value
      response = await getDetectionTasksApi(params)
    } else response = await getTrainingTasksApi(params)
    records.value = response.data?.items || []
    total.value = response.data?.total || 0
  } catch (error) {
    records.value = []
    total.value = 0
    console.error('加载历史记录失败:', error)
  } finally {
    loading.value = false
  }
}

function changeHistoryType() {
  currentPage.value = 1
  if (historyType.value === 'detection') loadScenes()
  loadHistory()
}

function ingredientText(ingredients = []) {
  return ingredients.map((item) => item.name).filter(Boolean).join('、')
}

function viewRecipe(item) {
  router.push({ path: '/food-recipes', query: { recipe_id: item.recipe_id } })
}

function continueChat(item) {
  router.push({ path: '/chat', query: { recipe_id: item.recipe_id } })
}

async function viewDetectionDetail(row) {
  showDetectionDetail.value = true
  try {
    const response = await getDetectionResultsApi(row.id, { page: 1, page_size: 100 })
    detectionResults.value = response.data?.items || []
  } catch (error) {
    detectionResults.value = []
    console.error('加载检测详情失败:', error)
  }
}

function viewTrainingDetail(row) {
  router.push({ path: '/training', query: { task_id: row.id } })
}

function getStatusType(status) {
  return { completed: 'success', running: 'warning', failed: 'danger', paused: 'warning' }[status] || 'info'
}

function getStatusText(status) {
  return { completed: '已完成', running: '运行中', failed: '失败', paused: '已暂停', pending: '等待中', cancelled: '已取消' }[status] || status
}

onMounted(async () => {
  await loadHistory()
})
</script>

<style lang="scss" scoped>
.history-page { min-height: calc(100vh - #{$header-height} - 40px); padding: $spacing-lg; background: $bg-color; }
.filter-bar, .record-list { background: #fff; border-radius: $border-radius-lg; padding: $spacing-md; }
.filter-bar { display: flex; align-items: center; justify-content: space-between; gap: $spacing-md; margin-bottom: $spacing-lg; }
.scene-select { width: 220px; }
.food-history-list { display: grid; gap: $spacing-md; }
.food-history-card { border: 1px solid #ebeef5; border-radius: $border-radius-md; padding: $spacing-md; }
.food-history-card__title, .food-history-card__meta, .food-history-card__actions { display: flex; align-items: center; gap: $spacing-sm; }
.food-history-card__title { justify-content: space-between; }
.food-history-card h3 { margin: 4px 0 0; }
.food-history-card__eyebrow { color: $text-secondary; font-size: 12px; }
.food-history-card__ingredients { margin: $spacing-sm 0; color: $text-regular; }
.food-history-card__meta { color: $text-secondary; font-size: 13px; flex-wrap: wrap; }
.food-history-card__actions { justify-content: flex-end; margin-top: $spacing-md; }
.pagination { display: flex; justify-content: flex-end; margin-top: $spacing-lg; }
</style>
