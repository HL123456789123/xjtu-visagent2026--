<template>
  <section class="recipe-ingredients">
    <h3 class="recipe-ingredients__title">食材用量</h3>
    <ul v-if="ingredients.length > 0" class="recipe-ingredients__list">
      <li
        v-for="(item, index) in ingredients"
        :key="index"
        class="recipe-ingredients__item"
        data-testid="ingredient-item"
      >
        <span class="recipe-ingredients__name" data-testid="ingredient-name">
          {{ item.name }}
        </span>
        <span class="recipe-ingredients__amount" data-testid="ingredient-amount">
          {{ item.amount }} {{ item.unit }}
        </span>
        <span
          v-if="item.note"
          class="recipe-ingredients__note"
          data-testid="ingredient-note"
        >
          ({{ item.note }})
        </span>
      </li>
    </ul>
    <p v-else class="recipe-ingredients__empty" data-testid="ingredient-empty">
      暂无食材信息
    </p>
  </section>
</template>

<script setup>
defineProps({
  ingredients: {
    type: Array,
    default: () => [],
  },
})
</script>

<style lang="scss" scoped>
.recipe-ingredients {
  display: grid;
  gap: $spacing-sm;
}

.recipe-ingredients__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.recipe-ingredients__list {
  display: grid;
  gap: $spacing-xs;
  margin: 0;
  padding: 0;
  list-style: none;
}

.recipe-ingredients__item {
  display: flex;
  align-items: baseline;
  gap: $spacing-xs;
  padding: $spacing-xs 0;
  border-bottom: 1px solid $border-color;
  font-size: 14px;
}

.recipe-ingredients__name {
  color: $text-primary;
  font-weight: 500;
}

.recipe-ingredients__amount {
  color: $text-regular;
  margin-left: auto;
}

.recipe-ingredients__note {
  color: $text-secondary;
  font-size: 12px;
}

.recipe-ingredients__empty {
  margin: 0;
  padding: $spacing-lg 0;
  text-align: center;
  color: $text-placeholder;
  font-size: 14px;
}
</style>
