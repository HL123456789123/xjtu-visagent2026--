<template>
  <section v-if="images.length" class="recognition-result-gallery" data-testid="recognition-result-gallery">
    <header class="recognition-result-gallery__header">
      <div>
        <span class="recognition-result-gallery__kicker">识别结果</span>
        <h2>每张图片的食材和置信度</h2>
        <p>识别结果与原图一一对应；置信度越高，模型判断越可靠。</p>
      </div>
      <span class="recognition-result-gallery__count">{{ images.length }} 张图片</span>
    </header>

    <div class="recognition-result-gallery__grid">
      <article
        v-for="image in images"
        :key="`${image.image_index}-${image.image_url}`"
        class="recognition-result-gallery__card"
        data-testid="recognition-image-card"
      >
        <div class="recognition-result-gallery__image-wrap">
          <img
            v-if="image.image_url && !failedImages.has(image.image_index)"
            :src="image.image_url"
            :alt="`第 ${image.image_index + 1} 张识别图片`"
            @error="markImageFailed(image.image_index)"
          />
          <div v-else class="recognition-result-gallery__image-fallback">原图暂时无法加载</div>
          <span class="recognition-result-gallery__image-index">图 {{ image.image_index + 1 }}</span>
        </div>

        <div class="recognition-result-gallery__content">
          <header>
            <strong>识别到 {{ image.ingredients.length }} 项食材</strong>
            <span>{{ image.ingredients.length ? '模型候选项' : '未检测到食材' }}</span>
          </header>
          <ul v-if="image.ingredients.length" class="recognition-result-gallery__ingredients">
            <li v-for="ingredient in image.ingredients" :key="ingredient.candidate_id">
              <span>{{ ingredient.display_name || ingredient.class_name || '未命名食材' }}</span>
              <strong data-testid="recognition-image-confidence">
                置信度 {{ formatConfidence(ingredient.confidence) }}
              </strong>
            </li>
          </ul>
          <p v-else class="recognition-result-gallery__empty">可以在下方手动补充食材。</p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  images: {
    type: Array,
    default: () => [],
  },
})

const failedImages = ref(new Set())

function markImageFailed(imageIndex) {
  failedImages.value = new Set([...failedImages.value, imageIndex])
}

function formatConfidence(value) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}
</script>

<style lang="scss" scoped>
.recognition-result-gallery {
  display: grid;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(121, 82, 45, 0.12);
}

.recognition-result-gallery__header {
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

.recognition-result-gallery__kicker {
  color: #b56a26;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
}

.recognition-result-gallery__count,
.recognition-result-gallery__image-index {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.recognition-result-gallery__count {
  padding: 8px 12px;
  background: #eff8d6;
  color: #62772b;
  white-space: nowrap;
}

.recognition-result-gallery__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 16px;
}

.recognition-result-gallery__card {
  overflow: hidden;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 20px;
  background: #fffdf8;
  box-shadow: 0 10px 24px rgba(102, 68, 35, 0.07);
}

.recognition-result-gallery__image-wrap {
  position: relative;
  height: 160px;
  overflow: hidden;
  background: #f4eadc;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.recognition-result-gallery__image-fallback {
  display: grid;
  height: 100%;
  place-items: center;
  color: #8a6a50;
  font-size: 13px;
}

.recognition-result-gallery__image-index {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 6px 10px;
  background: rgb(255 253 248 / 88%);
  color: #6f4528;
  box-shadow: 0 4px 12px rgb(58 42 29 / 14%);
}

.recognition-result-gallery__content {
  padding: 14px;

  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;

    strong {
      color: #3a2a1d;
      font-size: 14px;
    }

    span {
      color: #9a7659;
      font-size: 12px;
    }
  }
}

.recognition-result-gallery__ingredients {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 10px;
    background: #fff5df;
    color: #65442d;
    font-size: 13px;
  }

  strong {
    color: #62772b;
    font-size: 12px;
    white-space: nowrap;
  }
}

.recognition-result-gallery__empty {
  margin: 12px 0 0;
  color: #8a6a50;
  font-size: 13px;
}

@media (max-width: 640px) {
  .recognition-result-gallery__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
