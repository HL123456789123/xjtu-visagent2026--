<template>
  <main class="food-recipe-page">
    <FoodWorkflowHeader :workflow-state="workflowState" />

    <section class="food-recipe-page__body">
      <aside class="food-recipe-page__left">
        <div id="upload-panel" class="food-recipe-page__panel food-recipe-page__panel--upload">
          <header class="food-recipe-page__panel-header">
            <h2>上传食物照片</h2>
          </header>

          <FoodImageUploader
            v-model="selectedFiles"
            :disabled="isBusy"
            @selected="handleFileSelected"
            @cleared="resetRecognition"
            @validation-error="setValidationError"
          />

          <label class="food-recipe-page__threshold">
            <span>置信度阈值</span>
            <input v-model.number="confThreshold" type="number" min="0.1" max="1" step="0.05" />
          </label>

          <button
            class="food-recipe-page__primary"
            type="button"
            data-testid="start-recognition"
            :disabled="selectedFiles.length === 0 || isBusy"
            @click="startRecognition"
          >
            {{ workflowState === 'uploading' ? '正在识别...' : '开始识别食材' }}
          </button>
        </div>

      </aside>

      <section class="food-recipe-page__right">
        <div v-if="workflowState === 'idle'" class="food-recipe-page__empty" data-testid="idle-state">
          <strong>今天想用什么食材做饭？</strong>
          <span>先选择 1 至 8 张食物图片，系统会帮你整理候选食材。</span>
        </div>

        <div v-else-if="workflowState === 'selecting'" class="food-recipe-page__empty" data-testid="selecting-state">
          <strong>{{ selectedImageText }}已准备好</strong>
          <span>点击左侧按钮开始识别，稍后可以逐项确认或补充食材。</span>
        </div>

        <div
          v-else-if="workflowState === 'uploading' || workflowState === 'confirming'"
          class="food-recipe-page__loading"
          data-testid="loading-state"
        >
          <span class="food-recipe-page__spinner"></span>
          {{ busyText }}
        </div>

        <div v-else-if="workflowState === 'error'" class="food-recipe-page__error" data-testid="error-state">
          <strong>{{ errorState.title }}</strong>
          <p>{{ errorState.message }}</p>
        </div>

        <template v-else>
          <div v-if="recognizedIngredients.length === 0" class="food-recipe-page__empty" data-testid="empty-state">
            未识别到食材，可手动新增后确认。
          </div>

          <IngredientEditor
            v-model="recognizedIngredients"
            :disabled="workflowState === 'confirmed' || workflowState === 'confirming'"
            @confirm="handleConfirm"
          />

          <p v-if="recognitionMeta.task === 'classify'" class="food-recipe-page__mode-note">
            当前为整图分类模式，每张图片识别一个主要食材。多食材照片请联系管理员切换检测模型。
          </p>

          <RecognitionSummary
            :recognition-id="recognitionId"
            :confirmed-ingredients="confirmedIngredients"
            :status="workflowState"
            @generate-recipe="generateRecipeFromRecognition"
          />

          <RecipeWorkspace
            v-if="showRecipeFlow"
            v-model:preferences="recipePreferences"
            v-model:avoid-ingredients-text="avoidIngredientsText"
            :recipe="generatedRecipe"
            :loading="recipeLoading"
            :error="recipeError"
            :versions="recipeVersions"
            :current-version="currentRecipeVersion"
            :selected-version="selectedRecipeVersion"
            :version-loading="versionLoading"
            :version-error="versionError"
            :is-historical-version="isViewingHistoricalVersion"
            @retry="generateRecipeFromRecognition"
            @version-change="selectRecipeVersion"
            @recipe-updated="refreshGeneratedRecipe"
          />
        </template>
      </section>
    </section>
  </main>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import FoodImageUploader from '@/components/food/FoodImageUploader.vue'
import FoodWorkflowHeader from '@/components/food/FoodWorkflowHeader.vue'
import IngredientEditor from '@/components/food/IngredientEditor.vue'
import RecognitionSummary from '@/components/food/RecognitionSummary.vue'
import RecipeWorkspace from '@/components/recipe/RecipeWorkspace.vue'
import { useFoodRecognitionWorkflow } from '@/composables/useFoodRecognitionWorkflow'
import { useRecipeWorkflow } from '@/composables/useRecipeWorkflow'

const props = defineProps({
  recipeId: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['confirmed', 'recipe-requested'])

let recipeWorkflow

const {
  workflowState,
  selectedFiles,
  confThreshold,
  recognizedIngredients,
  confirmedIngredients,
  recognitionId,
  errorState,
  recognitionMeta,
  isBusy,
  busyText,
  selectedImageText,
  handleConfirm,
  handleFileSelected,
  resetRecognition,
  restoreRecipe: restoreRecognitionForRecipe,
  setValidationError,
  startRecognition,
} = useFoodRecognitionWorkflow({
  resetRecipeFlow: () => recipeWorkflow?.resetRecipeFlow(),
  onConfirmed: (payload) => emit('confirmed', payload),
})

recipeWorkflow = useRecipeWorkflow({
  workflowState,
  recognitionId,
  confirmedIngredients,
  restoreRecognitionForRecipe,
  onRecipeRequested: (payload) => emit('recipe-requested', payload),
  onRestoreError: () => {
    workflowState.value = 'error'
  },
})

const {
  generatedRecipe,
  recipeLoading,
  recipeError,
  recipeVersions,
  currentRecipeVersion,
  selectedRecipeVersion,
  versionLoading,
  versionError,
  avoidIngredientsText,
  recipePreferences,
  showRecipeFlow,
  isViewingHistoricalVersion,
  generateRecipeFromRecognition,
  refreshGeneratedRecipe,
  restoreRecipe,
  selectRecipeVersion,
} = recipeWorkflow

watch(
  () => props.recipeId,
  (recipeId) => {
    if (recipeId) restoreRecipe(recipeId)
  },
)

onMounted(() => {
  if (props.recipeId) restoreRecipe(props.recipeId)
})
</script>

<style lang="scss" scoped>
.food-recipe-page {
  height: calc(100vh - #{$header-height});
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 12% 10%, rgba(255, 213, 118, 0.42), transparent 28%),
    radial-gradient(circle at 84% 4%, rgba(145, 184, 102, 0.22), transparent 24%),
    linear-gradient(180deg, #fff8ea 0%, #fffdf7 42%, #f8efe3 100%);
  color: #3a2a1d;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
  position: relative;

  &::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.38;
    background-image:
      linear-gradient(rgba(125, 86, 36, 0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(125, 86, 36, 0.035) 1px, transparent 1px);
    background-size: 34px 34px;
  }
}

/* ---- 主体双栏 ---- */
.food-recipe-page__body {
  position: relative;
  z-index: 1;
  flex: 1;
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: clamp(14px, 2.5vw, 28px);
  padding: clamp(12px, 2vw, 24px) clamp(18px, 4vw, 72px) clamp(12px, 2vw, 24px);
  overflow-y: auto;
  min-height: 0;
}

.food-recipe-page__left {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.food-recipe-page__right {
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 251, 241, 0.9)),
    radial-gradient(circle at 100% 0, rgba(243, 178, 91, 0.22), transparent 34%);
  box-shadow: 0 20px 56px rgba(102, 68, 35, 0.1);
  backdrop-filter: blur(18px);
  padding: clamp(14px, 2vw, 24px);
  overflow-y: auto;
}

/* ---- 面板 ---- */
.food-recipe-page__panel {
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 16px 50px rgba(102, 68, 35, 0.1);
  backdrop-filter: blur(18px);
  padding: clamp(14px, 2vw, 22px);
}

.food-recipe-page__panel--upload {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(255, 248, 230, 0.84)),
    radial-gradient(circle at 0 0, rgba(255, 202, 97, 0.32), transparent 42%);
}

.food-recipe-page__eyebrow {
  color: #b56a26;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.food-recipe-page__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-sm;
  margin-bottom: $spacing-sm;

  h2 {
    margin: 3px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 20px;
    font-weight: 500;
  }
}

.food-recipe-page__threshold {
  display: grid;
  gap: 4px;
  margin-top: 12px;
  color: #856449;
  font-size: 12px;

  input {
    height: 36px;
    border: 1px solid rgba(121, 82, 45, 0.16);
    border-radius: 12px;
    padding: 0 12px;
    color: #3a2a1d;
    background: rgba(255, 255, 255, 0.82);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
  }
}

.food-recipe-page__primary {
  width: 100%;
  height: 42px;
  margin-top: 12px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  color: #fffaf0;
  cursor: pointer;
  font-weight: 800;
  font-size: 14px;
  letter-spacing: 0.04em;
  box-shadow: 0 12px 28px rgba(229, 104, 52, 0.24);
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 16px 36px rgba(229, 104, 52, 0.3);
  }

  &:disabled {
    background: #eadfce;
    color: #ad947d;
    box-shadow: none;
    cursor: not-allowed;
  }
}

/* ---- 状态占位 ---- */
.food-recipe-page__empty,
.food-recipe-page__loading,
.food-recipe-page__error {
  display: grid;
  place-items: center;
  gap: 6px;
  min-height: 180px;
  border: 1px dashed rgba(121, 82, 45, 0.22);
  border-radius: 20px;
  background:
    radial-gradient(circle at 50% 25%, rgba(255, 218, 132, 0.28), transparent 32%),
    rgba(255, 252, 244, 0.58);
  color: #8a6a50;
  text-align: center;

  strong {
    color: #3a2a1d;
    font-size: 16px;
  }

  span {
    max-width: 400px;
    line-height: 1.6;
    font-size: 13px;
  }
}

.food-recipe-page__loading {
  gap: $spacing-sm;
}

.food-recipe-page__spinner {
  width: 30px;
  height: 30px;
  border: 3px solid #ffe0a1;
  border-top-color: #e96d3b;
  border-radius: 50%;
  animation: food-spin 0.8s linear infinite;
}

.food-recipe-page__error {
  align-content: center;
  border-color: rgba(224, 82, 62, 0.22);
  background: #fff1e9;
  color: #c44b37;

  p {
    max-width: 420px;
    margin: $spacing-xs 0 0;
    font-size: 13px;
  }
}

.food-recipe-page__mode-note {
  margin: 12px 0 0;
  border-left: 3px solid #d99a2b;
  background: #fff6df;
  color: #765b36;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
}

@keyframes food-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ---- 响应式 ---- */
@media (max-width: 960px) {
  .food-recipe-page__body {
    grid-template-columns: 1fr;
  }

  .food-recipe-page {
    height: auto;
    min-height: calc(100vh - #{$header-height});
  }

}

@media (max-width: 640px) {
  .food-recipe-page__body {
    padding: 0 14px 20px;
  }

  .food-recipe-page__panel-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
