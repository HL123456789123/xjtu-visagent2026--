<template>
  <section class="ingredient-editor">
    <header class="ingredient-editor__header">
      <div>
        <h2>识别结果与食材确认</h2>
        <p>共 {{ ingredients.length }} 种食材，可以修改名称、数量，或补充遗漏食材。</p>
      </div>
      <button
        class="ingredient-editor__add"
        type="button"
        data-testid="ingredient-add"
        :disabled="readOnly"
        @click="addIngredient"
      >
        + 新增食材
      </button>
    </header>

    <div v-if="ingredients.length" class="ingredient-editor__list" data-testid="ingredient-list">
      <article
        v-for="(ingredient, index) in ingredients"
        :key="ingredient.draftId"
        class="ingredient-editor__row"
      >
        <label>
          <span>名称</span>
          <input
            v-model="ingredient.name"
            type="text"
            :disabled="readOnly"
            data-testid="ingredient-name"
            @input="syncIngredient(index)"
          />
        </label>
        <label>
          <span>数量</span>
          <input
            v-model.number="ingredient.quantity"
            type="number"
            min="0.01"
            step="0.01"
            :disabled="readOnly"
            data-testid="ingredient-quantity"
            @input="syncIngredient"
          />
        </label>
        <label>
          <span>单位</span>
          <input
            v-model="ingredient.unit"
            type="text"
            :disabled="readOnly"
            data-testid="ingredient-unit"
            @input="syncIngredient"
          />
        </label>
        <div class="ingredient-editor__meta">
          <button
            v-if="canPreviewIngredient(ingredient)"
            class="ingredient-editor__image-index ingredient-editor__image-link"
            type="button"
            data-testid="ingredient-image-link"
            @click="openPreview(ingredient)"
          >
            识别来源
          </button>
          <span v-else-if="formatDetectionSummary(ingredient)" class="ingredient-editor__image-index">
            识别来源
          </span>
          <span class="ingredient-editor__confidence">
            {{ formatConfidence(ingredient.confidence) }}
          </span>
          <span class="ingredient-editor__source">
            {{ formatSource(ingredient.source) }}
          </span>
        </div>
        <button
          class="ingredient-editor__delete"
          type="button"
          :disabled="readOnly"
          data-testid="ingredient-delete"
          @click="removeIngredient(index)"
        >
          删除
        </button>
      </article>
    </div>

    <div v-else class="ingredient-editor__empty" data-testid="ingredient-empty">
      未识别到食材，可手动新增后确认。
    </div>

    <ul v-if="validationErrors.length" class="ingredient-editor__errors" data-testid="ingredient-errors">
      <li v-for="error in validationErrors" :key="error">{{ error }}</li>
    </ul>

    <footer class="ingredient-editor__actions">
      <p v-if="editing && hasExistingRecipe" class="ingredient-editor__edit-note">
        重新确认后可按新食材生成菜谱，当前菜谱仍保留在历史记录中。
      </p>
      <span v-else></span>
      <button
        v-if="confirmed"
        class="ingredient-editor__confirm"
        type="button"
        data-testid="ingredient-edit-confirmed"
        :disabled="disabled"
        @click="emit('edit-requested')"
      >
        修改已确认食材
      </button>
      <button
        v-if="editing"
        class="ingredient-editor__cancel"
        type="button"
        data-testid="ingredient-edit-cancel"
        :disabled="disabled"
        @click="emit('cancel-edit')"
      >
        取消修改
      </button>
      <button
        v-if="!confirmed"
        class="ingredient-editor__confirm"
        type="button"
        data-testid="ingredient-confirm"
        :disabled="disabled"
        @click="confirmIngredients"
      >
        {{ editing ? '重新确认食材' : '确认食材，准备生成菜谱' }}
      </button>
    </footer>

    <Teleport to="body">
      <div
        v-if="previewIngredient && previewImage"
        class="ingredient-preview"
        data-testid="ingredient-preview"
        @click.self="closePreview"
      >
        <section class="ingredient-preview__dialog" role="dialog" aria-modal="true">
          <header class="ingredient-preview__header">
            <div>
              <strong>{{ previewIngredient.name }}</strong>
              <span>图 {{ previewDetection.image_index + 1 }}</span>
            </div>
            <div class="ingredient-preview__controls">
              <span v-if="previewDetections.length > 1">
                {{ previewDetectionIndex + 1 }} / {{ previewDetections.length }}
              </span>
              <button
                v-if="previewDetections.length > 1"
                type="button"
                title="上一个位置"
                data-testid="ingredient-preview-previous"
                @click="movePreview(-1)"
              >
                <el-icon><ArrowLeft /></el-icon>
              </button>
              <button
                v-if="previewDetections.length > 1"
                type="button"
                title="下一个位置"
                data-testid="ingredient-preview-next"
                @click="movePreview(1)"
              >
                <el-icon><ArrowRight /></el-icon>
              </button>
              <button type="button" title="关闭" data-testid="ingredient-preview-close" @click="closePreview">
                <el-icon><Close /></el-icon>
              </button>
            </div>
          </header>

          <div class="ingredient-preview__canvas">
            <div class="ingredient-preview__figure">
              <img :src="previewImage.image_url" :alt="`图 ${previewDetection.image_index + 1}`" @load="handlePreviewImageLoad" />
              <div v-if="previewBoxStyle" class="ingredient-preview__box" :style="previewBoxStyle">
                <span>{{ previewIngredient.name }} · {{ formatConfidence(previewDetection.confidence) }}</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, Close } from '@element-plus/icons-vue'
import {
  buildConfirmedIngredients,
  mapCandidatesToEditableIngredients,
  validateConfirmedIngredients,
} from './ingredientEditorModel'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  images: {
    type: Array,
    default: () => [],
  },
  confirmed: {
    type: Boolean,
    default: false,
  },
  editing: {
    type: Boolean,
    default: false,
  },
  hasExistingRecipe: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:modelValue',
  'confirm',
  'validation-error',
  'edit-requested',
  'cancel-edit',
])

const ingredients = ref(mapCandidatesToEditableIngredients(props.modelValue))
const validationErrors = ref([])
const previewIngredient = ref(null)
const previewDetectionIndex = ref(0)
const previewNaturalSize = ref({ width: 0, height: 0 })
const readOnly = computed(() => props.disabled || props.confirmed)

function getIngredientDetections(ingredient) {
  if (Array.isArray(ingredient?.sourceDetections) && ingredient.sourceDetections.length) {
    return ingredient.sourceDetections
  }
  if (Number.isInteger(ingredient?.image_index) && ingredient?.bbox) {
    return [{
      candidate_id: ingredient.candidate_id || null,
      image_index: ingredient.image_index,
      confidence: ingredient.confidence,
      bbox: ingredient.bbox,
    }]
  }
  return []
}

const previewDetections = computed(() => {
  if (!previewIngredient.value) return []
  return getIngredientDetections(previewIngredient.value).filter((detection) =>
    Number.isInteger(detection.image_index) &&
    detection.bbox &&
    props.images.some((image) => image.image_index === detection.image_index && image.image_url)
  )
})

const previewDetection = computed(() => previewDetections.value[previewDetectionIndex.value] || null)

const previewImage = computed(() => {
  if (!previewDetection.value) return null
  return props.images.find((image) => image.image_index === previewDetection.value.image_index) || null
})

const previewBoxStyle = computed(() => {
  const bbox = previewDetection.value?.bbox
  const { width, height } = previewNaturalSize.value
  if (!bbox || !width || !height) return null

  const x1 = Math.max(0, Math.min(width, Number(bbox.x1)))
  const y1 = Math.max(0, Math.min(height, Number(bbox.y1)))
  const x2 = Math.max(x1, Math.min(width, Number(bbox.x2)))
  const y2 = Math.max(y1, Math.min(height, Number(bbox.y2)))
  if (![x1, y1, x2, y2].every(Number.isFinite) || x2 <= x1 || y2 <= y1) return null

  return {
    left: `${(x1 / width) * 100}%`,
    top: `${(y1 / height) * 100}%`,
    width: `${((x2 - x1) / width) * 100}%`,
    height: `${((y2 - y1) / height) * 100}%`,
  }
})

function emitUpdate() {
  emit('update:modelValue', ingredients.value.map((ingredient) => ({ ...ingredient })))
}

function syncIngredient() {
  validationErrors.value = []
  emitUpdate()
}

function addIngredient() {
  ingredients.value.push({
    draftId: `manual_${Date.now()}_${ingredients.value.length}`,
    candidate_id: null,
    class_name: null,
    image_index: null,
    name: '',
    confidence: null,
    quantity: 1,
    unit: '个',
    source: 'manual',
    bbox: null,
    sourceDetections: [],
  })
  validationErrors.value = []
  emitUpdate()
}

function removeIngredient(index) {
  ingredients.value.splice(index, 1)
  validationErrors.value = []
  emitUpdate()
}

function formatConfidence(value) {
  if (typeof value !== 'number') return '手动'
  return `${(value * 100).toFixed(1)}%`
}

function formatSource(source) {
  return source === 'manual' ? '手动新增' : '模型识别'
}

function formatDetectionSummary(ingredient) {
  const detections = getIngredientDetections(ingredient)
  if (!detections.length) return ''
  const imageNumbers = [...new Set(
    detections
      .map((detection) => detection.image_index)
      .filter(Number.isInteger)
      .map((imageIndex) => imageIndex + 1)
  )]
  if (!imageNumbers.length) return ''
  const imageText = imageNumbers.length <= 2
    ? `图 ${imageNumbers.join('、')}`
    : `图 ${imageNumbers.slice(0, 2).join('、')} 等`
  return detections.length > 1 ? `${imageText} · ${detections.length}处` : imageText
}

function canPreviewIngredient(ingredient) {
  return (
    ingredient.source === 'model' &&
    getIngredientDetections(ingredient).some((detection) =>
      Number.isInteger(detection.image_index) &&
      detection.bbox &&
      props.images.some((image) => image.image_index === detection.image_index && image.image_url)
    )
  )
}

function openPreview(ingredient) {
  previewNaturalSize.value = { width: 0, height: 0 }
  previewIngredient.value = ingredient
  previewDetectionIndex.value = 0
}

function movePreview(direction) {
  const count = previewDetections.value.length
  if (count <= 1) return
  previewNaturalSize.value = { width: 0, height: 0 }
  previewDetectionIndex.value = (previewDetectionIndex.value + direction + count) % count
}

function closePreview() {
  previewIngredient.value = null
  previewDetectionIndex.value = 0
  previewNaturalSize.value = { width: 0, height: 0 }
}

function handlePreviewImageLoad(event) {
  previewNaturalSize.value = {
    width: event.target.naturalWidth,
    height: event.target.naturalHeight,
  }
}

function handlePreviewKeydown(event) {
  if (event.key === 'Escape' && previewIngredient.value) closePreview()
  if (event.key === 'ArrowLeft' && previewIngredient.value) movePreview(-1)
  if (event.key === 'ArrowRight' && previewIngredient.value) movePreview(1)
}

function validate() {
  const result = validateConfirmedIngredients(ingredients.value)
  validationErrors.value = result.errors
  if (!result.valid) {
    emit('validation-error', result.errors)
  }
  return result
}

function confirmIngredients() {
  const result = validate()
  if (!result.valid) return
  emit('confirm', buildConfirmedIngredients(ingredients.value))
}

watch(
  () => props.modelValue,
  (value) => {
    ingredients.value = mapCandidatesToEditableIngredients(value)
    validationErrors.value = []
  },
  { deep: true }
)

onMounted(() => window.addEventListener('keydown', handlePreviewKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handlePreviewKeydown))

defineExpose({
  addIngredient,
  removeIngredient,
  validate,
  confirmIngredients,
})
</script>

<style lang="scss" scoped>
.ingredient-editor {
  display: grid;
  gap: 18px;
}

.ingredient-editor__header,
.ingredient-editor__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;
}

.ingredient-editor__header {
  h2 {
    margin: 4px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 26px;
    font-weight: 500;
  }

  p {
    max-width: 520px;
    margin: 6px 0 0;
    color: #856449;
    font-size: 13px;
    line-height: 1.6;
  }
}

.ingredient-editor__add,
.ingredient-editor__confirm,
.ingredient-editor__delete {
  border: 1px solid rgba(121, 82, 45, 0.14);
  border-radius: 6px;
  background: #fff8ea;
  color: #7a4a28;
  height: 38px;
  padding: 0 16px;
  cursor: pointer;
  font-weight: 700;
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 10px 22px rgba(102, 68, 35, 0.12);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
}

.ingredient-editor__add,
.ingredient-editor__confirm {
  border-color: transparent;
  background: #e96d3b;
  color: #fffaf0;
  box-shadow: 0 12px 24px rgba(229, 104, 52, 0.22);
}

.ingredient-editor__list {
  display: grid;
  gap: 12px;
}

.ingredient-editor__row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 84px 84px 236px 64px;
  align-items: end;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(121, 82, 45, 0.11);
  border-radius: 6px;
  background: rgba(255, 252, 245, 0.82);

  label {
    display: grid;
    gap: $spacing-xs;
    color: #8a6a50;
    font-size: 12px;
  }

  input {
    width: 100%;
    height: 40px;
    box-sizing: border-box;
    border: 1px solid rgba(121, 82, 45, 0.16);
    border-radius: 6px;
    padding: 0 12px;
    color: #3a2a1d;
    background: #fffefa;
    font-size: 14px;

    &:focus {
      border-color: #e96d3b;
      box-shadow: 0 0 0 3px rgba(233, 109, 59, 0.12);
      outline: none;
    }
  }
}

.ingredient-editor__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.ingredient-editor__image-index,
.ingredient-editor__confidence,
.ingredient-editor__source {
  display: inline-flex;
  align-items: center;
  height: 24px;
  box-sizing: border-box;
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0 $spacing-sm;
  font-size: 12px;
}

.ingredient-editor__image-index {
  background: #eff8ff;
  color: #175cd3;
}

.ingredient-editor__image-link {
  border: 0;
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.ingredient-editor__confidence {
  background: #eff8d6;
  color: #62772b;
}

.ingredient-editor__source {
  background: #fff1d2;
  color: #965b22;
}

.ingredient-editor__delete {
  color: #c44b37;
}

.ingredient-editor__empty {
  display: grid;
  place-items: center;
  min-height: 96px;
  border: 1px dashed rgba(121, 82, 45, 0.22);
  border-radius: 6px;
  background: #fffaf1;
  color: #8a6a50;
}

.ingredient-editor__errors {
  margin: 0;
  padding: $spacing-sm $spacing-md;
  border-radius: 6px;
  background: #fff1e9;
  color: #c44b37;
  font-size: 13px;
}

.ingredient-editor__actions {
  justify-content: flex-end;
}

.ingredient-editor__edit-note {
  margin: 0 auto 0 0;
  color: #856449;
  font-size: 13px;
  line-height: 1.5;
}

.ingredient-editor__cancel {
  height: 38px;
  border: 1px solid rgba(121, 82, 45, 0.2);
  border-radius: 6px;
  background: #fff;
  color: #76573f;
  padding: 0 16px;
  cursor: pointer;
  font-weight: 700;
}

.ingredient-preview {
  position: fixed;
  inset: 0;
  z-index: 2100;
  display: grid;
  place-items: center;
  background: rgba(48, 37, 28, 0.42);
  padding: 24px;
}

.ingredient-preview__dialog {
  width: min(50vw, 720px);
  max-height: calc(100vh - 48px);
  overflow: auto;
  border: 1px solid rgba(121, 82, 45, 0.16);
  border-radius: 8px;
  background: #fffdf8;
  box-shadow: 0 24px 70px rgba(60, 39, 24, 0.24);
}

.ingredient-preview__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgba(121, 82, 45, 0.12);
  padding: 14px 16px;

  div {
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
  }

  strong {
    color: #3a2a1d;
    font-size: 17px;
  }

  span {
    color: #806a55;
    font-size: 13px;
  }

  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    flex: 0 0 auto;
    border: 0;
    border-radius: 50%;
    background: #f6ede0;
    color: #76573f;
    cursor: pointer;
    font-size: 18px;
  }
}

.ingredient-preview__controls {
  align-items: center !important;
  margin-left: auto;
}

.ingredient-preview__canvas {
  display: grid;
  min-height: 220px;
  place-items: center;
  background: #f5f0e7;
  padding: 16px;
}

.ingredient-preview__figure {
  position: relative;
  display: inline-block;
  max-width: 100%;
  line-height: 0;

  img {
    display: block;
    width: auto;
    max-width: 100%;
    height: auto;
    max-height: 62vh;
  }
}

.ingredient-preview__box {
  position: absolute;
  box-sizing: border-box;
  border: 3px solid #f06b38;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.78);

  span {
    position: absolute;
    top: 0;
    left: 0;
    display: inline-flex;
    min-height: 24px;
    align-items: center;
    background: #f06b38;
    color: #fff;
    padding: 0 7px;
    font-size: 12px;
    font-weight: 700;
    line-height: 1;
    white-space: nowrap;
  }
}

@media (max-width: 760px) {
  .ingredient-editor__header,
  .ingredient-editor__actions {
    align-items: stretch;
    flex-direction: column;
  }

  .ingredient-editor__row {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .ingredient-editor__meta {
    min-height: 24px;
  }

  .ingredient-editor__actions {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .ingredient-editor__edit-note {
    width: 100%;
  }

  .ingredient-preview {
    padding: 16px;
  }

  .ingredient-preview__dialog {
    width: calc(100vw - 32px);
  }
}
</style>
