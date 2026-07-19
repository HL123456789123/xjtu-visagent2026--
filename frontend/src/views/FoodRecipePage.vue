<template>
  <main class="food-recipe-page">
    <div class="food-recipe-page__toolbar">
      <div class="food-recipe-page__steps">
        <div
          v-for="step in workflowSteps"
          :key="step.key"
          class="food-recipe-page__step"
          :class="{ active: step.activeStates.includes(workflowState) }"
        >
          <span>{{ step.no }}</span>
          <strong>{{ step.title }}</strong>
        </div>
        <div class="food-recipe-page__steps-line"></div>
      </div>
      <select v-model="mockScenario" aria-label="Mock response scenario" data-testid="mock-scenario">
        <option value="off">后端 Mock API</option>
        <option value="success">前端 Mock 成功</option>
        <option value="empty">前端 Mock 空识别</option>
        <option value="401">前端 Mock 401</option>
        <option value="413">前端 Mock 413</option>
        <option value="415">前端 Mock 415</option>
        <option value="422">前端 Mock 422</option>
        <option value="503">前端 Mock 503</option>
        <option value="network">前端 Mock 网络失败</option>
      </select>
      <span class="food-recipe-page__state-badge" data-testid="workflow-state">
        {{ workflowState }}
      </span>
    </div>

    <section class="food-recipe-page__body">
      <aside class="food-recipe-page__left">
        <div id="upload-panel" class="food-recipe-page__panel food-recipe-page__panel--upload">
          <header class="food-recipe-page__panel-header">
            <div>
              <span>Step 01</span>
              <h2>上传食物照片</h2>
            </div>
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

        <div class="food-recipe-page__panel food-recipe-page__panel--guide">
          <span class="food-recipe-page__panel-kicker">小厨房流程</span>
          <ul class="food-recipe-page__step-list">
            <li v-for="step in workflowSteps" :key="step.key" :class="{ active: step.activeStates.includes(workflowState) }">
              <span>{{ step.no }}</span>
              <div>
                <strong>{{ step.title }}</strong>
                <small>{{ step.description }}</small>
              </div>
            </li>
          </ul>
          <p class="food-recipe-page__tip">如果识别不完整，可以手动补充食材，适合冰箱清库存和日常备餐。</p>
        </div>
      </aside>

      <section class="food-recipe-page__right">
        <div v-if="workflowState === 'idle'" class="food-recipe-page__empty" data-testid="idle-state">
          <strong>今天想用什么食材做饭？</strong>
          <span>先选择 1 至 5 张食物图片，系统会帮你整理候选食材。</span>
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
            @validation-error="handleIngredientValidation"
          />

          <RecognitionSummary
            :recognition-id="recognitionId"
            :confirmed-ingredients="confirmedIngredients"
            :status="workflowState"
            :provider="recognitionMeta.provider"
            :model-version="recognitionMeta.modelVersion"
            :image-count="recognizedImageCount"
            :source-image-names="selectedImageNames"
            @generate-recipe="generateRecipeFromRecognition"
          />

          <section
            v-if="showRecipeFlow"
            class="food-recipe-page__recipe-flow"
            data-testid="recipe-flow"
          >
            <header class="food-recipe-page__recipe-header">
              <div>
                <span>Recipe Flow</span>
                <h2>菜谱生成结果</h2>
              </div>
              <strong data-testid="recipe-flow-recognition-id">
                recognition_id: {{ recognitionId }}
              </strong>
            </header>

            <div class="food-recipe-page__preferences" data-testid="recipe-preferences">
              <label>
                <span>份数</span>
                <input
                  v-model.number="recipePreferences.servings"
                  type="number"
                  min="1"
                  max="10"
                  :disabled="recipeLoading"
                />
              </label>
              <label>
                <span>口味</span>
                <input
                  v-model.trim="recipePreferences.taste"
                  type="text"
                  maxlength="20"
                  :disabled="recipeLoading"
                />
              </label>
              <label>
                <span>最长时间</span>
                <input
                  v-model.number="recipePreferences.max_time_minutes"
                  type="number"
                  min="5"
                  max="180"
                  :disabled="recipeLoading"
                />
              </label>
              <label>
                <span>忌口</span>
                <input
                  v-model.trim="avoidIngredientsText"
                  type="text"
                  placeholder="例如：香菜, 辣椒"
                  :disabled="recipeLoading"
                />
              </label>
            </div>

            <RecipeCard
              :recipe="generatedRecipe"
              :loading="recipeLoading"
              :error="recipeError"
              :show-actions="false"
              @retry="generateRecipeFromRecognition"
            />
            <ChatPage
              v-if="generatedRecipe?.recipe_id"
              :recipe-id="generatedRecipe.recipe_id"
              @recipe-updated="refreshGeneratedRecipe"
            />
          </section>
        </template>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  createFoodRecognition,
  confirmFoodIngredients,
  getFoodRecognition,
  normalizeRecognitionId,
  unwrapFoodApiData,
} from '@/api/food'
import FoodImageUploader from '@/components/food/FoodImageUploader.vue'
import IngredientEditor from '@/components/food/IngredientEditor.vue'
import RecognitionSummary from '@/components/food/RecognitionSummary.vue'
import RecipeCard from '@/components/recipe/RecipeCard.vue'
import ChatPage from '@/views/ChatPage.vue'
import { mapCandidatesToEditableIngredients } from '@/components/food/ingredientEditorModel'
import { createRecipe, getRecipe, unwrapRecipeApiData } from '@/api/recipe'

const props = defineProps({
  recipeId: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['confirmed', 'recipe-requested'])

const workflowState = ref('idle')
const selectedFiles = ref([])
const confThreshold = ref(0.25)
const mockScenario = ref('off')
const recognizedIngredients = ref([])
const confirmedIngredients = ref([])
const recognizedImageCount = ref(0)
const recognitionId = ref('')
const validationMessage = ref('')
const generatedRecipe = ref(null)
const recipeLoading = ref(false)
const recipeError = ref(null)
const avoidIngredientsText = ref('')
const recipePreferences = ref({
  servings: 2,
  taste: '家常',
  max_time_minutes: 30,
  avoid_ingredients: [],
})
const errorState = ref({
  status: null,
  title: '',
  message: '',
})
const recognitionMeta = ref({
  provider: '',
  modelVersion: '',
})

const visibleStates = [
  { key: 'loading', title: 'Loading', description: '上传和识别处理中。' },
  { key: 'empty', title: '空识别', description: '识别成功但无候选食材。' },
  { key: '401', title: '401', description: '登录失效或未登录。' },
  { key: '413', title: '413', description: '图片超过大小限制。' },
  { key: '415', title: '415', description: '图片格式不支持。' },
  { key: '422', title: '422', description: '图片或参数校验失败。' },
  { key: '503', title: '503', description: '模型服务暂不可用。' },
]

const workflowSteps = [
  {
    key: 'upload',
    no: '01',
    title: '上传图片',
    description: '支持单张或多张 JPG / PNG。',
    activeStates: ['idle', 'selecting', 'uploading'],
  },
  {
    key: 'recognize',
    no: '02',
    title: '确认食材',
    description: '检查识别结果，也可以手动新增。',
    activeStates: ['recognized'],
  },
  {
    key: 'recipe',
    no: '03',
    title: '生成菜谱',
    description: '把确认食材交给菜谱模块。',
    activeStates: ['confirmed'],
  },
]

const visibleStateKey = computed(() => {
  if (workflowState.value === 'uploading' || workflowState.value === 'confirming') return 'loading'
  if (workflowState.value === 'recognized' && recognizedIngredients.value.length === 0) return 'empty'
  if (workflowState.value === 'error') return String(errorState.value.status || '503')
  return ''
})

const isBusy = computed(() => workflowState.value === 'uploading' || workflowState.value === 'confirming')
const busyText = computed(() => (workflowState.value === 'confirming' ? '正在确认食材...' : '正在识别食材...'))
const selectedImageNames = computed(() => selectedFiles.value.map((file) => file.name))
const showRecipeFlow = computed(
  () => workflowState.value === 'confirmed' || recipeLoading.value || generatedRecipe.value || recipeError.value
)
const selectedImageText = computed(() => {
  const count = selectedFiles.value.length
  if (count <= 1) return '图片'
  return `${count} 张图片`
})

function resetRecipeFlow() {
  generatedRecipe.value = null
  recipeError.value = null
  recipeLoading.value = false
}

function handleFileSelected() {
  workflowState.value = 'selecting'
  resetRecognition()
}

function resetRecognition() {
  recognizedIngredients.value = []
  confirmedIngredients.value = []
  recognizedImageCount.value = 0
  recognitionId.value = ''
  validationMessage.value = ''
  errorState.value = { status: null, title: '', message: '' }
  recognitionMeta.value = { provider: '', modelVersion: '' }
  resetRecipeFlow()
  if (selectedFiles.value.length === 0) workflowState.value = 'idle'
}

function setValidationError(message) {
  validationMessage.value = message
  errorState.value = {
    status: 422,
    title: '图片校验失败',
    message,
  }
  workflowState.value = 'error'
}

function getErrorTitle(status) {
  if (status === 0) return '网络连接失败'
  if (status === 401) return '需要重新登录'
  if (status === 413) return '图片过大'
  if (status === 415) return '图片格式不支持'
  if (status === 422) return '请求校验失败'
  if (status === 503) return '识别服务不可用'
  return '识别失败'
}

function handleApiError(error) {
  const status = error?.response?.status ?? 0
  const message =
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    '网络连接失败，请检查后端服务。'

  errorState.value = {
    status,
    title: getErrorTitle(status),
    message,
  }
  workflowState.value = 'error'
}

function applyRecognitionResult(response) {
  const payload = unwrapFoodApiData(response)
  const nextRecognitionId = normalizeRecognitionId(payload.recognition_id)
  if (!nextRecognitionId) {
    handleApiError({
      response: {
        status: 422,
        data: { message: '识别结果缺少整数 recognition_id。' },
      },
    })
    return
  }

  recognitionId.value = nextRecognitionId
  recognitionMeta.value = {
    provider: payload.provider,
    modelVersion: payload.model_version,
  }
  recognizedIngredients.value = mapCandidatesToEditableIngredients(payload.ingredients || [])
  confirmedIngredients.value = []
  resetRecipeFlow()
  recognizedImageCount.value = payload.images?.length || selectedFiles.value.length
  workflowState.value = 'recognized'
}

async function startRecognition() {
  if (selectedFiles.value.length === 0) {
    setValidationError('请先选择 1 至 5 张 JPG/PNG 图片。')
    return
  }

  workflowState.value = 'uploading'
  errorState.value = { status: null, title: '', message: '' }

  try {
    const response = await createFoodRecognition(
      {
        images: selectedFiles.value,
        conf_threshold: confThreshold.value,
      },
      { mockScenario: mockScenario.value }
    )
    applyRecognitionResult(response)
  } catch (error) {
    handleApiError(error)
  }
}

async function handleConfirm(ingredients) {
  if (!recognitionId.value) return

  workflowState.value = 'confirming'
  errorState.value = { status: null, title: '', message: '' }

  try {
    const response = await confirmFoodIngredients(recognitionId.value, ingredients, {
      mockScenario: mockScenario.value,
    })
    const payload = unwrapFoodApiData(response)
    const confirmedRecognitionId = normalizeRecognitionId(payload.recognition_id) || recognitionId.value
    const confirmed = payload.confirmed_ingredients || ingredients

    recognitionId.value = confirmedRecognitionId
    confirmedIngredients.value = confirmed
    workflowState.value = 'confirmed'
    resetRecipeFlow()

    emit('confirmed', {
      recognition_id: confirmedRecognitionId,
      confirmed_ingredients: confirmed,
    })
  } catch (error) {
    handleApiError(error)
  }
}

function handleIngredientValidation(errors) {
  validationMessage.value = errors[0] || ''
}

function buildRecipePreferences() {
  const avoidIngredients = avoidIngredientsText.value
    .split(/[,，、\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)

  return {
    servings: Number(recipePreferences.value.servings) || 2,
    taste: recipePreferences.value.taste || '家常',
    max_time_minutes: recipePreferences.value.max_time_minutes || null,
    avoid_ingredients: avoidIngredients,
  }
}

function resolveRecipeMockScenario() {
  return mockScenario.value === 'off' ? 'off' : 'success'
}

function normalizeRecipeError(error) {
  const status = error?.response?.status ?? 0
  return {
    status,
    code: error?.response?.data?.code || (status === 0 ? 'NETWORK_ERROR' : undefined),
    message:
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      error?.message ||
      '菜谱生成失败，请稍后重试。',
  }
}

async function generateRecipeFromRecognition(payload = {}) {
  const nextRecognitionId = normalizeRecognitionId(payload.recognition_id ?? recognitionId.value)
  if (!nextRecognitionId) {
    recipeError.value = {
      status: 422,
      code: 'BAD_REQUEST',
      message: '缺少有效的 recognition_id，无法生成菜谱。',
    }
    return
  }

  const preferences = buildRecipePreferences()
  recipeLoading.value = true
  recipeError.value = null

  try {
    const response = await createRecipe(
      {
        recognition_id: nextRecognitionId,
        preferences,
      },
      { mockScenario: resolveRecipeMockScenario() }
    )
    const recipe = unwrapRecipeApiData(response)
    generatedRecipe.value = recipe
    emit('recipe-requested', {
      recognition_id: nextRecognitionId,
      preferences,
      recipe_id: recipe?.recipe_id,
      confirmed_ingredients: payload.confirmed_ingredients || confirmedIngredients.value,
    })
  } catch (error) {
    recipeError.value = normalizeRecipeError(error)
  } finally {
    recipeLoading.value = false
  }
}

async function refreshGeneratedRecipe(payload = {}) {
  const recipeId = Number(payload.recipe_id ?? generatedRecipe.value?.recipe_id)
  if (!Number.isInteger(recipeId) || recipeId <= 0) return

  recipeLoading.value = true
  recipeError.value = null
  try {
    const response = await getRecipe(recipeId, {
      mockScenario: mockScenario.value === 'off' ? 'off' : 'v2',
    })
    generatedRecipe.value = unwrapRecipeApiData(response)
  } catch (error) {
    recipeError.value = normalizeRecipeError(error)
  } finally {
    recipeLoading.value = false
  }
}

async function restoreRecipe(recipeId) {
  if (!Number.isInteger(recipeId) || recipeId <= 0) return

  recipeLoading.value = true
  recipeError.value = null
  try {
    const recipeResponse = await getRecipe(recipeId)
    const recipe = unwrapRecipeApiData(recipeResponse)
    const recognitionResponse = await getFoodRecognition(recipe.recognition_id)
    const recognition = unwrapFoodApiData(recognitionResponse)

    recognitionId.value = recognition.recognition_id
    recognitionMeta.value = {
      provider: recognition.provider,
      modelVersion: recognition.model_version,
    }
    const restoredConfirmedIngredients = recognition.confirmed_ingredients || []
    recognizedIngredients.value = mapCandidatesToEditableIngredients(
      restoredConfirmedIngredients.length ? restoredConfirmedIngredients : recognition.ingredients || []
    )
    confirmedIngredients.value = restoredConfirmedIngredients
    recognizedImageCount.value = recognition.images?.length || 0
    selectedFiles.value = []
    generatedRecipe.value = recipe
    workflowState.value = 'confirmed'
  } catch (error) {
    recipeError.value = normalizeRecipeError(error)
    workflowState.value = 'error'
  } finally {
    recipeLoading.value = false
  }
}

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

/* ---- 顶部步骤条 ---- */
.food-recipe-page__toolbar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px clamp(18px, 4vw, 72px);
  border-bottom: 1px solid rgba(121, 82, 45, 0.08);
}

.food-recipe-page__steps {
  display: flex;
  align-items: center;
  gap: 0;
  position: relative;
}

.food-recipe-page__step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  border-radius: 999px;
  position: relative;
  z-index: 1;
  transition: background-color 0.25s ease;

  &.active {
    background: rgba(255, 241, 210, 0.8);

    span {
      background: #e96d3b;
      color: #fffaf0;
    }

    strong {
      color: #d76626;
    }
  }

  span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #f7db9a;
    color: #7c4c20;
    font-size: 11px;
    font-weight: 900;
    transition: background-color 0.25s ease, color 0.25s ease;
  }

  strong {
    font-size: 14px;
    font-weight: 700;
    color: #8a6a50;
    transition: color 0.25s ease;
  }
}

.food-recipe-page__steps-line {
  position: absolute;
  top: 50%;
  left: 40px;
  right: 40px;
  height: 2px;
  background: rgba(121, 82, 45, 0.12);
  transform: translateY(-50%);
  z-index: 0;
  border-radius: 1px;
}

.food-recipe-page__toolbar select {
  height: 34px;
  border: 1px solid rgba(121, 82, 45, 0.16);
  border-radius: 999px;
  padding: 0 12px;
  color: #6f5038;
  background: rgba(255, 255, 255, 0.78);
  font-size: 13px;
}

.food-recipe-page__state-badge {
  display: none;
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

.food-recipe-page__eyebrow,
.food-recipe-page__panel-kicker,
.food-recipe-page__panel-header span {
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

/* ---- 引导面板 ---- */
.food-recipe-page__panel--guide {
  h2 {
    display: none;
  }
}

.food-recipe-page__step-list {
  display: grid;
  gap: 8px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    border: 1px solid rgba(121, 82, 45, 0.1);
    border-radius: 16px;
    padding: 10px 12px;
    background: rgba(255, 252, 245, 0.72);
    transition: transform 0.2s ease, background-color 0.2s ease;

    &.active {
      transform: translateX(3px);
      border-color: rgba(233, 109, 59, 0.28);
      background: #fff1d2;

      > span {
        background: #e96d3b;
        color: #fffaf0;
      }
    }
  }

  li > span {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #f7db9a;
    color: #7c4c20;
    font-size: 11px;
    font-weight: 900;
  }

  strong {
    display: block;
    color: #3a2a1d;
    font-size: 13px;
  }

  small {
    display: block;
    margin-top: 2px;
    color: #8a6a50;
    font-size: 11px;
    line-height: 1.5;
  }
}

.food-recipe-page__tip {
  margin: 10px 0 0;
  border-radius: 14px;
  background: rgba(131, 170, 83, 0.12);
  color: #6b7040;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.6;
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

.food-recipe-page__recipe-flow {
  display: grid;
  gap: 18px;
  margin-top: 6px;
  border-top: 1px solid rgba(121, 82, 45, 0.12);
  padding-top: 24px;
}

.food-recipe-page__recipe-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;

  span {
    color: #7b8c37;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  h2 {
    margin: 4px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 24px;
    font-weight: 500;
  }

  strong {
    border-radius: 999px;
    background: #eff8d6;
    color: #62772b;
    padding: 8px 14px;
    font-size: 13px;
  }
}

.food-recipe-page__preferences {
  display: grid;
  grid-template-columns: 90px minmax(120px, 0.8fr) 110px minmax(160px, 1fr);
  gap: $spacing-md;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 22px;
  background: rgba(255, 250, 241, 0.82);
  padding: 14px;

  label {
    display: grid;
    gap: $spacing-xs;
    color: #8a6a50;
    font-size: 12px;
  }

  input {
    width: 100%;
    height: 38px;
    box-sizing: border-box;
    border: 1px solid rgba(121, 82, 45, 0.16);
    border-radius: 14px;
    padding: 0 12px;
    color: #3a2a1d;
    background: #fffefa;

    &:disabled {
      color: #ad947d;
      background: #f6efe4;
    }

    &:focus {
      border-color: #89a94f;
      box-shadow: 0 0 0 3px rgba(137, 169, 79, 0.14);
      outline: none;
    }
  }
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

  .food-recipe-page__preferences {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .food-recipe-page__body {
    padding: 0 14px 20px;
  }

  .food-recipe-page__panel-header,
  .food-recipe-page__recipe-header {
    align-items: stretch;
    flex-direction: column;
  }

  .food-recipe-page__toolbar {
    padding: 10px 14px;
  }

  .food-recipe-page__preferences {
    grid-template-columns: 1fr;
  }
}
</style>
