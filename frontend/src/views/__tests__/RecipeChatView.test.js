/**
 * RecipeChatView 集成测试
 * Day 3 核心验证：answer 不刷新，recipe_updated 才重新 GET
 *
 * 测试场景：
 * 1. fullUpdate: 发送修改请求 → token → recipe_updated → done → RecipeCard 更新到 version=2
 * 2. answerOnly: 发送纯问答 → token → done → RecipeCard 不更新（仍为 version=1）
 * 3. error: 发送消息 → error → 显示 503 提示
 * 4. recipeVersion 标签显示
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { recipeFixtures } from '@/fixtures/recipe'

// ========== Mock ChatPage 为简化版 ==========
// 因为 ChatPage 依赖 Element Plus 等重依赖，这里用 MockChatPage 替代
const MockChatPage = {
  name: 'MockChatPage',
  props: {
    recipeId: { type: Number, default: null },
  },
  emits: ['recipe-updated', 'service-unavailable'],
  setup(props, { emit }) {
    return {
      emit,
      /** 模拟发送修改消息（触发 recipe_updated） */
      triggerFullUpdate() {
        emit('recipe-updated', { recipe_id: 101, version: 2 })
      },
      /** 模拟发送纯问答（不触发 recipe_updated） */
      triggerAnswerOnly() {
        // 不 emit recipe-updated
      },
      /** 模拟 503 错误 */
      trigger503() {
        emit('service-unavailable', { code: 'LLM_UNAVAILABLE', message: '不可用' })
      },
    }
  },
  template: `
    <div class="mock-chat" data-testid="mock-chat">
      <button data-testid="trigger-full-update" @click="triggerFullUpdate">修改菜谱</button>
      <button data-testid="trigger-answer-only" @click="triggerAnswerOnly">纯问答</button>
      <button data-testid="trigger-503" @click="trigger503">触发503</button>
    </div>
  `,
}

// ========== 测试组件 ==========
import RecipeChatView from '../RecipeChatView.vue'

/**
 * 创建带 Mock 的 RecipeChatView
 * 将 ChatPage 替换为 MockChatPage
 */
function createWrapper() {
  // 创建 mock recipe client
  // create 返回 v1 菜谱，get 总是返回 v2 菜谱（模拟 recipe_updated 后重新 GET 的场景）
  const mockClient = {
    create: vi.fn(() => Promise.resolve({
      code: 201,
      message: '菜谱生成成功',
      data: JSON.parse(JSON.stringify(recipeFixtures.success)),
    })),
    get: vi.fn(() => Promise.resolve({
      code: 200,
      message: 'success',
      data: JSON.parse(JSON.stringify(recipeFixtures.v2)),
    })),
  }

  const wrapper = mount(RecipeChatView, {
    props: {
      recognitionId: 12,
      mock: false,
      mockRecipeClient: mockClient,
    },
    global: {
      stubs: {
        ChatPage: MockChatPage,
      },
    },
  })

  return { wrapper, mockClient }
}

describe('RecipeChatView', () => {
  let wrapper, mockClient

  beforeEach(async () => {
    const result = createWrapper()
    wrapper = result.wrapper
    mockClient = result.mockClient
    // 等待初始菜谱加载完成
    await nextTick()
    await nextTick()
  })

  afterEach(() => {
    wrapper?.unmount()
  })

  // ---------- 核心测试：recipe_updated 才重新 GET ----------

  it('触发 recipe_updated 后重新 GET 并更新菜谱到 version=2', async () => {
    // 验证初始状态：version=1
    expect(wrapper.html()).toContain('版本 1')
    expect(wrapper.html()).toContain('番茄炒蛋')

    // 模拟：用户发送修改消息 → 后端返回 recipe_updated
    await wrapper.find('[data-testid="trigger-full-update"]').trigger('click')
    await nextTick()
    await nextTick()

    // 验证：应该重新 GET 了菜谱
    expect(mockClient.get).toHaveBeenCalled()
    expect(mockClient.get.mock.calls[0][0]).toBe(101) // recipe_id

    // 验证：菜谱更新到 version=2
    expect(wrapper.html()).toContain('版本 2')
    expect(wrapper.html()).toContain('少油版番茄炒蛋')
  })

  // ---------- 核心测试：answer 不刷新 ----------

  it('纯问答不触发 recipe_updated，RecipeCard 不刷新', async () => {
    // 验证初始状态
    expect(wrapper.html()).toContain('版本 1')
    expect(wrapper.html()).toContain('番茄炒蛋')

    // 记录初始 get 调用次数
    const getCallCountBefore = mockClient.get.mock.calls.length

    // 模拟：用户发送纯问答 → 后端只返回 token + done（无 recipe_updated）
    await wrapper.find('[data-testid="trigger-answer-only"]').trigger('click')
    await nextTick()

    // 验证：getRecipe 不应该被再次调用（answer 不触发刷新）
    expect(mockClient.get.mock.calls.length).toBe(getCallCountBefore)

    // 验证：菜谱仍为 version=1，标题不变
    expect(wrapper.html()).toContain('版本 1')
    expect(wrapper.html()).toContain('番茄炒蛋')
  })

  // ---------- 503 错误处理 ----------

  it('503 错误时正确触发 service-unavailable 事件', async () => {
    await wrapper.find('[data-testid="trigger-503"]').trigger('click')
    await nextTick()

    // 验证：service-unavailable 事件应该被 emit
    const emitted = wrapper.emitted('service-unavailable')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0].code).toBe('LLM_UNAVAILABLE')
  })

  // ---------- 基本结构测试 ----------

  it('渲染 RecipeCard 和 ChatPage 两个面板', async () => {
    expect(wrapper.find('[data-testid="recipe-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chat-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="mock-chat"]').exists()).toBe(true)
  })

  it('初始加载时 createRecipe 被调用', async () => {
    expect(mockClient.create).toHaveBeenCalled()
  })

  it('初始菜谱显示 version=1 和标题"番茄炒蛋"', async () => {
    expect(wrapper.html()).toContain('版本 1')
    expect(wrapper.html()).toContain('番茄炒蛋')
  })

  it('recipe-refreshed 事件在 refreshRecipe 后被 emit', async () => {
    // 触发 recipe_updated
    await wrapper.find('[data-testid="trigger-full-update"]').trigger('click')
    await nextTick()
    await nextTick()

    // 验证：recipe-refreshed 事件应该被 emit
    const emitted = wrapper.emitted('recipe-refreshed')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0].version).toBe(2)
  })

  it('recipeId 通过 props 传递给 ChatPage', async () => {
    // 验证：recipeId 应该是 101（来自 recipeFixtures.success）
    const mockChat = wrapper.findComponent(MockChatPage)
    expect(mockChat.props('recipeId')).toBe(101)
  })

  it('连续两次 recipe_updated 触发两次 GET', async () => {
    // 第一次修改
    await wrapper.find('[data-testid="trigger-full-update"]').trigger('click')
    await nextTick()
    await nextTick()

    // 第二次修改（使用不同的 recipe_id 事件 payload）
    await wrapper.find('[data-testid="trigger-full-update"]').trigger('click')
    await nextTick()
    await nextTick()

    // 验证：getRecipe 应该被调用了两次
    expect(mockClient.get.mock.calls.length).toBe(2)
  })
})
