<template>
  <main class="food-recipe-page">
    <section class="food-recipe-page__hero">
      <div class="food-recipe-page__hero-copy">
        <span class="food-recipe-page__eyebrow">Daily kitchen assistant</span>
        <h1>拍下今天的餐桌，让它变成一份好做的家常食谱</h1>
        <p>上传 1 至 5 张食物图片，确认识别出的食材，再一键生成适合日常烹饪的菜谱。</p>
        <div class="food-recipe-page__hero-actions">
          <a href="#upload-panel">开始上传</a>
          <span>3 步完成：上传 · 确认 · 生成</span>
        </div>
      </div>
      <div class="food-recipe-page__hero-image">
        <img
          v-for="(slide, index) in carouselImages"
          :key="slide.src"
          class="food-recipe-page__slide"
          :class="{ active: currentSlide === index }"
          :src="slide.src"
          :alt="slide.alt"
        />
        <div class="food-recipe-page__image-note">
          <strong>营养美味，轻松上桌</strong>
          <span>{{ carouselImages[currentSlide].label }}</span>
        </div>
        <div class="food-recipe-page__status" data-testid="workflow-state">
          {{ workflowState }}
        </div>
        <div class="food-recipe-page__dots" role="tablist" aria-label="切换美食图片">
          <button
            v-for="(slide, index) in carouselImages"
            :key="slide.src + '-dot'"
            type="button"
            class="food-recipe-page__dot"
            :class="{ active: currentSlide === index }"
            :aria-label="`切换到第 ${index + 1} 张图片`"
            :aria-selected="currentSlide === index"
            role="tab"
            @click="goToSlide(index)"
          ></button>
        </div>
      </div>
    </section>

    <section class="food-recipe-page__body">
      <aside class="food-recipe-page__left">
        <div id="upload-panel" class="food-recipe-page__panel food-recipe-page__panel--upload">
          <header class="food-recipe-page__panel-header">
            <div>
              <span>Step 01</span>
              <h2>上传食物照片</h2>
            </div>
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
            {{ workflowState === 'uploading' ? '正在识别...' : '开始识别食材' }}
          </button>
        </div>

        <div class="food-recipe-page__panel food-recipe-page__panel--guide">
          <span class="food-recipe-page__panel-kicker">小厨房流程</span>
          <h2>从照片到菜谱</h2>
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
            @generate-recipe="emitRecipeRequest"
          />
        </template>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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

const currentSlide = ref(0)
let autoTimer = null

const carouselImages = [
  { src: '/food-carousel-1.jpg', alt: '家常热炒', label: '家常热炒 · 香气十足' },
  { src: '/food-carousel-2.jpg', alt: '清爽沙拉', label: '清爽沙拉 · 轻食时光' },
  { src: '/food-carousel-3.jpg', alt: '丰盛餐桌', label: '丰盛餐桌 · 每日灵感' },
]

function goToSlide(index) {
  currentSlide.value = index
  restartAutoPlay()
}

function nextSlide() {
  currentSlide.value = (currentSlide.value + 1) % carouselImages.length
}

function restartAutoPlay() {
  if (autoTimer) clearInterval(autoTimer)
  autoTimer = setInterval(nextSlide, 4200)
}

onMounted(() => {
  restartAutoPlay()
})

onBeforeUnmount(() => {
  if (autoTimer) clearInterval(autoTimer)
})

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
  overflow: hidden;
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

.food-recipe-page__hero,
.food-recipe-page__body {
  position: relative;
  z-index: 1;
}

.food-recipe-page__hero {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.72fr);
  align-items: center;
  gap: clamp(24px, 4vw, 56px);
  padding: clamp(36px, 6vw, 72px) clamp(24px, 5vw, 72px) clamp(30px, 4vw, 52px);
}

.food-recipe-page__hero-copy {
  max-width: 760px;

  h1 {
    max-width: 680px;
    margin: 12px 0 0;
    color: #2e2116;
    font-family: Georgia, "Songti SC", serif;
    font-size: clamp(34px, 5.8vw, 68px);
    font-weight: 500;
    line-height: 1.04;
    letter-spacing: -0.05em;
  }

  p {
    max-width: 560px;
    margin: 18px 0 0;
    color: #7a5940;
    font-size: 17px;
    line-height: 1.8;
  }
}

.food-recipe-page__eyebrow,
.food-recipe-page__panel-kicker,
.food-recipe-page__panel-header span {
  color: #b56a26;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.food-recipe-page__hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: $spacing-md;
  margin-top: 28px;

  a {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 46px;
    border: 1px solid #2e2116;
    border-radius: 999px;
    background: #2e2116;
    color: #fffaf0;
    padding: 0 24px;
    box-shadow: 0 14px 30px rgba(46, 33, 22, 0.18);
    font-size: 14px;
    font-weight: 700;
    text-decoration: none;
    transition: transform 0.2s ease, box-shadow 0.2s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 18px 36px rgba(46, 33, 22, 0.24);
    }
  }

  span {
    color: #8c6b4f;
    font-size: 13px;
  }
}

.food-recipe-page__hero-image {
  justify-self: center;
  width: min(460px, 88vw);
  min-height: 330px;
  overflow: hidden;
  border-radius: 42px;
  background: #fffaf1;
  box-shadow: 0 30px 80px rgba(82, 48, 24, 0.2);
  position: relative;

  &::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 1;
    background:
      linear-gradient(90deg, rgba(255, 248, 234, 0.04), rgba(255, 248, 234, 0.34)),
      radial-gradient(circle at 22% 20%, rgba(255, 255, 255, 0.36), transparent 28%);
  }
}

.food-recipe-page__slide {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 330px;
  display: block;
  object-fit: cover;
  opacity: 0;
  transform: scale(1.02);
  transition: opacity 0.9s ease, transform 4.5s ease-out;

  &.active {
    opacity: 1;
    transform: scale(1);
  }
}

.food-recipe-page__image-note {
  position: absolute;
  left: 24px;
  bottom: 24px;
  z-index: 2;
  display: grid;
  gap: 4px;
  max-width: 250px;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 20px;
  background: rgba(255, 253, 248, 0.88);
  padding: 14px 16px;
  box-shadow: 0 16px 38px rgba(102, 68, 35, 0.16);
  backdrop-filter: blur(14px);

  strong {
    color: #31512f;
    font-size: 14px;
  }

  span {
    color: #76573f;
    font-size: 12px;
  }
}

.food-recipe-page__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 118px;
  height: 42px;
  position: absolute;
  right: 20px;
  top: 20px;
  z-index: 2;
  border-radius: 999px;
  background: rgba(46, 33, 22, 0.92);
  color: #fff6df;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  box-shadow: 0 16px 36px rgba(46, 33, 22, 0.22);
}

.food-recipe-page__dots {
  position: absolute;
  left: 50%;
  bottom: 18px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 10px;
  transform: translateX(-50%);
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(255, 253, 247, 0.72);
  backdrop-filter: blur(10px);
}

.food-recipe-page__dot {
  width: 8px;
  height: 8px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(121, 82, 45, 0.36);
  cursor: pointer;
  transition: width 0.25s ease, height 0.25s ease, background-color 0.25s ease;

  &:hover {
    background: rgba(233, 109, 59, 0.7);
  }

  &.active {
    width: 16px;
    height: 16px;
    background: #e96d3b;
    box-shadow: 0 6px 16px rgba(233, 109, 59, 0.38);
  }
}

.food-recipe-page__body {
  display: grid;
  grid-template-columns: minmax(310px, 410px) minmax(0, 1fr);
  gap: clamp(18px, 3vw, 34px);
  padding: 0 clamp(18px, 5vw, 72px) clamp(36px, 6vw, 72px);
}

.food-recipe-page__left,
.food-recipe-page__right {
  display: grid;
  align-content: start;
  gap: $spacing-lg;
}

.food-recipe-page__panel,
.food-recipe-page__right {
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 24px 70px rgba(102, 68, 35, 0.12);
  backdrop-filter: blur(18px);
  padding: clamp(18px, 3vw, 28px);
}

.food-recipe-page__panel--upload {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(255, 248, 230, 0.84)),
    radial-gradient(circle at 0 0, rgba(255, 202, 97, 0.32), transparent 42%);
}

.food-recipe-page__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;
  margin-bottom: $spacing-md;

  h2 {
    margin: 4px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 24px;
    font-weight: 500;
  }

  select {
    height: 38px;
    border: 1px solid rgba(121, 82, 45, 0.18);
    border-radius: 999px;
    padding: 0 12px;
    color: #6f5038;
    background: rgba(255, 255, 255, 0.78);
  }
}

.food-recipe-page__threshold {
  display: grid;
  gap: $spacing-xs;
  margin-top: 18px;
  color: #856449;
  font-size: 13px;

  input {
    height: 42px;
    border: 1px solid rgba(121, 82, 45, 0.16);
    border-radius: 16px;
    padding: 0 14px;
    color: #3a2a1d;
    background: rgba(255, 255, 255, 0.82);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
  }
}

.food-recipe-page__primary {
  width: 100%;
  height: 48px;
  margin-top: 18px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  color: #fffaf0;
  cursor: pointer;
  font-weight: 800;
  letter-spacing: 0.04em;
  box-shadow: 0 16px 34px rgba(229, 104, 52, 0.26);
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 20px 42px rgba(229, 104, 52, 0.32);
  }

  &:disabled {
    background: #eadfce;
    color: #ad947d;
    box-shadow: none;
    cursor: not-allowed;
  }
}

.food-recipe-page__panel--guide {
  h2 {
    margin: 4px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 24px;
    font-weight: 500;
  }
}

.food-recipe-page__step-list {
  display: grid;
  gap: 12px;
  margin: 18px 0 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    border: 1px solid rgba(121, 82, 45, 0.12);
    border-radius: 20px;
    padding: 14px;
    background: rgba(255, 252, 245, 0.72);
    transition: transform 0.2s ease, background-color 0.2s ease;

    &.active {
      transform: translateX(4px);
      border-color: rgba(233, 109, 59, 0.32);
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
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: #f7db9a;
    color: #7c4c20;
    font-size: 12px;
    font-weight: 900;
  }

  strong {
    display: block;
    color: #3a2a1d;
    font-size: 14px;
  }

  small {
    display: block;
    margin-top: 3px;
    color: #8a6a50;
    font-size: 12px;
    line-height: 1.5;
  }
}

.food-recipe-page__tip {
  margin: 18px 0 0;
  border-radius: 18px;
  background: rgba(131, 170, 83, 0.12);
  color: #6b7040;
  padding: 14px;
  font-size: 13px;
  line-height: 1.7;
}

.food-recipe-page__right {
  min-height: 560px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 251, 241, 0.9)),
    radial-gradient(circle at 100% 0, rgba(243, 178, 91, 0.22), transparent 34%);
}

.food-recipe-page__empty,
.food-recipe-page__loading,
.food-recipe-page__error {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 260px;
  border: 1px dashed rgba(121, 82, 45, 0.22);
  border-radius: 26px;
  background:
    radial-gradient(circle at 50% 25%, rgba(255, 218, 132, 0.28), transparent 32%),
    rgba(255, 252, 244, 0.58);
  color: #8a6a50;
  text-align: center;

  strong {
    color: #3a2a1d;
    font-size: 18px;
  }

  span {
    max-width: 460px;
    line-height: 1.7;
  }
}

.food-recipe-page__loading {
  gap: $spacing-md;
}

.food-recipe-page__spinner {
  width: 34px;
  height: 34px;
  border: 4px solid #ffe0a1;
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
  .food-recipe-page__hero {
    grid-template-columns: 1fr;
  }

  .food-recipe-page__body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .food-recipe-page__hero {
    padding: 30px 18px 22px;
  }

  .food-recipe-page__hero-image {
    width: min(360px, 90vw);
    min-height: 260px;
    border-radius: 28px;

    .food-recipe-page__slide {
      min-height: 260px;
    }
  }

  .food-recipe-page__body {
    padding: 0 14px 30px;
  }

  .food-recipe-page__panel-header,
  .food-recipe-page__hero-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
