<template>
  <div class="recipe-chat-view" data-testid="recipe-chat-view">
    <!-- 左侧：菜谱展示 -->
    <section class="recipe-panel" data-testid="recipe-panel">
      <div class="recipe-panel__header">
        <h2 class="recipe-panel__title">当前菜谱</h2>
        <span v-if="recipeVersion" class="recipe-panel__version" data-testid="recipe-version">
          版本 {{ recipeVersion }}
        </span>
      </div>
      <RecipeCard
        :recipe="currentRecipe"
        :loading="recipeLoading"
        :error="recipeError"
        :show-actions="false"
      />
    </section>

    <!-- 右侧：对话区域 -->
    <section class="chat-panel" data-testid="chat-panel">
      <ChatPage
        :recipe-id="recipeId"
        @recipe-updated="handleRecipeUpdated"
        @service-unavailable="handleServiceUnavailable"
      />
    </section>
  </div>
</template>

<script setup>
/**
 * RecipeChatView — Mock 全链路整合页面
 *
 * 核心逻辑：
 * 1. 页面加载时通过 createRecipe 生成菜谱（Mock 模式）
 * 2. RecipeCard 展示当前菜谱
 * 3. ChatPage（传入 recipeId）用于对话修改菜谱
 * 4. ChatPage emit 'recipe-updated' 时，重新 GET 菜谱并更新 RecipeCard
 * 5. 纯问答（token → done）不触发刷新，只有 recipe_updated 才刷新
 */
import { ref, onMounted, computed } from 'vue'
import RecipeCard from '@/components/recipe/RecipeCard.vue'
import ChatPage from '@/views/ChatPage.vue'
import { createRecipe, getRecipe, setRecipeApiClient, resetRecipeApiClient } from '@/api/recipe'

const props = defineProps({
  /** 是否启用 Mock 模式 */
  mock: {
    type: Boolean,
    default: false,
  },
  /** Mock 客户端（注入式） */
  mockRecipeClient: {
    type: Object,
    default: null,
  },
  /** Mock fetch 函数（替代全局 fetch） */
  mockFetch: {
    type: Function,
    default: null,
  },
})

const emit = defineEmits(['recipe-refreshed', 'service-unavailable'])

// 菜谱状态
const currentRecipe = ref(null)
const recipeLoading = ref(false)
const recipeError = ref(null)

// 从菜谱中提取 recipeId
const recipeId = computed(() => currentRecipe.value?.recipe_id ?? null)

// 菜谱版本号（用于显示）
const recipeVersion = computed(() => currentRecipe.value?.version ?? null)

/**
 * 加载初始菜谱（createRecipe）
 */
async function loadInitialRecipe() {
  recipeLoading.value = true
  recipeError.value = null

  try {
    const options = {}
    if (props.mockRecipeClient) {
      options.client = props.mockRecipeClient
    } else if (props.mock) {
      options.mockScenario = 'success'
    }

    const res = await createRecipe(
      { recognition_id: 12, preferences: { servings: 2 } },
      options
    )
    currentRecipe.value = res.data
  } catch (err) {
    recipeError.value = err.response?.data || { message: err.message }
  } finally {
    recipeLoading.value = false
  }
}

/**
 * 重新获取菜谱（GET /api/recipes/{recipe_id}）
 * 仅当 ChatPage emit recipe-updated 时调用
 */
async function refreshRecipe(recipeId) {
  if (!recipeId) return

  try {
    const options = {}
    if (props.mockRecipeClient) {
      options.client = props.mockRecipeClient
    } else if (props.mock) {
      // Mock 模式下，recipe_updated 后返回 v2
      options.mockScenario = 'v2'
    }

    const res = await getRecipe(recipeId, options)
    currentRecipe.value = res.data
    emit('recipe-refreshed', res.data)
  } catch (err) {
    recipeError.value = err.response?.data || { message: err.message }
  }
}

/**
 * 处理 recipe_updated 事件（受控刷新）
 * 只有 recipe_updated 才触发重新 GET，answer 不触发
 */
function handleRecipeUpdated(payload) {
  refreshRecipe(payload.recipe_id)
}

/**
 * 处理 503 服务不可用
 */
function handleServiceUnavailable(payload) {
  emit('service-unavailable', payload)
}

// 页面加载时获取初始菜谱
onMounted(() => {
  loadInitialRecipe()
})
</script>

<style lang="scss" scoped>
.recipe-chat-view {
  display: grid;
  grid-template-columns: minmax(340px, 420px) minmax(0, 1fr);
  gap: 22px;
  min-height: calc(100vh - #{$header-height});
  padding: clamp(18px, 4vw, 42px);
  background:
    radial-gradient(circle at 12% 10%, rgba(255, 213, 118, 0.34), transparent 28%),
    radial-gradient(circle at 86% 8%, rgba(137, 169, 79, 0.18), transparent 26%),
    linear-gradient(180deg, #fff8ea 0%, #fffdf7 48%, #f8efe3 100%);
  color: #3a2a1d;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
}

.recipe-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.recipe-panel__header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.recipe-panel__title {
  margin: 0;
  color: #3a2a1d;
  font-family: Georgia, "Songti SC", serif;
  font-size: 22px;
  font-weight: 500;
}

.recipe-panel__version {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 999px;
  background: linear-gradient(135deg, #89a94f, #e6a23c);
  color: #fffaf0;
  font-size: 13px;
  font-weight: 700;
}

.chat-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 24px 70px rgba(102, 68, 35, 0.12);
  backdrop-filter: blur(18px);
}

@media (max-width: 960px) {
  .recipe-chat-view {
    grid-template-columns: 1fr;
  }
}
</style>
