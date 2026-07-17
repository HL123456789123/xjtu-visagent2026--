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
  gap: 12px;
  border: 1px solid rgba(121, 82, 45, 0.11);
  border-radius: 24px;
  background: rgba(255, 252, 245, 0.78);
  padding: 18px;
}

.recipe-ingredients__title {
  margin: 0;
  color: #3a2a1d;
  font-family: Georgia, "Songti SC", serif;
  font-size: 22px;
  font-weight: 500;
}

.recipe-ingredients__list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.recipe-ingredients__item {
  display: flex;
  align-items: baseline;
  gap: $spacing-xs;
  padding: 10px 0;
  border-bottom: 1px solid rgba(121, 82, 45, 0.1);
  font-size: 14px;

  &:last-child {
    border-bottom: 0;
  }
}

.recipe-ingredients__name {
  color: #3a2a1d;
  font-weight: 800;
}

.recipe-ingredients__amount {
  color: #8a4d2a;
  margin-left: auto;
  font-weight: 700;
}

.recipe-ingredients__note {
  color: #8a6a50;
  font-size: 12px;
}

.recipe-ingredients__empty {
  margin: 0;
  padding: $spacing-lg 0;
  text-align: center;
  color: #ad947d;
  font-size: 14px;
}
</style>
