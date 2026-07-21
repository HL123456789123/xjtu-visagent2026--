<template>
  <main class="food-recipe-page">
    <FoodWorkflowHeader
      :workflow-state="workflowState"
      :active-stage="activeStage"
      :can-enter-recipe="canEnterRecipe"
      @stage-change="switchStage"
    />

    <section
      v-show="activeStage === 'recognize'"
      class="food-recipe-page__stage food-recipe-page__stage--recognize"
      data-testid="recognition-stage"
    >
      <aside class="food-recipe-page__left">
        <div id="upload-panel" class="food-recipe-page__panel food-recipe-page__panel--upload">
          <header class="food-recipe-page__panel-header">
            <h2>选择食材图片</h2>
          </header>

          <FoodImageUploader
            v-model="selectedFiles"
            :disabled="isBusy"
            @selected="handleNewFilesSelected"
            @cleared="handleRecognitionCleared"
            @validation-error="setValidationError"
          />

          <label class="food-recipe-page__threshold">
            <span>识别置信度</span>
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
          <span>选择 1 至 8 张食物图片，系统会帮你整理候选食材。</span>
        </div>

        <div v-else-if="workflowState === 'selecting'" class="food-recipe-page__empty" data-testid="selecting-state">
          <strong>{{ selectedImageText }}已准备好</strong>
          <span>开始识别后，可以逐项确认或补充食材。</span>
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
            :images="recognitionImages"
            @confirm="handleConfirm"
          />

          <p v-if="recognitionMeta.task === 'classify'" class="food-recipe-page__mode-note">
            当前为整图分类模式，每张图片识别一个主要食材。多食材照片需要使用检测模型。
          </p>
        </template>
      </section>
    </section>

    <section
      v-show="activeStage === 'recipe'"
      class="food-recipe-page__stage food-recipe-page__stage--recipe"
      data-testid="recipe-stage"
    >
      <div class="food-recipe-page__recipe-scroll">
        <RecognitionSummary
          v-if="!generatedRecipe"
          :recognition-id="recognitionId"
          :confirmed-ingredients="confirmedIngredients"
          :status="workflowState"
          @generate-recipe="handleGenerateRecipe"
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
          @retry="handleGenerateRecipe"
          @version-change="selectRecipeVersion"
          @recipe-updated="refreshGeneratedRecipe"
        />
      </div>
    </section>

    <footer class="food-recipe-page__navigation" aria-label="流程切换">
      <button
        v-if="activeStage === 'recipe'"
        type="button"
        class="food-recipe-page__nav-button food-recipe-page__nav-button--secondary"
        data-testid="previous-stage"
        @click="switchStage('recognize')"
      >
        <el-icon><ArrowLeft /></el-icon>
        上一步
      </button>
      <span v-else></span>

      <button
        v-if="activeStage === 'recognize'"
        type="button"
        class="food-recipe-page__nav-button"
        data-testid="next-stage"
        :disabled="!canEnterRecipe"
        @click="switchStage('recipe')"
      >
        下一步
        <el-icon><ArrowRight /></el-icon>
      </button>
    </footer>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
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

const route = useRoute()
const router = useRouter()
const emit = defineEmits(['confirmed', 'recipe-requested'])
const activeStage = ref(props.recipeId ? 'recipe' : 'recognize')

let recipeWorkflow

const {
  workflowState,
  selectedFiles,
  confThreshold,
  recognizedIngredients,
  confirmedIngredients,
  recognitionImages,
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

const canEnterRecipe = computed(
  () => workflowState.value === 'confirmed' || Boolean(generatedRecipe.value),
)

function syncStageQuery(stage, { recipeId = null, clearRecipe = false } = {}) {
  const query = { ...route.query }
  if (stage === 'recipe') query.step = 'recipe'
  else delete query.step
  if (clearRecipe) delete query.recipe_id
  else if (Number.isInteger(Number(recipeId)) && Number(recipeId) > 0) {
    query.recipe_id = String(recipeId)
  }
  const navigation = router.replace({ query })
  navigation?.catch(() => {})
}

function switchStage(stage) {
  if (stage === 'recipe' && !canEnterRecipe.value) return
  activeStage.value = stage
  syncStageQuery(stage)
}

async function handleGenerateRecipe(payload) {
  switchStage('recipe')
  await generateRecipeFromRecognition(payload)
  syncStageQuery('recipe', { recipeId: generatedRecipe.value?.recipe_id })
}

function handleNewFilesSelected() {
  handleFileSelected()
  activeStage.value = 'recognize'
  syncStageQuery('recognize', { clearRecipe: true })
}

function handleRecognitionCleared() {
  resetRecognition()
  activeStage.value = 'recognize'
  syncStageQuery('recognize', { clearRecipe: true })
}

watch(
  () => props.recipeId,
  (recipeId) => {
    if (recipeId) {
      activeStage.value = 'recipe'
      syncStageQuery('recipe', { recipeId })
      restoreRecipe(recipeId)
    }
  },
)

watch(workflowState, (state) => {
  if (!['confirmed', 'confirming'].includes(state) && !generatedRecipe.value && activeStage.value === 'recipe') {
    switchStage('recognize')
  }
})

onMounted(() => {
  if (props.recipeId) {
    activeStage.value = 'recipe'
    syncStageQuery('recipe', { recipeId: props.recipeId })
    restoreRecipe(props.recipeId)
  }
})
</script>

<style lang="scss" scoped>
.food-recipe-page {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: #f7f3e9;
  color: #3a2a1d;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
}

.food-recipe-page__stage {
  flex: 1;
  min-height: 0;
}

.food-recipe-page__stage--recognize {
  display: grid;
  grid-template-columns: minmax(300px, 400px) minmax(0, 1fr);
  gap: 18px;
  padding: 18px clamp(18px, 4vw, 64px);
  overflow: hidden;
}

.food-recipe-page__left,
.food-recipe-page__right {
  min-height: 0;
  overflow-y: auto;
}

.food-recipe-page__right {
  border: 1px solid rgba(92, 82, 58, 0.16);
  border-radius: 8px;
  background: #fffdf8;
  padding: 22px;
}

.food-recipe-page__panel {
  border: 1px solid rgba(92, 82, 58, 0.16);
  border-radius: 8px;
  background: #fffdf8;
  padding: 20px;
}

.food-recipe-page__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;

  h2 {
    margin: 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 22px;
    font-weight: 600;
  }
}

.food-recipe-page__threshold {
  display: grid;
  gap: 5px;
  margin-top: 14px;
  color: #745d48;
  font-size: 12px;

  input {
    height: 38px;
    box-sizing: border-box;
    border: 1px solid rgba(92, 82, 58, 0.2);
    border-radius: 6px;
    padding: 0 12px;
    color: #3a2a1d;
    background: #fff;
  }
}

.food-recipe-page__primary,
.food-recipe-page__nav-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  border: 0;
  border-radius: 6px;
  background: #e96d3b;
  color: #fff;
  cursor: pointer;
  font: inherit;
  font-weight: 800;
  transition: background 0.2s ease, transform 0.2s ease;

  &:hover:not(:disabled) {
    background: #cb5528;
    transform: translateY(-1px);
  }

  &:disabled {
    background: #ded5c5;
    color: #9b8b78;
    cursor: not-allowed;
  }
}

.food-recipe-page__primary {
  width: 100%;
  margin-top: 14px;
}

.food-recipe-page__empty,
.food-recipe-page__loading,
.food-recipe-page__error {
  display: grid;
  min-height: 180px;
  place-items: center;
  align-content: center;
  gap: 7px;
  border: 1px dashed rgba(92, 82, 58, 0.24);
  border-radius: 8px;
  background: #faf6ed;
  color: #806a55;
  text-align: center;

  strong {
    color: #3a2a1d;
    font-size: 17px;
  }

  span {
    max-width: 420px;
    font-size: 13px;
    line-height: 1.6;
  }
}

.food-recipe-page__loading {
  gap: 10px;
}

.food-recipe-page__spinner {
  width: 30px;
  height: 30px;
  border: 3px solid #eadcae;
  border-top-color: #e96d3b;
  border-radius: 50%;
  animation: food-spin 0.8s linear infinite;
}

.food-recipe-page__error {
  border-color: rgba(196, 75, 55, 0.24);
  background: #fff1e9;
  color: #c44b37;

  p {
    max-width: 440px;
    margin: 0;
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

.food-recipe-page__stage--recipe {
  overflow: hidden;
}

.food-recipe-page__recipe-scroll {
  width: min(1240px, calc(100% - 36px));
  height: 100%;
  margin: 0 auto;
  box-sizing: border-box;
  overflow-y: auto;
  padding: 18px 0 28px;
}

.food-recipe-page__navigation {
  position: relative;
  z-index: 3;
  display: flex;
  min-height: 62px;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;
  border-top: 1px solid rgba(92, 82, 58, 0.14);
  background: #fffdf8;
  padding: 9px clamp(18px, 4vw, 64px);
}

.food-recipe-page__nav-button {
  min-width: 118px;
  padding: 0 18px;
}

.food-recipe-page__nav-button--secondary {
  border: 1px solid rgba(92, 82, 58, 0.22);
  background: #fff;
  color: #664c37;

  &:hover:not(:disabled) {
    background: #f4eddf;
  }
}

@keyframes food-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .food-recipe-page__stage--recognize {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }

  .food-recipe-page__left,
  .food-recipe-page__right {
    overflow: visible;
  }
}

@media (max-width: 640px) {
  .food-recipe-page__stage--recognize {
    gap: 12px;
    padding: 12px;
  }

  .food-recipe-page__right,
  .food-recipe-page__panel {
    padding: 14px;
  }

  .food-recipe-page__recipe-scroll {
    width: calc(100% - 24px);
    padding-top: 12px;
  }

  .food-recipe-page__navigation {
    min-height: 58px;
    padding: 8px 12px;
  }
}
</style>
