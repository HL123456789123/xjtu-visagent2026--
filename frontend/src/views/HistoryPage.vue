<template>
  <main class="history-page">
    <header class="page-heading">
      <div>
        <h1>历史记录</h1>
        <p>查看保存过的菜谱和每一次对话修改。</p>
      </div>
    </header>

    <section class="history-list" v-loading="loading">
      <el-empty v-if="!loading && records.length === 0" description="还没有菜谱记录" />
      <article v-for="item in records" :key="item.recipe_id" class="history-item">
        <header>
          <div>
            <h2>{{ item.title }}</h2>
            <p>{{ ingredientText(item.confirmed_ingredients) || '尚未记录确认食材' }}</p>
          </div>
          <el-tag type="success" effect="light">当前 v{{ item.version }}</el-tag>
        </header>

        <div class="history-item__meta">
          <span>{{ formatTime(item.updated_at) }}</span>
          <span v-if="item.latest_session">{{ item.latest_session.message_count }} 条对话消息</span>
        </div>

        <div class="history-item__actions">
          <el-button type="primary" @click="viewRecipe(item)">查看当前菜谱</el-button>
          <el-button @click="continueChat(item)">继续对话</el-button>
          <el-button data-testid="history-versions" text :loading="versionLoadingId === item.recipe_id" @click="toggleVersions(item)">
            {{ expandedRecipeId === item.recipe_id ? '收起版本' : '查看版本' }}
          </el-button>
        </div>

        <ol v-if="expandedRecipeId === item.recipe_id" class="version-timeline">
          <li v-for="version in versions" :key="version.version">
            <span class="version-timeline__dot"></span>
            <div class="version-card">
              <header>
                <strong>v{{ version.version }} · {{ changeTypeText(version.change_type) }}</strong>
                <el-tag v-if="version.is_current" size="small" type="success">当前版本</el-tag>
              </header>
              <p>{{ version.change_reason || defaultReason(version.change_type) }}</p>
              <blockquote v-if="version.source_message">
                你当时说：{{ version.source_message }}
              </blockquote>
              <small>{{ formatTime(version.created_at) }}</small>
              <div class="version-card__actions">
                <el-button link type="primary" @click="openVersion(item, version)">查看</el-button>
                <el-button
                  v-if="!version.is_current"
                  link
                  type="warning"
                  data-testid="history-restore-version"
                  @click="restoreVersion(item, version)"
                >恢复为新版本</el-button>
              </div>
            </div>
          </li>
        </ol>
      </article>
    </section>

    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next"
      @current-change="loadHistory"
    />

    <el-dialog v-model="detailVisible" :title="detailTitle" width="min(880px, 94vw)" destroy-on-close>
      <RecipeCard v-if="versionDetail" :recipe="versionDetail" :show-actions="false" />
    </el-dialog>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import RecipeCard from '@/components/recipe/RecipeCard.vue'
import {
  getRecipeHistory,
  getRecipeVersion,
  getRecipeVersions,
  restoreRecipeVersion,
} from '@/api/recipe'
import { formatTime } from '@/utils/format'

const router = useRouter()
const records = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const expandedRecipeId = ref(null)
const versionLoadingId = ref(null)
const versions = ref([])
const detailVisible = ref(false)
const detailTitle = ref('菜谱版本')
const versionDetail = ref(null)

async function loadHistory() {
  loading.value = true
  try {
    const response = await getRecipeHistory({ page: currentPage.value, page_size: pageSize.value })
    records.value = response.data?.items || []
    total.value = response.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function toggleVersions(item) {
  if (expandedRecipeId.value === item.recipe_id) {
    expandedRecipeId.value = null
    versions.value = []
    return
  }
  await loadVersions(item.recipe_id)
}

async function loadVersions(recipeId) {
  versionLoadingId.value = recipeId
  try {
    const response = await getRecipeVersions(recipeId)
    versions.value = response.data?.versions || []
    expandedRecipeId.value = recipeId
  } finally {
    versionLoadingId.value = null
  }
}

async function openVersion(item, version) {
  const response = await getRecipeVersion(item.recipe_id, version.version)
  const snapshot = response.data
  versionDetail.value = {
    ...snapshot.recipe,
    recipe_id: item.recipe_id,
    version: snapshot.version,
  }
  detailTitle.value = `${item.title} · v${version.version}`
  detailVisible.value = true
}

async function restoreVersion(item, version) {
  await ElMessageBox.confirm(
    `将 v${version.version} 的内容复制为新的最新版本？原有版本都会保留。`,
    '恢复菜谱版本',
    { confirmButtonText: '恢复', cancelButtonText: '取消', type: 'warning' },
  )
  const response = await restoreRecipeVersion(item.recipe_id, version.version)
  ElMessage.success(`已生成新版本 v${response.data.version}`)
  await loadHistory()
  await loadVersions(item.recipe_id)
}

function ingredientText(ingredients = []) {
  return ingredients.map((ingredient) => ingredient.name).filter(Boolean).join('、')
}

function changeTypeText(type) {
  return { generated: '初次生成', chat_update: '对话修改', restore: '版本恢复', backfill: '历史补录' }[type] || '菜谱更新'
}

function defaultReason(type) {
  return type === 'generated' ? '初次生成菜谱' : type === 'restore' ? '从旧版本恢复' : '保存菜谱内容'
}

function viewRecipe(item) {
  router.push({ path: '/food-recipes', query: { recipe_id: item.recipe_id } })
}

function continueChat(item) {
  router.push({ path: '/chat', query: { recipe_id: item.recipe_id } })
}

loadHistory()
</script>

<style lang="scss" scoped>
.history-page { display: grid; gap: 20px; min-height: calc(100vh - #{$header-height}); padding: 24px; background: #f8f7f3; color: #352a21; }
.page-heading h1 { margin: 0; }
.page-heading p { margin: 6px 0 0; color: #75685d; }
.history-list { display: grid; align-content: start; gap: 14px; }
.history-item { padding: 20px; border: 1px solid #e5dfd7; border-radius: 8px; background: #fff; }
.history-item > header, .history-item__meta, .history-item__actions, .version-card header, .version-card__actions { display: flex; align-items: center; gap: 12px; }
.history-item > header { justify-content: space-between; }
.history-item h2 { margin: 0; font-size: 20px; }
.history-item header p { margin: 6px 0 0; color: #6f6256; }
.history-item__meta { flex-wrap: wrap; margin-top: 12px; color: #8a7b6d; font-size: 13px; }
.history-item__actions { flex-wrap: wrap; margin-top: 16px; }
.version-timeline { display: grid; gap: 0; margin: 20px 0 0; padding: 0 0 0 12px; list-style: none; }
.version-timeline li { position: relative; padding: 0 0 14px 22px; border-left: 2px solid #e8dfd3; }
.version-timeline__dot { position: absolute; top: 14px; left: -6px; width: 10px; height: 10px; border-radius: 50%; background: #81963c; }
.version-card { padding: 14px 16px; border: 1px solid #ece5dc; border-radius: 6px; background: #fffdf9; }
.version-card header { justify-content: space-between; }
.version-card p { margin: 8px 0; color: #67594d; white-space: pre-wrap; }
.version-card blockquote { margin: 8px 0; padding: 8px 10px; border-left: 3px solid #d9a24b; background: #fff8e9; color: #59483a; }
.version-card small { color: #918376; }
.version-card__actions { justify-content: flex-end; }
@media (max-width: 640px) { .history-page { padding: 14px; } .history-item > header { align-items: flex-start; } }
</style>
