<template>
  <div v-if="modelValue" class="recipe-share-dialog" role="dialog" aria-modal="true" aria-labelledby="share-dialog-title">
    <button class="recipe-share-dialog__backdrop" type="button" aria-label="关闭分享稿" @click="close"></button>
    <section class="recipe-share-dialog__panel">
      <header>
        <div>
          <span>Recipe Share</span>
          <h2 id="share-dialog-title">小红书分享稿</h2>
        </div>
        <button class="recipe-share-dialog__close" type="button" aria-label="关闭" @click="close">×</button>
      </header>

      <div class="recipe-share-dialog__content">
        <article class="recipe-share-dialog__preview" aria-label="笔记预览">
          <span>VISAGENT | 今日下厨</span>
          <h3>{{ recipe.title || '我的今日菜谱' }}</h3>
          <p v-if="recipe.summary">{{ recipe.summary }}</p>
          <ul v-if="previewIngredients.length">
            <li v-for="ingredient in previewIngredients" :key="ingredient">{{ ingredient }}</li>
          </ul>
          <small>识别结果已由用户确认</small>
        </article>

        <label class="recipe-share-dialog__draft">
          <span>可编辑文案</span>
          <textarea v-model="draft" data-testid="xiaohongshu-draft" rows="16"></textarea>
        </label>
      </div>

      <footer>
        <span v-if="copyState" class="recipe-share-dialog__copy-state" data-testid="xiaohongshu-copy-state">{{ copyState }}</span>
        <button class="recipe-share-dialog__secondary" type="button" @click="close">稍后发布</button>
        <button class="recipe-share-dialog__primary" type="button" data-testid="xiaohongshu-copy" @click="copyDraft">复制文案</button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { buildXiaohongshuShareDraft } from '@/utils/xiaohongshuShare'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  recipe: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['update:modelValue'])

const draft = ref('')
const copyState = ref('')
const previewIngredients = computed(() =>
  (props.recipe.ingredients || [])
    .slice(0, 4)
    .map((ingredient) => String(ingredient?.name || '').trim())
    .filter(Boolean)
)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    draft.value = buildXiaohongshuShareDraft(props.recipe)
    copyState.value = ''
  }
)

function close() {
  emit('update:modelValue', false)
}

async function copyDraft() {
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable')
    await navigator.clipboard.writeText(draft.value)
    copyState.value = '文案已复制，可粘贴到小红书发布。'
  } catch {
    copyState.value = '复制失败，请手动选择文案复制。'
  }
}
</script>

<style lang="scss" scoped>
.recipe-share-dialog { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; padding: 20px; }
.recipe-share-dialog__backdrop { position: absolute; inset: 0; width: 100%; border: 0; background: rgba(50, 35, 22, 0.5); cursor: default; }
.recipe-share-dialog__panel { position: relative; width: min(760px, 100%); max-height: calc(100vh - 40px); overflow: auto; border-radius: 8px; background: #fffdfa; box-shadow: 0 24px 70px rgba(57, 37, 19, 0.28); }
.recipe-share-dialog__panel > header, .recipe-share-dialog__panel > footer { display: flex; align-items: center; gap: 12px; padding: 20px 24px; }
.recipe-share-dialog__panel > header { justify-content: space-between; border-bottom: 1px solid rgba(121, 82, 45, 0.14); }
.recipe-share-dialog__panel header span { color: #879b45; font-size: 12px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }
.recipe-share-dialog__panel h2 { margin: 4px 0 0; color: #3a2a1d; font-size: 22px; }
.recipe-share-dialog__close { width: 32px; height: 32px; border: 0; border-radius: 50%; background: #f4eadf; color: #6c5138; cursor: pointer; font-size: 22px; line-height: 1; }
.recipe-share-dialog__content { display: grid; grid-template-columns: minmax(220px, 0.8fr) minmax(0, 1.2fr); gap: 20px; padding: 24px; }
.recipe-share-dialog__preview { display: grid; align-content: start; gap: 14px; min-height: 360px; border: 1px solid #f0d89b; border-radius: 8px; background: #fff4d7; padding: 24px; color: #5a3d22; }
.recipe-share-dialog__preview > span { color: #b77328; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
.recipe-share-dialog__preview h3, .recipe-share-dialog__preview p, .recipe-share-dialog__preview ul { margin: 0; }
.recipe-share-dialog__preview h3 { font-size: 25px; line-height: 1.25; }
.recipe-share-dialog__preview p { color: #805f40; line-height: 1.6; }
.recipe-share-dialog__preview ul { display: flex; flex-wrap: wrap; gap: 8px; padding: 0; list-style: none; }
.recipe-share-dialog__preview li { border-radius: 4px; background: rgba(255, 255, 255, 0.72); padding: 5px 8px; font-size: 13px; }
.recipe-share-dialog__preview small { align-self: end; color: #8e6c4d; }
.recipe-share-dialog__draft { display: grid; gap: 8px; color: #6d5137; font-size: 14px; font-weight: 700; }
.recipe-share-dialog__draft textarea { width: 100%; resize: vertical; border: 1px solid #e5d6c5; border-radius: 8px; background: #fff; padding: 12px; color: #3a2a1d; font: inherit; font-weight: 400; line-height: 1.55; }
.recipe-share-dialog__draft textarea:focus { outline: 2px solid #edb649; outline-offset: 1px; }
.recipe-share-dialog__panel > footer { justify-content: flex-end; border-top: 1px solid rgba(121, 82, 45, 0.14); }
.recipe-share-dialog__copy-state { margin-right: auto; color: #65802e; font-size: 13px; }
.recipe-share-dialog__secondary, .recipe-share-dialog__primary { min-height: 38px; border-radius: 6px; padding: 0 16px; cursor: pointer; font: inherit; font-weight: 700; }
.recipe-share-dialog__secondary { border: 1px solid #dfcdb9; background: #fff; color: #795a3e; }
.recipe-share-dialog__primary { border: 1px solid #d95249; background: #d95249; color: #fff; }
@media (max-width: 640px) { .recipe-share-dialog__content { grid-template-columns: 1fr; } .recipe-share-dialog__preview { min-height: 220px; } .recipe-share-dialog__panel > header, .recipe-share-dialog__panel > footer, .recipe-share-dialog__content { padding-left: 16px; padding-right: 16px; } }
</style>
