<template>
  <section class="food-uploader" :class="{ 'is-dragging': dragging, 'is-disabled': disabled }">
    <input
      ref="fileInputRef"
      class="food-uploader__input"
      type="file"
      accept="image/jpeg,image/png"
      multiple
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
      <div
        v-if="previewUrls.length"
        class="food-uploader__preview-grid"
        :class="{ 'is-single': previewUrls.length === 1 }"
      >
        <div v-for="preview in previewUrls" :key="preview.file.name || preview.url" class="food-uploader__preview">
          <img :src="preview.url" :alt="preview.file.name" />
        </div>
      </div>
      <div v-else class="food-uploader__placeholder">
        <strong>选择食物图片</strong>
        <span>支持 1 至多张 JPG / JPEG / PNG，单图不超过 {{ maxSizeMB }} MB</span>
      </div>
    </div>

    <div class="food-uploader__footer">
      <span class="food-uploader__name" data-testid="food-image-name">
        {{ selectedName || '未选择图片' }}
      </span>
      <button
        v-if="selectedFiles.length"
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
    type: Array,
    default: () => [],
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
const previewUrls = ref([])
const validationMessage = ref('')
const dragging = ref(false)

const selectedFiles = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))
const selectedName = computed(() => {
  if (selectedFiles.value.length === 1) return selectedFiles.value[0].name
  if (selectedFiles.value.length > 1) return `已选择 ${selectedFiles.value.length} 张图片`
  return ''
})
const maxSizeBytes = computed(() => props.maxSizeMB * 1024 * 1024)

function revokePreviews() {
  if (previewUrls.value.length) {
    previewUrls.value.forEach((preview) => URL.revokeObjectURL(preview.url))
    previewUrls.value = []
    emit('preview-change', [])
  }
}

function setValidationError(message) {
  validationMessage.value = message
  emit('validation-error', message)
}

function validateFile(file) {
  if (!file) return '请选择至少一张图片。'
  const extension = file.name?.split('.').pop()?.toLowerCase()
  const hasSupportedType = ['image/jpeg', 'image/png'].includes(file.type)
  const hasSupportedExtension = ['jpg', 'jpeg', 'png'].includes(extension)
  if (!hasSupportedType && !hasSupportedExtension) {
    return '仅支持 JPG、JPEG 或 PNG 图片。'
  }
  if (file.size > maxSizeBytes.value) {
    return `图片大小不能超过 ${props.maxSizeMB} MB。`
  }
  return ''
}

function validateFiles(files) {
  if (!files.length) return '请选择至少一张图片。'
  const invalidFile = files.find((file) => validateFile(file))
  if (!invalidFile) return ''
  return `${invalidFile.name}：${validateFile(invalidFile)}`
}

function createPreviewUrl(file) {
  try {
    return URL.createObjectURL(file)
  } catch {
    return ''
  }
}

function selectFiles(files) {
  const nextFiles = Array.from(files || [])
  const error = validateFiles(nextFiles)
  if (error) {
    emit('update:modelValue', [])
    revokePreviews()
    setValidationError(error)
    return false
  }

  validationMessage.value = ''
  revokePreviews()
  previewUrls.value = nextFiles.map((file) => ({
    file,
    url: createPreviewUrl(file),
  }))
  emit('update:modelValue', nextFiles)
  emit('selected', nextFiles)
  emit(
    'preview-change',
    previewUrls.value.map((preview) => preview.url)
  )
  return true
}

function selectFile(file) {
  return selectFiles(file ? [file] : [])
}

function handleNativeFile(event) {
  selectFiles(event.target.files || [])
  event.target.value = ''
}

function handleDrop(event) {
  dragging.value = false
  if (props.disabled) return
  selectFiles(event.dataTransfer?.files || [])
}

function openFileDialog() {
  if (props.disabled) return
  fileInputRef.value?.click()
}

function clearSelection() {
  emit('update:modelValue', [])
  revokePreviews()
  validationMessage.value = ''
  emit('cleared')
}

watch(
  () => props.modelValue,
  (files) => {
    if (!Array.isArray(files) || files.length === 0) {
      revokePreviews()
    }
  }
)

onBeforeUnmount(() => {
  revokePreviews()
})

defineExpose({
  validateFile,
  validateFiles,
  selectFile,
  selectFiles,
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

.food-uploader__preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $spacing-sm;
  width: 100%;
  height: 260px;
  overflow: hidden;

  &.is-single {
    grid-template-columns: 1fr;
  }
}

.food-uploader__preview {
  min-width: 0;
  min-height: 0;
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
