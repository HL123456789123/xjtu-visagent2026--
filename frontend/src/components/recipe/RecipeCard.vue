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
      <RecipeTitle :recipe="recipe" />

      <div class="recipe-card__body">
        <RecipeIngredients :ingredients="recipe.ingredients || []" />
        <RecipeSteps :steps="recipe.steps || []" />
        <NutritionPanel
          :nutrition="recipe.nutrition || {}"
          :disclaimer="recipe.nutrition_disclaimer || defaultDisclaimer"
        />
      </div>

      <footer v-if="showActions" class="recipe-card__actions">
        <button
          class="recipe-card__chat-btn"
          type="button"
          data-testid="recipe-open-chat"
          :disabled="!recipe.recipe_id"
          @click="emitOpenChat"
        >
          对话修改菜谱
        </button>
      </footer>
    </template>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import RecipeTitle from './RecipeTitle.vue'
import RecipeIngredients from './RecipeIngredients.vue'
import RecipeSteps from './RecipeSteps.vue'
import NutritionPanel from './NutritionPanel.vue'

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
})

const emit = defineEmits(['open-chat', 'retry'])

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
</script>

<style lang="scss" scoped>
.recipe-card {
  display: grid;
  gap: $spacing-lg;
  border: 1px solid $border-color;
  border-radius: $border-radius-md;
  background: $bg-color-white;
  padding: $spacing-lg;
}

.recipe-card__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: $spacing-md;
  min-height: 220px;
  justify-content: center;
  color: $text-secondary;

  p {
    margin: 0;
    font-size: 14px;
  }
}

.recipe-card__spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #d9e8ff;
  border-top-color: $primary-color;
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
  border: 1px dashed #ffd3cc;
  border-radius: $border-radius-md;
  background: #fff7f6;
  padding: $spacing-lg;
  text-align: center;
  color: $danger-color;

  strong {
    font-size: 16px;
  }

  p {
    margin: 0;
    color: $text-secondary;
    font-size: 14px;
  }
}

.recipe-card__retry {
  justify-self: center;
  border: 1px solid $primary-color;
  border-radius: $border-radius-sm;
  background: $primary-color;
  color: #fff;
  height: 36px;
  padding: 0 $spacing-lg;
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
  border: 1px dashed $border-color-light;
  border-radius: $border-radius-md;
  color: $text-secondary;
  text-align: center;
  font-size: 14px;
}

.recipe-card__body {
  display: grid;
  gap: $spacing-lg;
}

.recipe-card__actions {
  border-top: 1px solid $border-color;
  padding-top: $spacing-md;
}

.recipe-card__chat-btn {
  border: 1px solid $success-color;
  border-radius: $border-radius-sm;
  background: $success-color;
  color: #fff;
  height: 38px;
  padding: 0 $spacing-xl;
  cursor: pointer;
  font-size: 14px;

  &:disabled {
    border-color: $border-color-light;
    background: #f2f4f7;
    color: $text-placeholder;
    cursor: not-allowed;
  }
}
</style>
