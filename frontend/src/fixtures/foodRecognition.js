import success from './food_recognition_success.json'
import empty from './food_recognition_empty.json'

export const foodRecognitionSuccessFixture = Object.freeze(success)
export const foodRecognitionEmptyFixture = Object.freeze(empty)

export const foodRecognitionFixtures = Object.freeze({ success, empty })

export const foodRecognitionErrorFixtures = Object.freeze({
  401: { status: 401, message: '登录已过期，请重新登录后再识别。', code: 'UNAUTHORIZED' },
  422: { status: 422, message: '图片或参数校验未通过。', code: 'EMPTY_INGREDIENTS' },
  503: { status: 503, message: '食物识别服务暂不可用，请稍后重试。', code: 'FOOD_MODEL_UNAVAILABLE' },
})
