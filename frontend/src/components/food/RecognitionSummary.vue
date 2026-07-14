<template>
  <section class="recognition-summary" :class="`is-${status}`">
    <header class="recognition-summary__header">
      <div>
        <h2>菜谱生成输入</h2>
        <p>{{ summaryText }}</p>
      </div>
      <button
        class="recognition-summary__button"
        type="button"
        data-testid="recipe-generate"
        :disabled="!canGenerate"
        @click="emitRecipeRequest"
      >
        生成菜谱
      </button>
    </header>

    <dl class="recognition-summary__contract">
      <div>
        <dt>recognition_id</dt>
        <dd data-testid="summary-recognition-id">{{ recognitionId || '-' }}</dd>
      </div>
      <div>
        <dt>confirmed_ingredients</dt>
        <dd data-testid="summary-confirmed-count">{{ confirmedIngredients.length }} 项</dd>
      </div>
      <div>
        <dt>provider</dt>
        <dd>{{ provider || '-' }}</dd>
      </div>
      <div>
        <dt>model_version</dt>
        <dd>{{ modelVersion || '-' }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  recognitionId: {
    type: String,
    default: '',
  },
  confirmedIngredients: {
    type: Array,
    default: () => [],
  },
  status: {
    type: String,
    default: 'idle',
  },
  provider: {
    type: String,
    default: '',
  },
  modelVersion: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['generate-recipe'])

const canGenerate = computed(
  () => props.status === 'confirmed' && props.recognitionId && props.confirmedIngredients.length > 0
)

const summaryText = computed(() => {
  if (props.status === 'confirmed') return '已确认，可交给菜谱模块。'
  if (props.status === 'recognized') return '请先确认食材。'
  return '等待识别结果。'
})

function emitRecipeRequest() {
  if (!canGenerate.value) return
  emit('generate-recipe', {
    recognition_id: props.recognitionId,
    confirmed_ingredients: props.confirmedIngredients,
  })
}
</script>

<style lang="scss" scoped>
.recognition-summary {
  display: grid;
  gap: $spacing-md;
  border-top: 1px solid $border-color;
  padding-top: $spacing-lg;
}

.recognition-summary__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;

  h2 {
    margin: 0;
    color: $text-primary;
    font-size: 18px;
  }

  p {
    margin: $spacing-xs 0 0;
    color: $text-secondary;
    font-size: 13px;
  }
}

.recognition-summary__button {
  border: 1px solid $success-color;
  border-radius: $border-radius-sm;
  background: $success-color;
  color: #fff;
  height: 36px;
  padding: 0 $spacing-md;
  cursor: pointer;

  &:disabled {
    border-color: $border-color-light;
    background: #f2f4f7;
    color: $text-placeholder;
    cursor: not-allowed;
  }
}

.recognition-summary__contract {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: $spacing-sm;
  margin: 0;

  div {
    min-width: 0;
    border: 1px solid $border-color;
    border-radius: $border-radius-sm;
    padding: $spacing-sm;
    background: #fafafa;
  }

  dt {
    color: $text-secondary;
    font-size: 12px;
  }

  dd {
    margin: $spacing-xs 0 0;
    color: $text-primary;
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

@media (max-width: 920px) {
  .recognition-summary__contract {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .recognition-summary__header {
    align-items: stretch;
    flex-direction: column;
  }

  .recognition-summary__contract {
    grid-template-columns: 1fr;
  }
}
</style>
