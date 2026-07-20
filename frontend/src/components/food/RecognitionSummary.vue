<template>
  <section class="recognition-summary" :class="`is-${status}`">
    <header class="recognition-summary__header">
      <div>
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
})

const emit = defineEmits(['generate-recipe'])

const canGenerate = computed(
  () => props.status === 'confirmed' && props.recognitionId && props.confirmedIngredients.length > 0
)

const summaryText = computed(() => {
  if (props.status === 'confirmed') return '食材都确认好啦，可以生成菜谱啦～'
  if (props.status === 'recognized') return '检查一下食材，确认后就能生成菜谱啦～'
  return '先识别并确认食材吧。'
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

@media (max-width: 640px) {
  .recognition-summary__header {
    align-items: stretch;
    flex-direction: column;
  }

}
</style>
