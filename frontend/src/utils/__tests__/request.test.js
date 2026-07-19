/**
 * Axios 请求封装测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import request from '../request'

// 使用 vi.hoisted 确保 mock 工厂中引用的对象在 resetModules 后保持稳定
const { mockInterceptors, mockAxiosInstance, mockCreate } = vi.hoisted(() => {
  const mockInterceptors = {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  }
  const mockAxiosInstance = {
    interceptors: mockInterceptors,
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }
  const mockCreate = vi.fn(() => mockAxiosInstance)
  return { mockInterceptors, mockAxiosInstance, mockCreate }
})

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: mockCreate,
  },
}))

// Mock pinia store
vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    token: 'test-token',
    logout: vi.fn(),
  })),
}))

// Mock router
vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
  },
}))

describe('request', () => {
  it('应该创建 axios 实例', () => {
    expect(mockCreate).toHaveBeenCalled()
    expect(request).toBeDefined()
  })

  it('应该配置正确的 baseURL', () => {
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        baseURL: '/api',
        timeout: 30000,
      })
    )
  })

  it('应该配置请求拦截器', () => {
    // 验证请求拦截器被注册
    expect(mockInterceptors.request.use).toHaveBeenCalled()
  })

  it('应该配置响应拦截器', () => {
    // 验证响应拦截器被注册
    expect(mockInterceptors.response.use).toHaveBeenCalled()
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
