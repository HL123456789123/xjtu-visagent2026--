function text(value) {
  return String(value || '').trim()
}

function formatIngredient(ingredient) {
  const amount = ingredient?.amount ?? ingredient?.quantity
  const amountText = amount === undefined || amount === null || amount === '' ? '' : String(amount)
  return `${text(ingredient?.name)}${amountText}${text(ingredient?.unit)}`
}

function formatStep(step, index) {
  const stepNo = Number(step?.step_no) || index + 1
  return `${stepNo}. ${text(step?.description)}`
}

export function buildXiaohongshuShareDraft(recipe = {}) {
  const title = text(recipe.title) || '我的今日菜谱'
  const summary = text(recipe.summary)
  const ingredients = (recipe.ingredients || []).map(formatIngredient).filter(Boolean)
  const steps = (recipe.steps || []).map(formatStep).filter(Boolean)
  const servings = Number(recipe.servings) > 0 ? `${recipe.servings} 人份` : ''
  const duration = Number(recipe.cooking_time_minutes) > 0 ? `${recipe.cooking_time_minutes} 分钟` : ''
  const meta = [servings, duration, text(recipe.difficulty)].filter(Boolean).join(' | ')
  const tags = ['#今日菜谱', '#家常菜', `#${title.replace(/\s+/g, '')}`]

  return [
    title,
    meta,
    summary,
    ingredients.length ? `食材准备：\n${ingredients.map((item) => `- ${item}`).join('\n')}` : '',
    steps.length ? `做法：\n${steps.join('\n')}` : '',
    '食材由 VisAgent 识别后经人工确认，做饭时请按实际食材情况调整。',
    tags.join(' '),
  ]
    .filter(Boolean)
    .join('\n\n')
}
