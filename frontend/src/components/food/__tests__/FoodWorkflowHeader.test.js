import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FoodWorkflowHeader from '../FoodWorkflowHeader.vue'

describe('FoodWorkflowHeader', () => {
  it('展示当前流程状态并高亮对应步骤', async () => {
    const wrapper = mount(FoodWorkflowHeader, {
      props: { workflowState: 'recognized' },
    })

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('请确认食材')
    expect(wrapper.find('.food-recipe-page__step.active strong').text()).toBe('确认食材')

    await wrapper.setProps({ workflowState: 'confirmed' })

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('可以生成菜谱啦～')
    expect(wrapper.find('.food-recipe-page__step.active strong').text()).toBe('生成菜谱')
  })

  it('未知状态使用安全的准备中文案', () => {
    const wrapper = mount(FoodWorkflowHeader, {
      props: { workflowState: 'unknown' },
    })

    expect(wrapper.find('[data-testid="workflow-state"]').text()).toBe('准备中')
  })
})
