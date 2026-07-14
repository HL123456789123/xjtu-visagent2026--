export function normalizeIngredientKey(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
}

export function mapCandidatesToEditableIngredients(candidates = []) {
  return candidates.map((candidate, index) => ({
    draftId: candidate.id || `${candidate.key || 'ingredient'}_${index}`,
    key: candidate.key || normalizeIngredientKey(candidate.name),
    name: candidate.name || '',
    confidence: typeof candidate.confidence === 'number' ? candidate.confidence : null,
    source: candidate.source || 'model',
    bbox: candidate.bbox || null,
  }))
}

export function buildConfirmedIngredients(ingredients = []) {
  return ingredients.map((ingredient) => {
    const name = String(ingredient.name || '').trim()
    return {
      key: ingredient.key || normalizeIngredientKey(name),
      name,
      confidence: ingredient.confidence,
      source: ingredient.source || 'manual',
    }
  })
}

export function validateConfirmedIngredients(ingredients = []) {
  const errors = []
  const confirmed = buildConfirmedIngredients(ingredients)

  if (confirmed.length === 0) {
    errors.push('至少保留一个食材后再确认。')
  }

  const seenKeys = new Map()
  confirmed.forEach((ingredient, index) => {
    if (!ingredient.name) {
      errors.push(`第 ${index + 1} 个食材名称不能为空。`)
      return
    }

    const key = normalizeIngredientKey(ingredient.key || ingredient.name)
    if (!key) {
      errors.push(`第 ${index + 1} 个食材 key 不能为空。`)
      return
    }

    if (seenKeys.has(key)) {
      errors.push(`食材 key 重复：${key}`)
    } else {
      seenKeys.set(key, true)
    }
  })

  return {
    valid: errors.length === 0,
    errors,
    ingredients: confirmed,
  }
}
