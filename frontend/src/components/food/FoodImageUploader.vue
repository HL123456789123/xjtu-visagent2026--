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
        <div
          v-for="(preview, index) in previewUrls"
          :key="preview.file.name || preview.url"
          class="food-uploader__preview"
        >
          <img :src="preview.url" :alt="preview.file.name" />
          <button
            class="food-uploader__preview-remove"
            type="button"
            :disabled="disabled"
            :aria-label="`删除第 ${index + 1} 张图片`"
            title="删除图片"
            data-testid="food-image-remove"
            @click.stop="removeSelectedFile(index)"
          >
            ×
          </button>
        </div>
      </div>
      <div v-else class="food-uploader__placeholder">
        <span class="food-uploader__icon">+</span>
        <strong>把餐桌照片放到这里</strong>
        <span>
          支持 1 至 {{ maxFiles }} 张 JPG / JPEG / PNG，单图不超过 {{ maxSizeMB }} MB，整批不超过
          {{ maxBatchSizeMB }} MB
        </span>
        <small>点击选择，或直接拖拽图片上传</small>
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
        清空
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
  maxFiles: {
    type: Number,
    default: 5,
  },
  maxBatchSizeMB: {
    type: Number,
    default: 50,
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
const maxBatchSizeBytes = computed(() => props.maxBatchSizeMB * 1024 * 1024)

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
  if (files.length > props.maxFiles) return `每次最多上传 ${props.maxFiles} 张图片。`
  const totalSize = files.reduce((sum, file) => sum + (file.size || 0), 0)
  if (totalSize > maxBatchSizeBytes.value) return `整批图片大小不能超过 ${props.maxBatchSizeMB} MB。`
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

function removeSelectedFile(index) {
  if (props.disabled) return
  const nextFiles = selectedFiles.value.filter((_, fileIndex) => fileIndex !== index)
  if (nextFiles.length === 0) {
    clearSelection()
    return
  }
  selectFiles(nextFiles)
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
  removeSelectedFile,
})
</script>

<style lang="scss" scoped>
.food-uploader {
  display: grid;
  gap: 12px;

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
  min-height: 280px;
  overflow: hidden;
  border: 1.5px dashed rgba(135, 89, 50, 0.28);
  border-radius: 26px;
  background:
    radial-gradient(circle at 16% 14%, rgba(255, 205, 106, 0.34), transparent 22%),
    radial-gradient(circle at 88% 82%, rgba(121, 165, 76, 0.18), transparent 28%),
    #fffaf1;
  color: #88664d;
  cursor: pointer;
  box-shadow: inset 0 0 0 8px rgba(255, 255, 255, 0.42);
  transition: border-color 0.2s ease, background-color 0.2s ease, transform 0.2s ease;

  &:focus-visible,
  &:hover,
  .is-dragging & {
    border-color: #e96d3b;
    background:
      radial-gradient(circle at 16% 14%, rgba(255, 205, 106, 0.42), transparent 24%),
      radial-gradient(circle at 88% 82%, rgba(121, 165, 76, 0.24), transparent 30%),
      #fff3da;
    transform: translateY(-2px);
    outline: none;
  }
}

.food-uploader__placeholder {
  display: grid;
  justify-items: center;
  gap: 7px;
  padding: 28px;
  text-align: center;

  strong {
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 23px;
    font-weight: 500;
  }

  span {
    font-size: 13px;
  }

  small {
    color: #b56a26;
    font-size: 12px;
    font-weight: 700;
  }
}

.food-uploader__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  margin-bottom: 4px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f7c864, #e96d3b);
  color: #fffaf0;
  box-shadow: 0 14px 28px rgba(229, 109, 59, 0.26);
  font-size: 34px;
  font-weight: 300;
}

.food-uploader__preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
  height: 280px;
  padding: 10px;
  box-sizing: border-box;
  overflow: hidden;

  &.is-single {
    grid-template-columns: 1fr;
  }
}

.food-uploader__preview {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border-radius: 20px;
  box-shadow: 0 12px 28px rgba(82, 48, 24, 0.16);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    background: #2e2116;
  }
}

.food-uploader__preview-remove {
  position: absolute;
  top: $spacing-xs;
  right: $spacing-xs;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: 1px solid rgb(255 255 255 / 75%);
  border-radius: 50%;
  background: rgb(17 24 39 / 72%);
  color: #fff;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
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
  color: #6f5038;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.food-uploader__clear {
  border: 1px solid rgba(135, 89, 50, 0.18);
  border-radius: 999px;
  background: #fff8ea;
  color: #8a4d2a;
  height: 32px;
  padding: 0 $spacing-md;
  cursor: pointer;
}

.food-uploader__error {
  margin: 0;
  color: #c44b37;
  font-size: 13px;
}
</style>
