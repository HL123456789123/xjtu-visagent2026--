import success from './food_recognition_success.json'
import empty from './food_recognition_empty.json'

export const foodRecognitionSuccessFixture = Object.freeze(success)
export const foodRecognitionEmptyFixture = Object.freeze(empty)

export const foodRecognitionFixtures = Object.freeze({ success, empty })

export const foodRecognitionErrorFixtures = Object.freeze({
  401: { status: 401, message: '登录已过期，请重新登录后再识别。', code: 'UNAUTHORIZED' },
  413: { status: 413, message: '单张图片不能超过 10 MB，整批不能超过 50 MB。', code: 'IMAGE_BATCH_TOO_LARGE' },
  415: { status: 415, message: '仅支持 JPG、JPEG 或 PNG 图片。', code: 'UNSUPPORTED_IMAGE_TYPE' },
  422: { status: 422, message: '图片内容或参数校验未通过。', code: 'INVALID_IMAGE_CONTENT' },
  503: { status: 503, message: '食物识别服务暂不可用，请稍后重试。', code: 'FOOD_MODEL_UNAVAILABLE' },
  network: { status: 0, message: '网络连接失败，请检查后端 Mock 服务是否已启动。', code: 'NETWORK_ERROR' },
})
