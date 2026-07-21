<template>
  <article class="recipe-card" data-testid="recipe-card">
    <!-- Loading 状态 -->
    <div v-if="loading" class="recipe-card__loading" data-testid="recipe-loading">
      <span class="recipe-card__spinner"></span>
      <p>正在生成菜谱...</p>
    </div>

    <!-- 503 错误占位 -->
    <div
      v-else-if="error"
      class="recipe-card__error"
      data-testid="recipe-error"
    >
      <strong>{{ errorTitle }}</strong>
      <p>{{ errorMessage }}</p>
      <button
        v-if="error?.code === 'LLM_UNAVAILABLE' || error?.status === 503"
        class="recipe-card__retry"
        data-testid="recipe-retry"
        type="button"
        @click="emitRetry"
      >
        重试
      </button>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!hasRecipe" class="recipe-card__empty" data-testid="recipe-empty">
      <p>暂无菜谱，请先上传图片并确认食材后生成菜谱。</p>
    </div>

    <!-- 菜谱内容 -->
    <template v-else>
      <RecipeTitle
        :recipe="recipe"
        :versions="availableVersions"
        :selected-version="selectedVersion"
        :version-loading="versionLoading"
        @version-change="emitVersionChange"
      />

      <div class="recipe-card__body">
        <RecipeIngredients :ingredients="recipe.ingredients || []" />
        <RecipeSteps :steps="recipe.steps || []" />
        <NutritionPanel
          :nutrition="recipe.nutrition || {}"
          :disclaimer="recipe.nutrition_disclaimer || defaultDisclaimer"
        />
      </div>

      <footer v-if="showActions && (showShareAction || showChatAction)" class="recipe-card__actions">
        <button
          v-if="showShareAction"
          class="recipe-card__share-btn"
          type="button"
          data-testid="recipe-open-xiaohongshu-share"
          @click="shareDialogVisible = true"
        >
          生成小红书分享稿
        </button>
        <button
          v-if="showChatAction"
          class="recipe-card__chat-btn"
          type="button"
          data-testid="recipe-open-chat"
          :disabled="!recipe.recipe_id"
          @click="emitOpenChat"
        >
          对话修改菜谱
        </button>
      </footer>

      <RecipeShareDialog v-model="shareDialogVisible" :recipe="recipe" />
    </template>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import RecipeTitle from './RecipeTitle.vue'
import RecipeIngredients from './RecipeIngredients.vue'
import RecipeSteps from './RecipeSteps.vue'
import NutritionPanel from './NutritionPanel.vue'
import RecipeShareDialog from './RecipeShareDialog.vue'

const props = defineProps({
  recipe: {
    type: Object,
    default: () => ({}),
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: [Object, String, null],
    default: null,
  },
  showActions: {
    type: Boolean,
    default: true,
  },
  showShareAction: {
    type: Boolean,
    default: true,
  },
  showChatAction: {
    type: Boolean,
    default: true,
  },
  availableVersions: {
    type: Array,
    default: () => [],
  },
  selectedVersion: {
    type: Number,
    default: null,
  },
  versionLoading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['open-chat', 'retry', 'version-change'])
const shareDialogVisible = ref(false)

const defaultDisclaimer = '营养数据由模型估算，仅供参考，不构成医疗或营养建议。'

const hasRecipe = computed(() => {
  return props.recipe && (props.recipe.recipe_id || props.recipe.title)
})

const errorTitle = computed(() => {
  if (typeof props.error === 'string') return '出错了'
  if (props.error?.status === 503 || props.error?.code === 'LLM_UNAVAILABLE')
    return '智能服务不可用'
  if (props.error?.status === 404 || props.error?.code === 'RECIPE_NOT_FOUND')
    return '菜谱不存在'
  return '出错了'
})

const errorMessage = computed(() => {
  if (typeof props.error === 'string') return props.error
  return props.error?.message || '菜谱加载失败，请稍后重试。'
})

function emitOpenChat() {
  if (props.recipe?.recipe_id) {
    emit('open-chat', { recipe_id: props.recipe.recipe_id })
  }
}

function emitRetry() {
  emit('retry')
}

function emitVersionChange(version) {
  emit('version-change', version)
}
</script>

<style lang="scss" scoped>
.recipe-card {
  display: grid;
  gap: 24px;
  border: 0;
  background: transparent;
  padding: clamp(6px, 1vw, 12px);
  color: #3a2a1d;
}

.recipe-card__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: $spacing-md;
  min-height: 220px;
  justify-content: center;
  color: #856449;

  p {
    margin: 0;
    font-size: 14px;
  }
}

.recipe-card__spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #ffe0a1;
  border-top-color: #e96d3b;
  border-radius: 50%;
  animation: recipe-spin 0.8s linear infinite;
}

@keyframes recipe-spin {
  to {
    transform: rotate(360deg);
  }
}

.recipe-card__error {
  display: grid;
  gap: $spacing-sm;
  align-content: center;
  min-height: 220px;
  border: 1px dashed rgba(224, 82, 62, 0.22);
  border-radius: 8px;
  background: #fff1e9;
  padding: $spacing-lg;
  text-align: center;
  color: #c44b37;

  strong {
    font-size: 16px;
  }

  p {
    margin: 0;
    color: #856449;
    font-size: 14px;
  }
}

.recipe-card__retry {
  justify-self: center;
  border: 0;
  border-radius: 6px;
  background: #e96d3b;
  color: #fffaf0;
  height: 38px;
  padding: 0 22px;
  cursor: pointer;
  font-size: 14px;

  &:hover {
    opacity: 0.9;
  }
}

.recipe-card__empty {
  display: grid;
  place-items: center;
  min-height: 220px;
  border: 1px dashed rgba(121, 82, 45, 0.22);
  border-radius: 8px;
  background: #fffaf1;
  color: #8a6a50;
  text-align: center;
  font-size: 14px;
}

.recipe-card__body {
  display: grid;
  gap: $spacing-lg;
}

.recipe-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-sm;
  border-top: 1px solid rgba(121, 82, 45, 0.12);
  padding-top: $spacing-md;
}

.recipe-card__chat-btn,
.recipe-card__share-btn {
  border: 0;
  border-radius: 6px;
  color: #fffaf0;
  height: 42px;
  padding: 0 24px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 800;
}

.recipe-card__chat-btn {
  background: linear-gradient(135deg, #89a94f, #e6a23c);
  box-shadow: 0 14px 26px rgba(137, 169, 79, 0.22);
}

.recipe-card__share-btn {
  background: #d95249;
  box-shadow: 0 12px 22px rgba(217, 82, 73, 0.2);
}

.recipe-card__chat-btn:disabled {
  background: #eadfce;
  color: #ad947d;
  box-shadow: none;
  cursor: not-allowed;
}
</style>
