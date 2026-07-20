import { computed, ref, unref } from 'vue'
import { normalizeRecognitionId } from '@/api/food'
import {
  createRecipe,
  getRecipe,
  getRecipeVersion,
  getRecipeVersions,
  unwrapRecipeApiData,
} from '@/api/recipe'

export function useRecipeWorkflow({
  workflowState,
  recognitionId,
  confirmedIngredients,
  restoreRecognitionForRecipe,
  onRecipeRequested = () => {},
  onRestoreError = () => {},
}) {
  const generatedRecipe = ref(null)
  const recipeLoading = ref(false)
  const recipeError = ref(null)
  const recipeVersions = ref([])
  const currentRecipeVersion = ref(null)
  const selectedRecipeVersion = ref(null)
  const versionLoading = ref(false)
  const versionError = ref('')
  const avoidIngredientsText = ref('')
  const recipePreferences = ref({
    servings: 2,
    taste: '家常',
    max_time_minutes: 30,
    avoid_ingredients: [],
  })

  const showRecipeFlow = computed(
    () =>
      unref(workflowState) === 'confirmed' ||
      recipeLoading.value ||
      generatedRecipe.value ||
      recipeError.value
  )
  const isViewingHistoricalVersion = computed(() =>
    Number.isInteger(selectedRecipeVersion.value) &&
    Number.isInteger(currentRecipeVersion.value) &&
    selectedRecipeVersion.value !== currentRecipeVersion.value
  )

  function resetRecipeFlow() {
    generatedRecipe.value = null
    recipeError.value = null
    recipeLoading.value = false
    recipeVersions.value = []
    currentRecipeVersion.value = null
    selectedRecipeVersion.value = null
    versionError.value = ''
  }

  function buildRecipePreferences() {
    const avoidIngredients = avoidIngredientsText.value
      .split(/[,，、\s]+/)
      .map((item) => item.trim())
      .filter(Boolean)

    return {
      servings: Number(recipePreferences.value.servings) || 2,
      taste: recipePreferences.value.taste || '家常',
      max_time_minutes: recipePreferences.value.max_time_minutes || null,
      avoid_ingredients: avoidIngredients,
    }
  }

  function normalizeRecipeError(error) {
    const status = error?.response?.status ?? 0
    return {
      status,
      code: error?.response?.data?.code || (status === 0 ? 'NETWORK_ERROR' : undefined),
      message:
        error?.response?.data?.message ||
        error?.response?.data?.detail ||
        error?.message ||
        '菜谱生成失败，请稍后重试。',
    }
  }

  async function loadRecipeVersions(recipeId, fallbackVersion) {
    const normalizedFallback = Number(fallbackVersion) || 1
    try {
      const response = await getRecipeVersions(recipeId)
      const data = unwrapRecipeApiData(response) || {}
      const versions = Array.isArray(data.versions) ? data.versions : []
      recipeVersions.value = versions.length
        ? versions
        : [{ version: normalizedFallback, is_current: true }]
      currentRecipeVersion.value = Number(data.current_version) || normalizedFallback
    } catch {
      recipeVersions.value = [{ version: normalizedFallback, is_current: true }]
      currentRecipeVersion.value = normalizedFallback
    }
    selectedRecipeVersion.value = currentRecipeVersion.value
  }

  async function selectRecipeVersion(version) {
    const recipeId = Number(generatedRecipe.value?.recipe_id)
    const targetVersion = Number(version)
    if (!Number.isInteger(recipeId) || recipeId <= 0 || !Number.isInteger(targetVersion)) return
    if (targetVersion === selectedRecipeVersion.value) return

    versionLoading.value = true
    versionError.value = ''
    try {
      if (targetVersion === currentRecipeVersion.value) {
        const response = await getRecipe(recipeId)
        generatedRecipe.value = unwrapRecipeApiData(response)
      } else {
        const response = await getRecipeVersion(recipeId, targetVersion)
        const snapshot = unwrapRecipeApiData(response)
        generatedRecipe.value = {
          ...snapshot.recipe,
          recipe_id: recipeId,
          recognition_id: generatedRecipe.value?.recognition_id,
          version: snapshot.version,
        }
      }
      selectedRecipeVersion.value = targetVersion
    } catch (error) {
      versionError.value = normalizeRecipeError(error).message
    } finally {
      versionLoading.value = false
    }
  }

  async function generateRecipeFromRecognition(payload = {}) {
    const nextRecognitionId = normalizeRecognitionId(payload.recognition_id ?? unref(recognitionId))
    if (!nextRecognitionId) {
      recipeError.value = {
        status: 422,
        code: 'BAD_REQUEST',
        message: '当前识别记录无效，请重新识别并确认食材。',
      }
      return
    }

    const preferences = buildRecipePreferences()
    recipeLoading.value = true
    recipeError.value = null
    try {
      const response = await createRecipe({ recognition_id: nextRecognitionId, preferences })
      const recipe = unwrapRecipeApiData(response)
      generatedRecipe.value = recipe
      await loadRecipeVersions(recipe.recipe_id, recipe.version)
      onRecipeRequested({
        recognition_id: nextRecognitionId,
        preferences,
        recipe_id: recipe?.recipe_id,
        confirmed_ingredients: payload.confirmed_ingredients || unref(confirmedIngredients),
      })
    } catch (error) {
      recipeError.value = normalizeRecipeError(error)
    } finally {
      recipeLoading.value = false
    }
  }

  async function refreshGeneratedRecipe(payload = {}) {
    const recipeId = Number(payload.recipe_id ?? generatedRecipe.value?.recipe_id)
    if (!Number.isInteger(recipeId) || recipeId <= 0) return

    recipeLoading.value = true
    recipeError.value = null
    try {
      const response = await getRecipe(recipeId)
      generatedRecipe.value = unwrapRecipeApiData(response)
      await loadRecipeVersions(recipeId, generatedRecipe.value?.version)
    } catch (error) {
      recipeError.value = normalizeRecipeError(error)
    } finally {
      recipeLoading.value = false
    }
  }

  async function restoreRecipe(recipeId) {
    if (!Number.isInteger(recipeId) || recipeId <= 0) return

    recipeLoading.value = true
    recipeError.value = null
    try {
      const recipeResponse = await getRecipe(recipeId)
      const recipe = unwrapRecipeApiData(recipeResponse)
      await restoreRecognitionForRecipe(recipe)
      generatedRecipe.value = recipe
      await loadRecipeVersions(recipeId, recipe.version)
    } catch (error) {
      recipeError.value = normalizeRecipeError(error)
      onRestoreError(error)
    } finally {
      recipeLoading.value = false
    }
  }

  return {
    generatedRecipe,
    recipeLoading,
    recipeError,
    recipeVersions,
    currentRecipeVersion,
    selectedRecipeVersion,
    versionLoading,
    versionError,
    avoidIngredientsText,
    recipePreferences,
    showRecipeFlow,
    isViewingHistoricalVersion,
    generateRecipeFromRecognition,
    refreshGeneratedRecipe,
    resetRecipeFlow,
    restoreRecipe,
    selectRecipeVersion,
  }
}
