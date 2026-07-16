<template>
  <section class="ingredient-editor">
    <header class="ingredient-editor__header">
      <div>
        <span class="ingredient-editor__kicker">Step 02</span>
        <h2>确认今天的食材</h2>
        <p>{{ ingredients.length }} 项待确认，可以直接修改名称或补充遗漏食材。</p>
      </div>
      <button
        class="ingredient-editor__add"
        type="button"
        data-testid="ingredient-add"
        :disabled="disabled"
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
        确认食材，准备生成菜谱
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

.ingredient-editor__kicker {
  color: #b56a26;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.ingredient-editor__add,
.ingredient-editor__confirm,
.ingredient-editor__delete {
  border: 1px solid rgba(121, 82, 45, 0.14);
  border-radius: 999px;
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
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  color: #fffaf0;
  box-shadow: 0 12px 24px rgba(229, 104, 52, 0.22);
}

.ingredient-editor__list {
  display: grid;
  gap: 12px;
}

.ingredient-editor__row {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 90px 90px 150px 64px;
  align-items: end;
  gap: $spacing-md;
  padding: 14px;
  border: 1px solid rgba(121, 82, 45, 0.11);
  border-radius: 20px;
  background: rgba(255, 252, 245, 0.82);
  box-shadow: 0 12px 26px rgba(102, 68, 35, 0.06);

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
    border-radius: 14px;
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
  gap: $spacing-sm;
  min-height: 36px;
}

.ingredient-editor__confidence,
.ingredient-editor__source {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  padding: 0 $spacing-sm;
  font-size: 12px;
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
  border-radius: 20px;
  background: #fffaf1;
  color: #8a6a50;
}

.ingredient-editor__errors {
  margin: 0;
  padding: $spacing-sm $spacing-md;
  border-radius: 16px;
  background: #fff1e9;
  color: #c44b37;
  font-size: 13px;
}

.ingredient-editor__actions {
  justify-content: flex-end;
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
}
</style>
