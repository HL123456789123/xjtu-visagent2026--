<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="recipe-share-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="share-dialog-title"
    >
      <button class="recipe-share-dialog__backdrop" type="button" aria-label="关闭分享稿" @click="close"></button>
      <section class="recipe-share-dialog__panel">
        <header>
          <h2 id="share-dialog-title">小红书分享稿</h2>
          <button class="recipe-share-dialog__close" type="button" aria-label="关闭" @click="close">×</button>
        </header>

        <div class="recipe-share-dialog__content">
          <label>
            <span>标题</span>
            <input v-model="title" data-testid="xiaohongshu-title" maxlength="50" />
          </label>
          <label>
            <span>正文</span>
            <textarea v-model="body" data-testid="xiaohongshu-draft" rows="14"></textarea>
          </label>
          <label>
            <span>话题标签</span>
            <input v-model="tags" data-testid="xiaohongshu-tags" />
          </label>
        </div>

        <footer>
          <span v-if="copyState" class="recipe-share-dialog__copy-state" data-testid="xiaohongshu-copy-state">
            {{ copyState }}
          </span>
          <button class="recipe-share-dialog__secondary" type="button" @click="close">关闭</button>
          <button class="recipe-share-dialog__primary" type="button" data-testid="xiaohongshu-copy" @click="copyDraft">
            复制全部
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { buildXiaohongshuShareParts } from '@/utils/xiaohongshuShare'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  recipe: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:modelValue'])
const title = ref('')
const body = ref('')
const tags = ref('')
const copyState = ref('')
let previousOverflow = ''

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      const draft = buildXiaohongshuShareParts(props.recipe)
      title.value = draft.title
      body.value = draft.body
      tags.value = draft.tags
      copyState.value = ''
      previousOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    } else {
      restoreBodyScroll()
    }
  },
)

function restoreBodyScroll() {
  document.body.style.overflow = previousOverflow
}

function close() {
  emit('update:modelValue', false)
}

async function copyDraft() {
  const text = [title.value.trim(), body.value.trim(), tags.value.trim()].filter(Boolean).join('\n\n')
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable')
    await navigator.clipboard.writeText(text)
    copyState.value = '已复制，可以粘贴到小红书啦～'
  } catch {
    copyState.value = '复制失败，请手动选择内容复制。'
  }
}

onBeforeUnmount(restoreBodyScroll)
</script>

<style lang="scss" scoped>
.recipe-share-dialog { position: fixed; inset: 0; z-index: 3000; display: grid; place-items: center; padding: 20px; }
.recipe-share-dialog__backdrop { position: absolute; inset: 0; width: 100%; border: 0; background: rgba(50, 35, 22, 0.52); }
.recipe-share-dialog__panel { position: relative; width: min(680px, 100%); max-height: calc(100dvh - 40px); overflow: auto; border-radius: 8px; background: #fffdfa; box-shadow: 0 24px 70px rgba(57, 37, 19, 0.28); }
.recipe-share-dialog__panel > header, .recipe-share-dialog__panel > footer { display: flex; align-items: center; gap: 12px; padding: 20px 24px; }
.recipe-share-dialog__panel > header { justify-content: space-between; border-bottom: 1px solid rgba(121, 82, 45, 0.14); }
.recipe-share-dialog__panel h2 { margin: 0; color: #3a2a1d; font-size: 22px; }
.recipe-share-dialog__close { width: 32px; height: 32px; border: 0; border-radius: 50%; background: #f4eadf; color: #6c5138; cursor: pointer; font-size: 22px; line-height: 1; }
.recipe-share-dialog__content { display: grid; gap: 16px; padding: 24px; }
.recipe-share-dialog__content label { display: grid; gap: 7px; color: #6d5137; font-size: 14px; font-weight: 700; }
.recipe-share-dialog__content input, .recipe-share-dialog__content textarea { width: 100%; border: 1px solid #e5d6c5; border-radius: 6px; background: #fff; padding: 11px 12px; color: #3a2a1d; font: inherit; font-weight: 400; line-height: 1.55; }
.recipe-share-dialog__content textarea { resize: vertical; }
.recipe-share-dialog__content input:focus, .recipe-share-dialog__content textarea:focus { outline: 2px solid #edb649; outline-offset: 1px; }
.recipe-share-dialog__panel > footer { justify-content: flex-end; border-top: 1px solid rgba(121, 82, 45, 0.14); }
.recipe-share-dialog__copy-state { margin-right: auto; color: #65802e; font-size: 13px; }
.recipe-share-dialog__secondary, .recipe-share-dialog__primary { min-height: 38px; border-radius: 6px; padding: 0 16px; cursor: pointer; font: inherit; font-weight: 700; }
.recipe-share-dialog__secondary { border: 1px solid #dfcdb9; background: #fff; color: #795a3e; }
.recipe-share-dialog__primary { border: 1px solid #d95249; background: #d95249; color: #fff; }
@media (max-width: 640px) { .recipe-share-dialog { padding: 10px; } .recipe-share-dialog__panel { max-height: calc(100dvh - 20px); } .recipe-share-dialog__panel > header, .recipe-share-dialog__panel > footer, .recipe-share-dialog__content { padding-left: 16px; padding-right: 16px; } .recipe-share-dialog__panel > footer { align-items: stretch; flex-direction: column; } .recipe-share-dialog__copy-state { margin: 0; } }
</style>
