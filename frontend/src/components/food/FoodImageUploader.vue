<template>
  <section class="food-uploader" :class="{ 'is-dragging': dragging, 'is-disabled': disabled }">
    <input
      ref="fileInputRef"
      class="food-uploader__input"
      type="file"
      accept="image/jpeg,image/png"
      :disabled="disabled"
      data-testid="food-image-input"
      @change="handleNativeFile"
    />

    <div
      class="food-uploader__dropzone"
      tabindex="0"
      role="button"
      data-testid="food-image-dropzone"
      @click="openFileDialog"
      @keydown.enter.prevent="openFileDialog"
      @keydown.space.prevent="openFileDialog"
      @dragenter.prevent="dragging = true"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="handleDrop"
    >
      <div v-if="previewUrl" class="food-uploader__preview">
        <img :src="previewUrl" :alt="selectedName" />
      </div>
      <div v-else class="food-uploader__placeholder">
        <strong>选择食物图片</strong>
        <span>JPG / PNG，单图不超过 {{ maxSizeMB }} MB</span>
      </div>
    </div>

    <div class="food-uploader__footer">
      <span class="food-uploader__name" data-testid="food-image-name">
        {{ selectedName || '未选择图片' }}
      </span>
      <button
        v-if="previewUrl"
        class="food-uploader__clear"
        type="button"
        :disabled="disabled"
        data-testid="food-image-clear"
        @click="clearSelection"
      >
        清除
      </button>
    </div>

    <p v-if="validationMessage" class="food-uploader__error" data-testid="food-image-error">
      {{ validationMessage }}
    </p>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: File,
    default: null,
  },
  maxSizeMB: {
    type: Number,
    default: 10,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:modelValue',
  'selected',
  'preview-change',
  'validation-error',
  'cleared',
])

const fileInputRef = ref(null)
const previewUrl = ref('')
const validationMessage = ref('')
const dragging = ref(false)

const selectedName = computed(() => props.modelValue?.name || '')
const maxSizeBytes = computed(() => props.maxSizeMB * 1024 * 1024)

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
    emit('preview-change', '')
  }
}

function setValidationError(message) {
  validationMessage.value = message
  emit('validation-error', message)
}

function validateFile(file) {
  if (!file) return '请选择一张图片。'
  if (!['image/jpeg', 'image/png'].includes(file.type)) {
    return '仅支持 JPG 或 PNG 图片。'
  }
  if (file.size > maxSizeBytes.value) {
    return `图片大小建议不超过 ${props.maxSizeMB} MB。`
  }
  return ''
}

function selectFile(file) {
  const error = validateFile(file)
  if (error) {
    emit('update:modelValue', null)
    revokePreview()
    setValidationError(error)
    return false
  }

  validationMessage.value = ''
  revokePreview()
  previewUrl.value = URL.createObjectURL(file)
  emit('update:modelValue', file)
  emit('selected', file)
  emit('preview-change', previewUrl.value)
  return true
}

function handleNativeFile(event) {
  const [file] = Array.from(event.target.files || [])
  selectFile(file)
  event.target.value = ''
}

function handleDrop(event) {
  dragging.value = false
  if (props.disabled) return
  const files = Array.from(event.dataTransfer?.files || [])
  if (files.length > 1) {
    emit('update:modelValue', null)
    revokePreview()
    setValidationError('一次只能上传一张图片。')
    return
  }
  const [file] = files
  selectFile(file)
}

function openFileDialog() {
  if (props.disabled) return
  fileInputRef.value?.click()
}

function clearSelection() {
  emit('update:modelValue', null)
  revokePreview()
  validationMessage.value = ''
  emit('cleared')
}

watch(
  () => props.modelValue,
  (file) => {
    if (!file) {
      revokePreview()
    }
  }
)

onBeforeUnmount(() => {
  revokePreview()
})

defineExpose({
  validateFile,
  selectFile,
  clearSelection,
})
</script>

<style lang="scss" scoped>
.food-uploader {
  display: grid;
  gap: $spacing-sm;

  &.is-disabled {
    opacity: 0.72;
    pointer-events: none;
  }
}

.food-uploader__input {
  display: none;
}

.food-uploader__dropzone {
  display: grid;
  place-items: center;
  min-height: 260px;
  border: 1px dashed #b8c0cc;
  border-radius: $border-radius-md;
  background: #f8fafc;
  color: $text-secondary;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;

  &:focus-visible,
  &:hover,
  .is-dragging & {
    border-color: $primary-color;
    background: #eef6ff;
    outline: none;
  }
}

.food-uploader__placeholder {
  display: grid;
  gap: $spacing-xs;
  text-align: center;

  strong {
    color: $text-primary;
    font-size: 16px;
  }

  span {
    font-size: 13px;
  }
}

.food-uploader__preview {
  width: 100%;
  height: 260px;
  overflow: hidden;
  border-radius: $border-radius-sm;

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    background: #111827;
  }
}

.food-uploader__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  gap: $spacing-md;
}

.food-uploader__name {
  min-width: 0;
  color: $text-regular;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.food-uploader__clear {
  border: 1px solid $border-color-light;
  border-radius: $border-radius-sm;
  background: #fff;
  color: $text-regular;
  height: 32px;
  padding: 0 $spacing-md;
  cursor: pointer;
}

.food-uploader__error {
  margin: 0;
  color: $danger-color;
  font-size: 13px;
}
</style>
