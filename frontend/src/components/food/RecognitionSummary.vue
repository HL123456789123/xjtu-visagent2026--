<template>
  <section class="recognition-summary" :class="`is-${status}`">
    <header class="recognition-summary__header">
      <div>
        <span class="recognition-summary__kicker">Step 03</span>
        <h2>生成家常菜谱</h2>
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
    type: [String, Number],
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
  gap: 18px;
  margin-top: 6px;
  border-top: 1px solid rgba(121, 82, 45, 0.12);
  padding-top: 24px;
}

.recognition-summary__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;

  h2 {
    margin: 4px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 26px;
    font-weight: 500;
  }

  p {
    margin: 6px 0 0;
    color: #856449;
    font-size: 13px;
    line-height: 1.6;
  }
}

.recognition-summary__kicker {
  color: #b56a26;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.recognition-summary__button {
  border: 0;
  border-radius: 999px;
  background: linear-gradient(135deg, #89a94f, #e6a23c);
  color: #fffaf0;
  height: 42px;
  padding: 0 22px;
  cursor: pointer;
  font-weight: 800;
  box-shadow: 0 14px 26px rgba(137, 169, 79, 0.24);
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 18px 34px rgba(137, 169, 79, 0.3);
  }

  &:disabled {
    background: #eadfce;
    color: #ad947d;
    box-shadow: none;
    cursor: not-allowed;
  }
}

.recognition-summary__contract {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  gap: $spacing-sm;
  margin: 0;

  div {
    min-width: 0;
    border: 1px solid rgba(121, 82, 45, 0.12);
    border-radius: 18px;
    padding: 12px;
    background: rgba(255, 250, 241, 0.82);
  }

  dt {
    color: #9a7659;
    font-size: 12px;
  }

  dd {
    margin: $spacing-xs 0 0;
    color: #3a2a1d;
    font-size: 13px;
    font-weight: 700;
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
