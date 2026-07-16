<template>
  <section class="ingredient-editor">
    <header class="ingredient-editor__header">
      <div>
        <h2>候选食材</h2>
        <p>{{ ingredients.length }} 项待确认</p>
      </div>
      <button
        class="ingredient-editor__add"
        type="button"
        data-testid="ingredient-add"
        :disabled="disabled"
        @click="addIngredient"
      >
        新增食材
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
            :disabled="disabled"
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
            :disabled="disabled"
            data-testid="ingredient-quantity"
            @input="syncIngredient"
          />
        </label>
        <label>
          <span>单位</span>
          <input
            v-model="ingredient.unit"
            type="text"
            :disabled="disabled"
            data-testid="ingredient-unit"
            @input="syncIngredient"
          />
        </label>
        <div class="ingredient-editor__meta">
          <span v-if="ingredient.image_index !== null" class="ingredient-editor__image-index">
            图 {{ ingredient.image_index + 1 }}
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
          :disabled="disabled"
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
      <button
        class="ingredient-editor__confirm"
        type="button"
        data-testid="ingredient-confirm"
        :disabled="disabled"
        @click="confirmIngredients"
      >
        确认食材
      </button>
    </footer>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
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
})

const emit = defineEmits(['update:modelValue', 'confirm', 'validation-error'])

const ingredients = ref(mapCandidatesToEditableIngredients(props.modelValue))
const validationErrors = ref([])

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
  gap: $spacing-md;
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
    margin: 0;
    color: $text-primary;
    font-size: 18px;
    font-weight: 600;
  }

  p {
    margin: $spacing-xs 0 0;
    color: $text-secondary;
    font-size: 13px;
  }
}

.ingredient-editor__add,
.ingredient-editor__confirm,
.ingredient-editor__delete {
  border: 1px solid $border-color-light;
  border-radius: $border-radius-sm;
  background: #fff;
  color: $text-regular;
  height: 34px;
  padding: 0 $spacing-md;
  cursor: pointer;

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
}

.ingredient-editor__add,
.ingredient-editor__confirm {
  border-color: $primary-color;
  background: $primary-color;
  color: #fff;
}

.ingredient-editor__list {
  display: grid;
  gap: $spacing-sm;
}

.ingredient-editor__row {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 90px 90px 150px 64px;
  align-items: end;
  gap: $spacing-md;
  padding: $spacing-md 0;
  border-bottom: 1px solid $border-color;

  label {
    display: grid;
    gap: $spacing-xs;
    color: $text-secondary;
    font-size: 12px;
  }

  input {
    width: 100%;
    height: 36px;
    box-sizing: border-box;
    border: 1px solid $border-color-light;
    border-radius: $border-radius-sm;
    padding: 0 $spacing-sm;
    color: $text-primary;
    font-size: 14px;
  }
}

.ingredient-editor__meta {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  min-height: 36px;
}

.ingredient-editor__image-index,
.ingredient-editor__confidence,
.ingredient-editor__source {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  padding: 0 $spacing-sm;
  font-size: 12px;
}

.ingredient-editor__image-index {
  background: #eff8ff;
  color: #175cd3;
}

.ingredient-editor__confidence {
  background: #ecfdf3;
  color: #027a48;
}

.ingredient-editor__source {
  background: #f2f4f7;
  color: #475467;
}

.ingredient-editor__delete {
  color: $danger-color;
}

.ingredient-editor__empty {
  display: grid;
  place-items: center;
  min-height: 96px;
  border: 1px dashed $border-color-light;
  border-radius: $border-radius-md;
  color: $text-secondary;
}

.ingredient-editor__errors {
  margin: 0;
  padding: $spacing-sm $spacing-md;
  border-radius: $border-radius-sm;
  background: #fff2f0;
  color: $danger-color;
  font-size: 13px;
}

@media (max-width: 760px) {
  .ingredient-editor__row {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .ingredient-editor__meta {
    min-height: 24px;
  }
}
</style>
