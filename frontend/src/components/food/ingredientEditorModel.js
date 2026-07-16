/**
 * V1.1 IngredientCandidate (API response):
 * { candidate_id, class_name, display_name, confidence, bbox, source }
 *
 * V1 ConfirmedIngredient (confirmation request):
 * { name, class_name, quantity, unit, source }
 */

export function mapCandidatesToEditableIngredients(candidates = []) {
  const groupedIngredients = new Map()

  candidates.forEach((candidate, index) => {
    const name = String(candidate.display_name ?? candidate.name ?? '').trim()
    const className = candidate.class_name || null
    const unit = String(candidate.unit || '个').trim() || '个'
    const source = candidate.source || 'model'
    const quantity = Number.isInteger(Number(candidate.quantity)) && Number(candidate.quantity) > 0
      ? Number(candidate.quantity)
      : 1
    const identity = String(className || name).trim().toLocaleLowerCase()
    const key = `${identity}|${unit.toLocaleLowerCase()}|${source}`
    const existing = groupedIngredients.get(key)

    if (existing) {
      existing.quantity += quantity
      return
    }

    groupedIngredients.set(key, {
      draftId: candidate.draftId || candidate.candidate_id || `candidate_${index}`,
      candidate_id: candidate.candidate_id || null,
      class_name: className,
      name,
      quantity,
      unit,
      source,
    })
  })

  return Array.from(groupedIngredients.values())
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
    if (!Number.isInteger(ingredient.quantity) || ingredient.quantity <= 0) {
      errors.push(`第 ${index + 1} 个食材数量必须为正整数。`)
    }
    if (!ingredient.unit) errors.push(`第 ${index + 1} 个食材单位不能为空。`)
    if (!['model', 'manual'].includes(ingredient.source)) {
      errors.push(`第 ${index + 1} 个食材来源无效。`)
    }
  })
  return { valid: errors.length === 0, errors, ingredients: confirmed }
}
