<template>
  <section v-if="results.length" class="recognition-result-list" data-testid="recognition-result-list">
    <header class="recognition-result-list__header">
      <div>
        <span class="recognition-result-list__kicker">识别结果</span>
        <h2>识别到的食材</h2>
        <p>置信度反映模型判断的可靠程度；点击链接图标可在新页面查看对应图片。</p>
      </div>
      <span class="recognition-result-list__count">{{ results.length }} 条结果</span>
    </header>

    <ul class="recognition-result-list__items">
      <li v-for="result in results" :key="result.candidate_id">
        <span class="recognition-result-list__name">
          {{ result.display_name || result.class_name || '未命名食材' }}
        </span>
        <strong>置信度 {{ formatConfidence(result.confidence) }}</strong>
        <a
          v-if="result.image_url"
          class="recognition-result-list__image-link"
          :href="result.image_url"
          target="_blank"
          rel="noopener"
          title="查看识别图片"
          aria-label="查看识别图片"
          data-testid="recognition-image-link"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M14 3h7v7m0-7-10 10" />
            <path d="M11 5H6a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-5" />
          </svg>
        </a>
      </li>
    </ul>
  </section>
</template>

<script setup>
defineProps({
  results: {
    type: Array,
    default: () => [],
  },
})

function formatConfidence(value) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}
</script>

<style lang="scss" scoped>
.recognition-result-list {
  display: grid;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(121, 82, 45, 0.12);
}

.recognition-result-list__header {
  display: flex;
  align-items: flex-end;
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

.recognition-result-list__kicker {
  color: #b56a26;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
}

.recognition-result-list__count {
  padding: 8px 12px;
  border-radius: 999px;
  background: #eff8d6;
  color: #62772b;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.recognition-result-list__items {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;

  li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto 34px;
    align-items: center;
    gap: 12px;
    min-height: 48px;
    padding: 0 12px;
    border: 1px solid rgba(121, 82, 45, 0.1);
    border-radius: 14px;
    background: #fffaf1;
  }

  strong {
    color: #62772b;
    font-size: 13px;
    white-space: nowrap;
  }
}

.recognition-result-list__name {
  min-width: 0;
  overflow: hidden;
  color: #3a2a1d;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recognition-result-list__image-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: #9b5f2d;

  &:hover,
  &:focus-visible {
    background: #fff0cf;
    color: #e96d3b;
    outline: none;
  }

  svg {
    width: 17px;
    height: 17px;
    fill: none;
    stroke: currentcolor;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-width: 1.9;
  }
}

@media (max-width: 640px) {
  .recognition-result-list__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .recognition-result-list__items li {
    grid-template-columns: minmax(0, 1fr) 34px;
    padding: 10px 12px;

    strong {
      grid-column: 1;
    }

    .recognition-result-list__image-link {
      grid-column: 2;
      grid-row: 1 / span 2;
    }
  }
}
</style>
