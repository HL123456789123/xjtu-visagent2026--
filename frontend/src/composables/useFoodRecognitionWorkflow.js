import { computed, ref } from 'vue'
import {
  confirmFoodIngredients,
  createFoodRecognition,
  getFoodRecognition,
  normalizeRecognitionId,
  unwrapFoodApiData,
} from '@/api/food'
import { mapCandidatesToEditableIngredients } from '@/components/food/ingredientEditorModel'

/**
 * Owns the recognition and confirmation state used by the food-to-recipe flow.
 * Recipe generation remains in the page so this composable does not couple the
 * recognition contract to the Recipe or Chat contracts.
 */
export function useFoodRecognitionWorkflow({ onConfirmed, resetRecipeFlow }) {
  const workflowState = ref('idle')
  const selectedFiles = ref([])
  const confThreshold = ref(0.25)
  const recognizedIngredients = ref([])
  const confirmedIngredients = ref([])
  const recognizedImageCount = ref(0)
  const recognitionId = ref('')
  const errorState = ref({ status: null, title: '', message: '' })
  const recognitionMeta = ref({ provider: '', modelVersion: '', task: 'detect', localization: 'object' })

  const isBusy = computed(() => workflowState.value === 'uploading' || workflowState.value === 'confirming')
  const busyText = computed(() =>
    workflowState.value === 'confirming' ? '正在确认食材...' : '正在识别食材...'
  )
  const selectedImageNames = computed(() => selectedFiles.value.map((file) => file.name))
  const selectedImageText = computed(() => {
    const count = selectedFiles.value.length
    return count <= 1 ? '图片' : `${count} 张图片`
  })

  function resetFoodRecipeFlow() {
    resetRecipeFlow?.()
  }

  function getErrorTitle(status) {
    if (status === 0) return '网络连接失败'
    if (status === 401) return '需要重新登录'
    if (status === 413) return '图片过大'
    if (status === 415) return '图片格式不支持'
    if (status === 422) return '请求校验失败'
    if (status === 503) return '识别服务不可用'
    return '识别失败'
  }

  function handleApiError(error) {
    const status = error?.response?.status ?? 0
    errorState.value = {
      status,
      title: getErrorTitle(status),
      message:
        error?.response?.data?.message ||
        error?.response?.data?.detail ||
        error?.message ||
        '网络连接失败，请检查后端服务。',
    }
    workflowState.value = 'error'
  }

  function resetRecognition() {
    recognizedIngredients.value = []
    confirmedIngredients.value = []
    recognizedImageCount.value = 0
    recognitionId.value = ''
    errorState.value = { status: null, title: '', message: '' }
    recognitionMeta.value = { provider: '', modelVersion: '', task: 'detect', localization: 'object' }
    resetFoodRecipeFlow()
    if (selectedFiles.value.length === 0) workflowState.value = 'idle'
  }

  function handleFileSelected() {
    workflowState.value = 'selecting'
    resetRecognition()
  }

  function setValidationError(message) {
    errorState.value = {
      status: 422,
      title: '图片校验失败',
      message,
    }
    workflowState.value = 'error'
  }

  function applyRecognitionResult(response) {
    const payload = unwrapFoodApiData(response)
    const nextRecognitionId = normalizeRecognitionId(payload.recognition_id)
    if (!nextRecognitionId) {
      handleApiError({
        response: {
          status: 422,
          data: { message: '识别结果缺少整数 recognition_id。' },
        },
      })
      return
    }

    recognitionId.value = nextRecognitionId
    recognitionMeta.value = {
      provider: payload.provider,
      modelVersion: payload.model_version,
      task: payload.task || 'detect',
      localization: payload.localization || 'object',
    }
    recognizedIngredients.value = mapCandidatesToEditableIngredients(payload.ingredients || [])
    confirmedIngredients.value = []
    recognizedImageCount.value = payload.images?.length || selectedFiles.value.length
    resetFoodRecipeFlow()
    workflowState.value = 'recognized'
  }

  async function startRecognition() {
    if (selectedFiles.value.length === 0) {
      setValidationError('请先选择 1 至 5 张 JPG/PNG 图片。')
      return
    }

    workflowState.value = 'uploading'
    errorState.value = { status: null, title: '', message: '' }
    try {
      const response = await createFoodRecognition(
        {
          images: selectedFiles.value,
          conf_threshold: confThreshold.value,
        },
      )
      applyRecognitionResult(response)
    } catch (error) {
      handleApiError(error)
    }
  }

  async function handleConfirm(ingredients) {
    if (!recognitionId.value) return

    workflowState.value = 'confirming'
    errorState.value = { status: null, title: '', message: '' }
    try {
      const response = await confirmFoodIngredients(recognitionId.value, ingredients)
      const payload = unwrapFoodApiData(response)
      const confirmedRecognitionId = normalizeRecognitionId(payload.recognition_id) || recognitionId.value
      const confirmed = payload.confirmed_ingredients || ingredients

      recognitionId.value = confirmedRecognitionId
      confirmedIngredients.value = confirmed
      workflowState.value = 'confirmed'
      resetFoodRecipeFlow()
      onConfirmed?.({
        recognition_id: confirmedRecognitionId,
        confirmed_ingredients: confirmed,
      })
    } catch (error) {
      handleApiError(error)
    }
  }

  async function restoreRecipe(recipe) {
    if (!recipe?.recognition_id) return

    const recognitionResponse = await getFoodRecognition(recipe.recognition_id)
    const recognition = unwrapFoodApiData(recognitionResponse)
    recognitionId.value = recognition.recognition_id
    recognitionMeta.value = {
      provider: recognition.provider,
      modelVersion: recognition.model_version,
      task: recognition.task || 'detect',
      localization: recognition.localization || 'object',
    }
    const restoredConfirmedIngredients = recognition.confirmed_ingredients || []
    recognizedIngredients.value = mapCandidatesToEditableIngredients(
      restoredConfirmedIngredients.length ? restoredConfirmedIngredients : recognition.ingredients || []
    )
    confirmedIngredients.value = restoredConfirmedIngredients
    recognizedImageCount.value = recognition.images?.length || 0
    selectedFiles.value = []
    workflowState.value = 'confirmed'
  }

  return {
    workflowState,
    selectedFiles,
    confThreshold,
    recognizedIngredients,
    confirmedIngredients,
    recognizedImageCount,
    recognitionId,
    errorState,
    recognitionMeta,
    isBusy,
    busyText,
    selectedImageNames,
    selectedImageText,
    handleApiError,
    handleConfirm,
    handleFileSelected,
    resetRecognition,
    restoreRecipe,
    setValidationError,
    startRecognition,
  }
}
