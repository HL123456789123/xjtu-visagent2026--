<template>
  <section class="nutrition-panel">
    <h3 class="nutrition-panel__title">营养估算</h3>

    <p v-if="nutrition.basis" class="nutrition-panel__basis" data-testid="nutrition-basis">
      {{ basisLabel }}
    </p>

    <div v-if="hasNutrition" class="nutrition-panel__grid">
      <div class="nutrition-panel__cell" data-testid="nutrition-calories">
        <span class="nutrition-panel__value">{{ nutrition.calories_kcal }}</span>
        <span class="nutrition-panel__unit">kcal</span>
        <span class="nutrition-panel__label">热量</span>
      </div>
      <div class="nutrition-panel__cell" data-testid="nutrition-protein">
        <span class="nutrition-panel__value">{{ nutrition.protein_g }}</span>
        <span class="nutrition-panel__unit">g</span>
        <span class="nutrition-panel__label">蛋白质</span>
      </div>
      <div class="nutrition-panel__cell" data-testid="nutrition-fat">
        <span class="nutrition-panel__value">{{ nutrition.fat_g }}</span>
        <span class="nutrition-panel__unit">g</span>
        <span class="nutrition-panel__label">脂肪</span>
      </div>
      <div class="nutrition-panel__cell" data-testid="nutrition-carbohydrates">
        <span class="nutrition-panel__value">{{ nutrition.carbohydrates_g }}</span>
        <span class="nutrition-panel__unit">g</span>
        <span class="nutrition-panel__label">碳水化合物</span>
      </div>
    </div>

    <p v-else class="nutrition-panel__empty" data-testid="nutrition-empty">
      暂无营养数据
    </p>

    <!-- 固定显示营养免责声明 (V1 第一节第3点) -->
    <p class="nutrition-panel__disclaimer" data-testid="nutrition-disclaimer">
      {{ disclaimer }}
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  nutrition: {
    type: Object,
    default: () => ({}),
  },
  disclaimer: {
    type: String,
    default: '营养数据由模型估算，仅供参考，不构成医疗或营养建议。',
  },
})

const hasNutrition = computed(() => {
  const n = props.nutrition
  if (!n) return false
  return (
    n.calories_kcal != null ||
    n.protein_g != null ||
    n.fat_g != null ||
    n.carbohydrates_g != null
  )
})

const basisLabel = computed(() => {
  const map = {
    per_serving: '每份营养',
    per_100g: '每 100g 营养',
    per_recipe: '整道菜营养',
  }
  return map[props.nutrition?.basis] || props.nutrition?.basis || ''
})
</script>

<style lang="scss" scoped>
.nutrition-panel {
  display: grid;
  gap: 12px;
  border: 1px solid rgba(121, 82, 45, 0.11);
  border-radius: 24px;
  background: rgba(255, 252, 245, 0.78);
  padding: 18px;
}

.nutrition-panel__title {
  margin: 0;
  color: #3a2a1d;
  font-family: Georgia, "Songti SC", serif;
  font-size: 22px;
  font-weight: 500;
}

.nutrition-panel__basis {
  margin: 0;
  font-size: 13px;
  color: #8a6a50;
}

.nutrition-panel__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: $spacing-sm;
}

.nutrition-panel__cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: $spacing-md $spacing-sm;
  border: 1px solid rgba(121, 82, 45, 0.1);
  border-radius: 18px;
  background: linear-gradient(180deg, #fff8ea, #fffdf8);
}

.nutrition-panel__value {
  font-size: 20px;
  font-weight: 700;
  color: #3a2a1d;
}

.nutrition-panel__unit {
  font-size: 12px;
  color: #9a7659;
}

.nutrition-panel__label {
  font-size: 12px;
  color: #8a6a50;
}

.nutrition-panel__empty {
  margin: 0;
  padding: $spacing-lg 0;
  text-align: center;
  color: #ad947d;
  font-size: 14px;
}

.nutrition-panel__disclaimer {
  margin: 0;
  padding: $spacing-sm $spacing-md;
  border-left: 3px solid #e6a23c;
  background: #fff3d8;
  border-radius: 14px;
  color: #856449;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 640px) {
  .nutrition-panel__grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
