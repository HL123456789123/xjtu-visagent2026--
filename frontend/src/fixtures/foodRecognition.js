export const foodRecognitionSuccessFixture = Object.freeze({
  recognition_id: 'rec_mock_day1_001',
  status: 'recognized',
  provider: 'mock',
  model_version: 'mock-food-v1',
  image_url: '',
  created_at: '2026-07-14T10:00:00+08:00',
  ingredients: [
    {
      id: 'cand_tomato_01',
      key: 'tomato',
      name: '番茄',
      confidence: 0.94,
      source: 'model',
      bbox: [92, 116, 238, 280],
    },
    {
      id: 'cand_egg_01',
      key: 'egg',
      name: '鸡蛋',
      confidence: 0.89,
      source: 'model',
      bbox: [268, 144, 386, 262],
    },
    {
      id: 'cand_spinach_01',
      key: 'spinach',
      name: '菠菜',
      confidence: 0.82,
      source: 'model',
      bbox: [408, 98, 588, 292],
    },
  ],
})

export const foodRecognitionEmptyFixture = Object.freeze({
  recognition_id: 'rec_mock_day1_empty',
  status: 'recognized',
  provider: 'mock',
  model_version: 'mock-food-v1',
  image_url: '',
  created_at: '2026-07-14T10:00:00+08:00',
  ingredients: [],
})

export const foodRecognitionFixtures = Object.freeze({
  success: foodRecognitionSuccessFixture,
  empty: foodRecognitionEmptyFixture,
})

export const foodRecognitionErrorFixtures = Object.freeze({
  401: {
    status: 401,
    message: '登录已过期，请重新登录后再识别。',
    code: 'UNAUTHORIZED',
  },
  422: {
    status: 422,
    message: '图片格式或参数校验未通过，请重新选择 JPG/PNG 图片。',
    code: 'VALIDATION_ERROR',
  },
  503: {
    status: 503,
    message: '食物识别服务暂不可用，请稍后重试或切换 Mock。',
    code: 'MODEL_UNAVAILABLE',
  },
})
