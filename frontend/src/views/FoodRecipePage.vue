<template>
  <main class="food-recipe-page">
    <section class="food-recipe-page__toolbar">
      <div>
        <h1>食物识别生成菜谱</h1>
        <p>上传 1 至 5 张图片、确认食材，再把确认快照交给菜谱模块。</p>
      </div>
      <div class="food-recipe-page__status" data-testid="workflow-state">
        {{ workflowState }}
      </div>
    </section>

    <section class="food-recipe-page__body">
      <aside class="food-recipe-page__left">
        <div class="food-recipe-page__panel">
          <header class="food-recipe-page__panel-header">
            <h2>图片</h2>
            <select v-model="mockScenario" aria-label="Mock response scenario" data-testid="mock-scenario">
              <option value="success">Mock 成功</option>
              <option value="empty">Mock 空识别</option>
              <option value="401">Mock 401</option>
              <option value="413">Mock 413</option>
              <option value="415">Mock 415</option>
              <option value="422">Mock 422</option>
              <option value="503">Mock 503</option>
            </select>
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
            开始识别
          </button>
        </div>

        <div class="food-recipe-page__panel">
          <h2>状态占位</h2>
          <ul class="food-recipe-page__state-list">
            <li v-for="state in visibleStates" :key="state.key" :class="{ active: state.key === visibleStateKey }">
              <strong>{{ state.title }}</strong>
              <span>{{ state.description }}</span>
            </li>
          </ul>
        </div>
      </aside>

      <section class="food-recipe-page__right">
        <div v-if="workflowState === 'idle'" class="food-recipe-page__empty" data-testid="idle-state">
          请选择 1 至 5 张食物图片。
        </div>

        <div v-else-if="workflowState === 'selecting'" class="food-recipe-page__empty" data-testid="selecting-state">
          {{ selectedImageText }}已准备好，可以开始识别。
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
            @generate-recipe="emitRecipeRequest"
          />
        </template>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  createFoodRecognition,
  confirmFoodIngredients,
  normalizeRecognitionId,
  unwrapFoodApiData,
} from '@/api/food'
import FoodImageUploader from '@/components/food/FoodImageUploader.vue'
import IngredientEditor from '@/components/food/IngredientEditor.vue'
import RecognitionSummary from '@/components/food/RecognitionSummary.vue'
import { mapCandidatesToEditableIngredients } from '@/components/food/ingredientEditorModel'

const emit = defineEmits(['confirmed', 'recipe-requested'])

const workflowState = ref('idle')
const selectedFiles = ref([])
const confThreshold = ref(0.25)
const mockScenario = ref('success')
const recognizedIngredients = ref([])
const confirmedIngredients = ref([])
const recognizedImageCount = ref(0)
const recognitionId = ref('')
const validationMessage = ref('')
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
  { key: '413', title: '413', description: '图片超过 10 MB。' },
  { key: '415', title: '415', description: '图片格式不支持。' },
  { key: '422', title: '422', description: '图片或参数校验失败。' },
  { key: '503', title: '503', description: '模型服务暂不可用。' },
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
const selectedImageText = computed(() => {
  const count = selectedFiles.value.length
  if (count <= 1) return '图片'
  return `${count} 张图片`
})

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
  if (status === 401) return '需要重新登录'
  if (status === 413) return '图片过大'
  if (status === 415) return '图片格式不支持'
  if (status === 422) return '请求校验失败'
  if (status === 503) return '识别服务不可用'
  return '识别失败'
}

function handleApiError(error) {
  const status = error?.response?.status || 503
  const message =
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    '识别暂时失败，请稍后重试。'

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
    handleApiError(new Error('识别结果缺少整数 recognition_id。'))
    return
  }

  recognitionId.value = nextRecognitionId
  recognitionMeta.value = {
    provider: payload.provider,
    modelVersion: payload.model_version,
  }
  recognizedIngredients.value = mapCandidatesToEditableIngredients(payload.ingredients || [])
  confirmedIngredients.value = []
  recognizedImageCount.value = payload.image_count || payload.images?.length || selectedFiles.value.length
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

function emitRecipeRequest(payload) {
  emit('recipe-requested', {
    recognition_id: normalizeRecognitionId(payload.recognition_id),
    confirmed_ingredients: payload.confirmed_ingredients,
  })
}
</script>

<style lang="scss" scoped>
.food-recipe-page {
  min-height: calc(100vh - #{$header-height});
  background: #f4f6f8;
  color: $text-primary;
}

.food-recipe-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-lg;
  padding: $spacing-lg $spacing-xl;
  border-bottom: 1px solid $border-color;
  background: #fff;

  h1 {
    margin: 0;
    font-size: 22px;
    font-weight: 650;
  }

  p {
    margin: $spacing-xs 0 0;
    color: $text-secondary;
    font-size: 14px;
  }
}

.food-recipe-page__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 112px;
  height: 34px;
  border-radius: 999px;
  background: #101828;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}

.food-recipe-page__body {
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: $spacing-lg;
  padding: $spacing-lg $spacing-xl;
}

.food-recipe-page__left,
.food-recipe-page__right {
  display: grid;
  align-content: start;
  gap: $spacing-lg;
}

.food-recipe-page__panel,
.food-recipe-page__right {
  border: 1px solid $border-color;
  border-radius: $border-radius-md;
  background: #fff;
  padding: $spacing-lg;
}

.food-recipe-page__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;
  margin-bottom: $spacing-md;

  h2 {
    margin: 0;
    font-size: 18px;
  }

  select {
    height: 34px;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-sm;
    padding: 0 $spacing-sm;
    color: $text-regular;
    background: #fff;
  }
}

.food-recipe-page__threshold {
  display: grid;
  gap: $spacing-xs;
  margin-top: $spacing-md;
  color: $text-secondary;
  font-size: 13px;

  input {
    height: 36px;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-sm;
    padding: 0 $spacing-sm;
    color: $text-primary;
  }
}

.food-recipe-page__primary {
  width: 100%;
  height: 40px;
  margin-top: $spacing-md;
  border: 1px solid $primary-color;
  border-radius: $border-radius-sm;
  background: $primary-color;
  color: #fff;
  cursor: pointer;

  &:disabled {
    border-color: $border-color-light;
    background: #f2f4f7;
    color: $text-placeholder;
    cursor: not-allowed;
  }
}

.food-recipe-page__state-list {
  display: grid;
  gap: $spacing-sm;
  margin: $spacing-md 0 0;
  padding: 0;
  list-style: none;

  li {
    display: grid;
    gap: $spacing-xs;
    border-left: 3px solid $border-color-light;
    padding: $spacing-sm $spacing-md;
    background: #fafafa;

    &.active {
      border-left-color: $primary-color;
      background: #eef6ff;
    }
  }

  strong {
    font-size: 13px;
  }

  span {
    color: $text-secondary;
    font-size: 12px;
  }
}

.food-recipe-page__right {
  min-height: 520px;
}

.food-recipe-page__empty,
.food-recipe-page__loading,
.food-recipe-page__error {
  display: grid;
  place-items: center;
  min-height: 220px;
  border: 1px dashed $border-color-light;
  border-radius: $border-radius-md;
  color: $text-secondary;
  text-align: center;
}

.food-recipe-page__loading {
  gap: $spacing-md;
}

.food-recipe-page__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #d9e8ff;
  border-top-color: $primary-color;
  border-radius: 50%;
  animation: food-spin 0.8s linear infinite;
}

.food-recipe-page__error {
  align-content: center;
  border-color: #ffd3cc;
  background: #fff7f6;
  color: $danger-color;

  p {
    max-width: 520px;
    margin: $spacing-sm 0 0;
  }
}

@keyframes food-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 960px) {
  .food-recipe-page__body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .food-recipe-page__toolbar {
    align-items: flex-start;
    flex-direction: column;
    padding: $spacing-lg;
  }

  .food-recipe-page__body {
    padding: $spacing-lg;
  }
}
</style>
