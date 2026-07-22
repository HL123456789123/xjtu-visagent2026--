/**
 * V1.1 IngredientCandidate (API response):
 * { candidate_id, image_index, class_name, display_name, confidence, bbox, source }
 *
 * V1 ConfirmedIngredient (confirmation request):
 * { name, class_name, quantity, unit, source }
 */

function candidateDetections(candidate) {
  if (Array.isArray(candidate.sourceDetections)) {
    return candidate.sourceDetections.map((detection) => ({ ...detection }))
  }
  if (!Number.isInteger(candidate.image_index) || !candidate.bbox) return []
  return [{
    candidate_id: candidate.candidate_id || null,
    image_index: candidate.image_index,
    confidence: typeof candidate.confidence === 'number' ? candidate.confidence : null,
    bbox: candidate.bbox,
  }]
}

function mapCandidate(candidate, index) {
  return {
    draftId: candidate.draftId || candidate.candidate_id || `candidate_${index}`,
    candidate_id: candidate.candidate_id || null,
    class_name: candidate.class_name || null,
    image_index: Number.isInteger(candidate.image_index) ? candidate.image_index : null,
    name: candidate.display_name ?? candidate.name ?? '',
    confidence: typeof candidate.confidence === 'number' ? candidate.confidence : null,
    quantity: candidate.quantity ?? 1,
    unit: candidate.unit || '个',
    source: candidate.source || 'model',
    bbox: candidate.bbox || null,
    sourceDetections: candidateDetections(candidate),
  }
}

export function mapCandidatesToEditableIngredients(candidates = []) {
  const groupedByClass = new Map()
  const ingredients = []

  candidates.forEach((candidate, index) => {
    const editable = mapCandidate(candidate, index)
    const canGroup = editable.source === 'model' && Boolean(editable.class_name)
    if (!canGroup || !groupedByClass.has(editable.class_name)) {
      ingredients.push(editable)
      if (canGroup) groupedByClass.set(editable.class_name, editable)
      return
    }

    const grouped = groupedByClass.get(editable.class_name)
    grouped.sourceDetections.push(...editable.sourceDetections)
    if ((editable.confidence ?? -1) > (grouped.confidence ?? -1)) {
      grouped.candidate_id = editable.candidate_id
      grouped.image_index = editable.image_index
      grouped.confidence = editable.confidence
      grouped.bbox = editable.bbox
    }
  })

  return ingredients
}

export function mergeConfirmedIngredientsWithCandidates(candidates = [], confirmed = []) {
  const editableCandidates = mapCandidatesToEditableIngredients(candidates)
  return confirmed.map((ingredient, index) => {
    const matched = editableCandidates.find((candidate) =>
      ingredient.class_name
        ? candidate.class_name === ingredient.class_name
        : candidate.name === ingredient.name
    )
    return {
      ...(matched || mapCandidate(ingredient, index)),
      draftId: matched?.draftId || `confirmed_${index}`,
      class_name: ingredient.class_name || matched?.class_name || null,
      name: ingredient.name,
      quantity: ingredient.quantity,
      unit: ingredient.unit,
      source: ingredient.source || matched?.source || 'manual',
    }
  })
}

export function buildConfirmedIngredients(ingredients = []) {
  return ingredients.map((ingredient) => ({
    name: String(ingredient.name || '').trim(),
    class_name: ingredient.class_name || null,
    quantity: Number(ingredient.quantity),
    unit: String(ingredient.unit || '').trim(),
    source: ingredient.source || 'manual',
  }))
}

export function validateConfirmedIngredients(ingredients = []) {
  const errors = []
  const confirmed = buildConfirmedIngredients(ingredients)
  if (confirmed.length === 0) errors.push('至少保留一个食材后再确认。')
  confirmed.forEach((ingredient, index) => {
    if (!ingredient.name) errors.push(`第 ${index + 1} 个食材名称不能为空。`)
    if (!Number.isFinite(ingredient.quantity) || ingredient.quantity <= 0) {
      errors.push(`第 ${index + 1} 个食材数量必须大于 0。`)
    }
    if (!ingredient.unit) errors.push(`第 ${index + 1} 个食材单位不能为空。`)
    if (!['model', 'manual'].includes(ingredient.source)) {
      errors.push(`第 ${index + 1} 个食材来源无效。`)
    }
  })
  return { valid: errors.length === 0, errors, ingredients: confirmed }
}
