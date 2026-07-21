import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FoodWorkflowHeader from '../FoodWorkflowHeader.vue'

describe('FoodWorkflowHeader', () => {
  it('将识别和确认合并为第一阶段，并在确认后开放第二阶段', async () => {
    const wrapper = mount(FoodWorkflowHeader, {
      props: {
        workflowState: 'recognized',
        activeStage: 'recognize',
        canEnterRecipe: false,
      },
    })

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请确认食材')
    expect(wrapper.find('[data-testid="workflow-step-recognize"]').text()).toContain('图像识别与食材确认')
    expect(wrapper.find('[data-testid="workflow-step-recipe"]').text()).toContain('菜谱生成与智能对话')
    expect(wrapper.find('[data-testid="workflow-step-recipe"]').attributes('disabled')).toBeDefined()

    await wrapper.setProps({
      workflowState: 'confirmed',
      activeStage: 'recipe',
      canEnterRecipe: true,
    })

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('可以生成菜谱啦～')
    expect(wrapper.find('[data-testid="workflow-step-recipe"]').classes()).toContain('is-active')
    expect(wrapper.find('[data-testid="workflow-step-recipe"]').attributes('disabled')).toBeUndefined()
  })

  it('点击可用阶段时向页面请求切换', async () => {
    const wrapper = mount(FoodWorkflowHeader, {
      props: {
        workflowState: 'confirmed',
        activeStage: 'recognize',
        canEnterRecipe: true,
      },
    })

    await wrapper.find('[data-testid="workflow-step-recipe"]').trigger('click')
    expect(wrapper.emitted('stage-change')?.[0]).toEqual(['recipe'])
  })

  it('未知状态使用安全的准备中文案', () => {
    const wrapper = mount(FoodWorkflowHeader, {
      props: { workflowState: 'unknown' },
    })

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('准备中')
  })
})
