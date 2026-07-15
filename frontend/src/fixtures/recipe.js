/**
 * V1 Recipe Canonical Fixture
 * 对应 backend/tests/fixtures/recipe_success.json
 * 字段与 api_v1.md 第六节完全一致
 */
export const recipeSuccessFixture = Object.freeze({
  recipe_id: 101,
  recognition_id: 12,
  version: 1,
  title: '番茄炒蛋',
  summary: '一道适合两人食用的家常快手菜。',
  servings: 2,
  cooking_time_minutes: 20,
  difficulty: '简单',
  ingredients: [
    { name: '番茄', amount: 2, unit: '个', note: null },
    { name: '鸡蛋', amount: 3, unit: '个', note: null },
    { name: '葱花', amount: 10, unit: '克', note: '可选' },
  ],
  steps: [
    { step_no: 1, description: '番茄洗净切块。', duration_minutes: 5 },
    { step_no: 2, description: '鸡蛋打散，加少许盐搅匀。', duration_minutes: 3 },
    { step_no: 3, description: '热锅冷油，倒入蛋液炒至凝固后盛出。', duration_minutes: 5 },
    { step_no: 4, description: '锅中余油炒番茄至出汁，放回鸡蛋翻炒，加盐调味。', duration_minutes: 7 },
  ],
  nutrition: {
    basis: 'per_serving',
    calories_kcal: 280,
    protein_g: 16.5,
    fat_g: 15.2,
    carbohydrates_g: 18.4,
  },
  nutrition_disclaimer: '营养数据由模型估算，仅供参考，不构成医疗或营养建议。',
  generator: {
    provider: 'openai_compatible',
    model: 'configured-model',
    is_mock: false,
  },
  created_at: '2026-07-14T21:40:00+08:00',
  updated_at: '2026-07-14T21:40:00+08:00',
})

/**
 * version=2 菜谱 fixture（对话修改后）
 */
export const recipeV2Fixture = Object.freeze({
  recipe_id: 101,
  recognition_id: 12,
  version: 2,
  title: '少油版番茄炒蛋',
  summary: '适合三人食用的少油版本。',
  servings: 3,
  cooking_time_minutes: 20,
  difficulty: '简单',
  ingredients: [
    { name: '番茄', amount: 3, unit: '个', note: null },
    { name: '鸡蛋', amount: 4, unit: '个', note: null },
    { name: '食用油', amount: 5, unit: '克', note: '减量' },
  ],
  steps: [
    { step_no: 1, description: '番茄洗净切块。', duration_minutes: 5 },
    { step_no: 2, description: '鸡蛋打散，加少许盐搅匀。', duration_minutes: 3 },
    { step_no: 3, description: '少量油热锅，倒入蛋液炒至刚凝固后盛出。', duration_minutes: 5 },
    { step_no: 4, description: '番茄入锅炒至出汁，放回鸡蛋翻炒，加盐调味。', duration_minutes: 7 },
  ],
  nutrition: {
    basis: 'per_serving',
    calories_kcal: 230,
    protein_g: 15,
    fat_g: 10,
    carbohydrates_g: 18,
  },
  nutrition_disclaimer: '营养数据由模型估算，仅供参考，不构成医疗或营养建议。',
  generator: {
    provider: 'openai_compatible',
    model: 'configured-model',
    is_mock: false,
  },
  created_at: '2026-07-14T21:40:00+08:00',
  updated_at: '2026-07-14T21:50:00+08:00',
})

/**
 * 空菜谱 fixture（极端边界）
 */
export const recipeEmptyFixture = Object.freeze({
  recipe_id: 0,
  recognition_id: 0,
  version: 1,
  title: '',
  summary: '',
  servings: 0,
  cooking_time_minutes: 0,
  difficulty: '',
  ingredients: [],
  steps: [],
  nutrition: {
    basis: 'per_serving',
    calories_kcal: 0,
    protein_g: 0,
    fat_g: 0,
    carbohydrates_g: 0,
  },
  nutrition_disclaimer: '营养数据由模型估算，仅供参考，不构成医疗或营养建议。',
  generator: { provider: '', model: '', is_mock: true },
  created_at: '',
  updated_at: '',
})

export const recipeFixtures = Object.freeze({
  success: recipeSuccessFixture,
  v2: recipeV2Fixture,
  empty: recipeEmptyFixture,
})

/**
 * Recipe API 错误 fixture
 */
export const recipeErrorFixtures = Object.freeze({
  404: {
    status: 404,
    code: 'RECIPE_NOT_FOUND',
    message: '菜谱不存在',
  },
  422: {
    status: 422,
    code: 'NO_CONFIRMED_INGREDIENTS',
    message: '未确认食材，请先完成食材确认。',
  },
  503: {
    status: 503,
    code: 'LLM_UNAVAILABLE',
    message: '智能服务暂时不可用',
  },
})
