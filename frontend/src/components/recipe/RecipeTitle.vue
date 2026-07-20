<template>
  <header class="recipe-title">
    <div class="recipe-title__heading">
      <h2 data-testid="recipe-title">{{ recipe.title || '未命名菜谱' }}</h2>
      <select
        v-if="selectableVersions.length > 1"
        class="recipe-title__version-select"
        :value="selectedVersion || recipe.version"
        :disabled="versionLoading"
        aria-label="选择菜谱版本"
        data-testid="recipe-version-select"
        @change="changeVersion"
      >
        <option v-for="item in selectableVersions" :key="item.version" :value="item.version">
          v{{ item.version }}{{ item.is_current ? '（当前）' : '' }}
        </option>
      </select>
      <span v-else-if="recipe.version" class="recipe-title__version" data-testid="recipe-version">
        v{{ recipe.version }}
      </span>
    </div>
    <p v-if="recipe.summary" class="recipe-title__summary" data-testid="recipe-summary">
      {{ recipe.summary }}
    </p>
    <dl class="recipe-title__meta">
      <div>
        <dt class="sr-only">用餐人数</dt>
        <dd data-testid="recipe-servings">适合 {{ recipe.servings ?? '-' }} 人食用</dd>
      </div>
      <div>
        <dt class="sr-only">预计用时</dt>
        <dd data-testid="recipe-cooking-time">预计用时 {{ recipe.cooking_time_minutes ?? '-' }} 分钟</dd>
      </div>
      <div>
        <dt class="sr-only">难度</dt>
        <dd data-testid="recipe-difficulty">难度 {{ recipe.difficulty || '-' }}</dd>
      </div>
    </dl>
  </header>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  recipe: {
    type: Object,
    default: () => ({}),
  },
  versions: {
    type: Array,
    default: () => [],
  },
  selectedVersion: {
    type: Number,
    default: null,
  },
  versionLoading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['version-change'])
const selectableVersions = computed(() =>
  [...props.versions]
    .filter((item) => Number.isInteger(Number(item?.version)))
    .sort((left, right) => Number(left.version) - Number(right.version))
)

function changeVersion(event) {
  const version = Number(event.target.value)
  if (Number.isInteger(version) && version > 0) emit('version-change', version)
}
</script>

<style lang="scss" scoped>
.recipe-title {
  display: grid;
  gap: 12px;
  padding-bottom: 6px;
}

.recipe-title__heading {
  display: flex;
  align-items: center;
  gap: $spacing-sm;

  h2 {
    margin: 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: clamp(28px, 4vw, 42px);
    font-weight: 500;
    line-height: 1.12;
  }
}

.recipe-title__version {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 $spacing-sm;
  border-radius: 999px;
  background: #fff1d2;
  color: #965b22;
  font-size: 12px;
  font-weight: 600;
}

.recipe-title__summary {
  margin: 0;
  max-width: 760px;
  color: #76573f;
  font-size: 15px;
  line-height: 1.8;
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
    border: 1px solid rgba(121, 82, 45, 0.12);
    border-radius: 999px;
    background: rgba(255, 248, 234, 0.78);
    padding: 8px 13px;
  }

  dt {
    color: #9a7659;
    font-size: 13px;
  }

  dd {
    margin: 0;
    color: #3a2a1d;
    font-size: 14px;
    font-weight: 800;
  }
}

.recipe-title__version-select {
  height: 30px;
  border: 1px solid rgba(150, 91, 34, 0.24);
  border-radius: 6px;
  background: #fff8e8;
  color: #965b22;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  padding: 0 26px 0 9px;

  &:disabled {
    cursor: wait;
    opacity: 0.68;
  }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
