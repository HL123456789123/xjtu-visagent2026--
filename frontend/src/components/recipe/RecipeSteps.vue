<template>
  <section class="recipe-steps">
    <h3 class="recipe-steps__title">烹饪步骤</h3>
    <ol v-if="steps.length > 0" class="recipe-steps__list">
      <li
        v-for="step in steps"
        :key="step.step_no"
        class="recipe-steps__item"
        data-testid="step-item"
      >
        <span class="recipe-steps__no" data-testid="step-no">{{ step.step_no }}</span>
        <div class="recipe-steps__body">
          <p class="recipe-steps__desc" data-testid="step-description">{{ step.description }}</p>
          <span
            v-if="step.duration_minutes != null"
            class="recipe-steps__duration"
            data-testid="step-duration"
          >
            约 {{ step.duration_minutes }} 分钟
          </span>
        </div>
      </li>
    </ol>
    <p v-else class="recipe-steps__empty" data-testid="step-empty">
      暂无步骤信息
    </p>
  </section>
</template>

<script setup>
defineProps({
  steps: {
    type: Array,
    default: () => [],
  },
})
</script>

<style lang="scss" scoped>
.recipe-steps {
  display: grid;
  gap: $spacing-sm;
}

.recipe-steps__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.recipe-steps__list {
  display: grid;
  gap: $spacing-md;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: none;
}

.recipe-steps__item {
  display: flex;
  gap: $spacing-md;
}

.recipe-steps__no {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: $primary-color;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}

.recipe-steps__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: $spacing-xs;
}

.recipe-steps__desc {
  margin: 0;
  color: $text-primary;
  font-size: 14px;
  line-height: 1.6;
}

.recipe-steps__duration {
  color: $text-secondary;
  font-size: 12px;
}

.recipe-steps__empty {
  margin: 0;
  padding: $spacing-lg 0;
  text-align: center;
  color: $text-placeholder;
  font-size: 14px;
}
</style>
