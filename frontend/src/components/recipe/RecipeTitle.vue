<template>
  <header class="recipe-title">
    <div class="recipe-title__heading">
      <h2 data-testid="recipe-title">{{ recipe.title || '未命名菜谱' }}</h2>
      <span v-if="recipe.version" class="recipe-title__version" data-testid="recipe-version">
        v{{ recipe.version }}
      </span>
    </div>
    <p v-if="recipe.summary" class="recipe-title__summary" data-testid="recipe-summary">
      {{ recipe.summary }}
    </p>
    <dl class="recipe-title__meta">
      <div>
        <dt>份数</dt>
        <dd data-testid="recipe-servings">{{ recipe.servings ?? '-' }} 人份</dd>
      </div>
      <div>
        <dt>耗时</dt>
        <dd data-testid="recipe-cooking-time">{{ recipe.cooking_time_minutes ?? '-' }} 分钟</dd>
      </div>
      <div>
        <dt>难度</dt>
        <dd data-testid="recipe-difficulty">{{ recipe.difficulty || '-' }}</dd>
      </div>
    </dl>
  </header>
</template>

<script setup>
defineProps({
  recipe: {
    type: Object,
    default: () => ({}),
  },
})
</script>

<style lang="scss" scoped>
.recipe-title {
  display: grid;
  gap: $spacing-sm;
}

.recipe-title__heading {
  display: flex;
  align-items: center;
  gap: $spacing-sm;

  h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 650;
    color: $text-primary;
  }
}

.recipe-title__version {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 $spacing-sm;
  border-radius: 999px;
  background: $bg-color-light-blue;
  color: $primary-color;
  font-size: 12px;
  font-weight: 600;
}

.recipe-title__summary {
  margin: 0;
  color: $text-secondary;
  font-size: 14px;
  line-height: 1.5;
}

.recipe-title__meta {
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-md;
  margin: 0;

  div {
    display: flex;
    align-items: baseline;
    gap: $spacing-xs;
  }

  dt {
    color: $text-secondary;
    font-size: 13px;
  }

  dd {
    margin: 0;
    color: $text-primary;
    font-size: 14px;
    font-weight: 500;
  }
}
</style>
