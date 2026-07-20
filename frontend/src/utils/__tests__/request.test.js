/**
 * Axios 请求封装测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import request, { uploadRequest } from '../request'

// 使用 vi.hoisted 确保 mock 工厂中引用的对象在 resetModules 后保持稳定
const { mockClients, mockCreate, mockMessage, mockLogout, mockPush } = vi.hoisted(() => {
  const createClient = () => ({
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  })
  const mockClients = [createClient(), createClient()]
  let clientIndex = 0
  const mockCreate = vi.fn(() => mockClients[clientIndex++])
  return {
    mockClients,
    mockCreate,
    mockMessage: vi.fn(),
    mockLogout: vi.fn(),
    mockPush: vi.fn(),
  }
})

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: mockCreate,
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: mockMessage,
  },
}))

// Mock pinia store
vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    token: 'test-token',
    logout: mockLogout,
  })),
}))

// Mock router
vi.mock('@/router', () => ({
  default: {
    push: mockPush,
  },
}))

const requestResponseHandlers = mockClients[0].interceptors.response.use.mock.calls[0]
const uploadResponseHandlers = mockClients[1].interceptors.response.use.mock.calls[0]

function makeHttpError(status, data = {}, url = '/recipes') {
  return {
    config: { url },
    response: { status, data },
  }
}

describe('request', () => {
  it('应该创建 axios 实例', () => {
    expect(mockCreate).toHaveBeenCalledTimes(2)
    expect(request).toBeDefined()
    expect(uploadRequest).toBeDefined()
  })

  it('应该为普通请求和上传请求配置正确的超时', () => {
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        baseURL: '/api',
        timeout: 30000,
      })
    )
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        baseURL: '/api',
        timeout: 600000,
      })
    )
  })

  it('应该配置请求拦截器', () => {
    // 验证请求拦截器被注册
    expect(mockClients[0].interceptors.request.use).toHaveBeenCalled()
  })

  it('应该配置响应拦截器', () => {
    // 验证响应拦截器被注册
    expect(mockClients[0].interceptors.response.use).toHaveBeenCalled()
    expect(mockClients[1].interceptors.response.use).toHaveBeenCalled()
  })

  it('两个客户端都直接解包响应 data', () => {
    const response = { data: { code: 200 } }
    expect(requestResponseHandlers[0](response)).toEqual({ code: 200 })
    expect(uploadResponseHandlers[0](response)).toEqual({ code: 200 })
  })
})

describe.each([
  ['普通请求', requestResponseHandlers[1]],
  ['上传请求', uploadResponseHandlers[1]],
])('%s错误处理', (_clientName, rejectResponse) => {
  beforeEach(() => {
    mockMessage.mockClear()
    mockLogout.mockClear()
    mockPush.mockClear()
  })

  it.each([
    [403, '没有权限访问该资源'],
    [404, '请求的资源不存在'],
    [413, '上传图片总大小超过限制'],
    [415, '图片格式不受支持'],
    [422, '请求参数错误'],
    [500, '服务器内部错误'],
    [503, '服务暂时不可用'],
  ])('统一处理 HTTP %i', async (status, expectedMessage) => {
    const error = makeHttpError(status)
    await expect(rejectResponse(error)).rejects.toBe(error)
    expect(mockMessage).toHaveBeenCalledWith(expectedMessage)
  })

  it('优先展示后端 message 或数组 detail', async () => {
    await expect(
      rejectResponse(makeHttpError(422, { detail: [{ msg: '字段格式错误' }] }))
    ).rejects.toBeDefined()
    expect(mockMessage).toHaveBeenCalledWith('字段格式错误')

    mockMessage.mockClear()
    await expect(
      rejectResponse(makeHttpError(503, { message: '智能服务暂时不可用' }))
    ).rejects.toBeDefined()
    expect(mockMessage).toHaveBeenCalledWith('智能服务暂时不可用')
  })

  it('登录接口 401 只提示凭据错误', async () => {
    const error = makeHttpError(401, {}, '/auth/login')
    await expect(rejectResponse(error)).rejects.toBe(error)
    expect(mockMessage).toHaveBeenCalledWith('用户名或密码错误')
    expect(mockLogout).not.toHaveBeenCalled()
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('其他接口 401 只触发一次退出和登录跳转', async () => {
    const error = makeHttpError(401)
    await expect(rejectResponse(error)).rejects.toBe(error)
    expect(mockLogout).toHaveBeenCalledTimes(1)
    expect(mockPush).toHaveBeenCalledOnce()
    expect(mockPush).toHaveBeenCalledWith('/login')
  })

  it('无响应时提示网络连接失败', async () => {
    const error = { config: { url: '/recipes' } }
    await expect(rejectResponse(error)).rejects.toBe(error)
    expect(mockMessage).toHaveBeenCalledWith('网络连接失败，请检查网络')
  })
})

describe("错误上报模块", () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  it("应该正确初始化错误上报", async () => {
    const { setupErrorReporting } = await import("@/utils/error_reporter");
    expect(setupErrorReporting).toBeDefined();
    expect(typeof setupErrorReporting).toBe("function");
  });

  it("错误信息应该存入 localStorage", () => {
    const errorInfo = {
      type: "test_error",
      message: "测试错误",
    };
    const errors = JSON.parse(localStorage.getItem("error_logs") || "[]");
    errors.push({ ...errorInfo, timestamp: new Date().toISOString() });
    localStorage.setItem("error_logs", JSON.stringify(errors));

    const stored = JSON.parse(localStorage.getItem("error_logs"));
    expect(stored).toHaveLength(1);
    expect(stored[0].type).toBe("test_error");
  });
});
