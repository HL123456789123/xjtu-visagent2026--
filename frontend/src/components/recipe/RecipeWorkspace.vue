<template>
  <section class="food-recipe-page__recipe-flow" data-testid="recipe-flow">
    <header class="food-recipe-page__recipe-header">
      <h2>按你的口味生成</h2>
    </header>

    <div class="food-recipe-page__preferences" data-testid="recipe-preferences">
      <label>
        <span>用餐人数</span>
        <input
          :value="preferences.servings"
          type="number"
          min="1"
          max="10"
          :disabled="loading"
          @input="updateNumberPreference('servings', $event)"
        />
      </label>
      <label>
        <span>口味偏好</span>
        <input
          :value="preferences.taste"
          type="text"
          maxlength="20"
          :disabled="loading"
          @input="updateTextPreference('taste', $event)"
        />
      </label>
      <label>
        <span>希望多久做好</span>
        <input
          :value="preferences.max_time_minutes"
          type="number"
          min="5"
          max="180"
          :disabled="loading"
          @input="updateNumberPreference('max_time_minutes', $event)"
        />
      </label>
      <label>
        <span>不吃或忌口</span>
        <input
          :value="avoidIngredientsText"
          type="text"
          placeholder="例如：香菜, 辣椒"
          :disabled="loading"
          @input="emit('update:avoidIngredientsText', $event.target.value.trim())"
        />
      </label>
    </div>

    <RecipeCard
      :recipe="recipe"
      :loading="loading"
      :error="error"
      :available-versions="versions"
      :selected-version="selectedVersion"
      :version-loading="versionLoading"
      :show-chat-action="false"
      @retry="emit('retry')"
      @version-change="emit('version-change', $event)"
    />
    <div
      v-if="isHistoricalVersion"
      class="food-recipe-page__version-note"
      data-testid="historical-version-note"
    >
      <span>正在查看 v{{ selectedVersion }}，历史内容不会被改写。</span>
      <button
        type="button"
        data-testid="return-current-version"
        @click="emit('version-change', currentVersion)"
      >
        返回当前 v{{ currentVersion }}
      </button>
    </div>
    <p v-if="versionError" class="food-recipe-page__version-error" data-testid="recipe-version-error">
      {{ versionError }}
    </p>
    <ChatPage
      v-if="recipe?.recipe_id && !isHistoricalVersion"
      :recipe-id="recipe.recipe_id"
      @recipe-updated="emit('recipe-updated', $event)"
    />
  </section>
</template>

<script setup>
import RecipeCard from '@/components/recipe/RecipeCard.vue'
import ChatPage from '@/views/ChatPage.vue'

const props = defineProps({
  recipe: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: [Object, String], default: null },
  preferences: { type: Object, required: true },
  avoidIngredientsText: { type: String, default: '' },
  versions: { type: Array, default: () => [] },
  currentVersion: { type: Number, default: null },
  selectedVersion: { type: Number, default: null },
  versionLoading: { type: Boolean, default: false },
  versionError: { type: String, default: '' },
  isHistoricalVersion: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:preferences',
  'update:avoidIngredientsText',
  'retry',
  'version-change',
  'recipe-updated',
])

function updateNumberPreference(key, event) {
  const value = event.target.value === '' ? '' : Number(event.target.value)
  emit('update:preferences', { ...props.preferences, [key]: value })
}

function updateTextPreference(key, event) {
  emit('update:preferences', { ...props.preferences, [key]: event.target.value.trim() })
}
</script>

<style lang="scss" scoped>
.food-recipe-page__recipe-flow {
  display: grid;
  gap: 18px;
  margin-top: 6px;
  border-top: 1px solid rgba(121, 82, 45, 0.12);
  padding-top: 24px;
}

.food-recipe-page__version-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-left: 3px solid #d99a2b;
  background: #fff6df;
  color: #765b36;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;

  button {
    flex-shrink: 0;
    border: 0;
    background: transparent;
    color: #b45b25;
    cursor: pointer;
    font: inherit;
    font-weight: 800;
    padding: 4px;
  }
}

.food-recipe-page__version-error {
  margin: 0;
  color: #c44b37;
  font-size: 13px;
}

.food-recipe-page__recipe-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;

  h2 {
    margin: 4px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 24px;
    font-weight: 500;
  }
}

.food-recipe-page__preferences {
  display: grid;
  grid-template-columns: 90px minmax(120px, 0.8fr) 110px minmax(160px, 1fr);
  gap: $spacing-md;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 8px;
  background: rgba(255, 250, 241, 0.82);
  padding: 14px;

  label {
    display: grid;
    gap: $spacing-xs;
    color: #8a6a50;
    font-size: 12px;
  }

  input {
    width: 100%;
    height: 38px;
    box-sizing: border-box;
    border: 1px solid rgba(121, 82, 45, 0.16);
    border-radius: 6px;
    padding: 0 12px;
    color: #3a2a1d;
    background: #fffefa;

    &:disabled {
      color: #ad947d;
      background: #f6efe4;
    }

    &:focus {
      border-color: #89a94f;
      box-shadow: 0 0 0 3px rgba(137, 169, 79, 0.14);
      outline: none;
    }
  }
}

@media (max-width: 960px) {
  .food-recipe-page__preferences {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .food-recipe-page__recipe-header {
    align-items: stretch;
    flex-direction: column;
  }

  .food-recipe-page__preferences {
    grid-template-columns: 1fr;
  }
}
</style>
