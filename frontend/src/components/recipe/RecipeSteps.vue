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
  gap: 14px;
  border: 1px solid rgba(121, 82, 45, 0.11);
  border-radius: 24px;
  background: rgba(255, 252, 245, 0.78);
  padding: 18px;
}

.recipe-steps__title {
  margin: 0;
  color: #3a2a1d;
  font-family: Georgia, "Songti SC", serif;
  font-size: 22px;
  font-weight: 500;
}

.recipe-steps__list {
  display: grid;
  gap: 14px;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: none;
}

.recipe-steps__item {
  display: flex;
  gap: 14px;
  padding: 14px;
  border-radius: 20px;
  background: rgba(255, 248, 234, 0.78);
}

.recipe-steps__no {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e96d3b;
  color: #fffaf0;
  box-shadow: 0 8px 18px rgba(233, 109, 59, 0.22);
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
  color: #3a2a1d;
  font-size: 14px;
  line-height: 1.6;
}

.recipe-steps__duration {
  color: #9a7659;
  font-size: 12px;
  font-weight: 700;
}

.recipe-steps__empty {
  margin: 0;
  padding: $spacing-lg 0;
  text-align: center;
  color: #ad947d;
  font-size: 14px;
}
</style>
