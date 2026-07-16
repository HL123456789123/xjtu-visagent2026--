/**
 * V1.1 IngredientCandidate (API response):
 * { candidate_id, image_index, class_name, display_name, confidence, bbox, source }
 *
 * V1 ConfirmedIngredient (confirmation request):
 * { name, class_name, quantity, unit, source }
 */

export function mapCandidatesToEditableIngredients(candidates = []) {
  return candidates.map((candidate, index) => ({
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
  }))
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
