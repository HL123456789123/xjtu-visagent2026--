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

export function buildXiaohongshuShareParts(recipe = {}) {
  const recipeTitle = text(recipe.title) || '今日家常菜'
  const title = `超简单${recipeTitle}，学会你也是大厨 🍳`
  const summary = text(recipe.summary)
  const ingredients = (recipe.ingredients || []).map(formatIngredient).filter(Boolean)
  const steps = (recipe.steps || []).map(formatStep).filter(Boolean)
  const servings = Number(recipe.servings) > 0 ? `适合 ${recipe.servings} 人` : ''
  const duration = Number(recipe.cooking_time_minutes) > 0 ? `约 ${recipe.cooking_time_minutes} 分钟` : ''
  const meta = [servings, duration, text(recipe.difficulty)].filter(Boolean).join(' | ')
  const tags = ['#今日菜谱', '#家常菜', '#下饭菜', '#新手学做菜', `#${recipeTitle.replace(/\s+/g, '')}`].join(' ')

  const body = [
    `今天安排${recipeTitle}，真的嘎嘎下饭 😋`,
    summary,
    meta ? `👩‍🍳 ${meta}，厨房新手也能轻松安排` : '',
    ingredients.length ? `🥬 食材准备\n${ingredients.map((item) => `- ${item}`).join('\n')}` : '',
    steps.length ? `🍳 做法\n${steps.join('\n')}` : '',
    '一口下去太满足啦，生活不仅要吃甜头，也要记得好好吃饭～',
  ]
    .filter(Boolean)
    .join('\n\n')

  return { title, body, tags }
}

export function buildXiaohongshuShareDraft(recipe = {}) {
  const { title, body, tags } = buildXiaohongshuShareParts(recipe)
  return [title, body, tags].filter(Boolean).join('\n\n')
}
