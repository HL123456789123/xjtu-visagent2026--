<template>
  <div class="food-recipe-page__toolbar">
    <div class="food-recipe-page__steps">
      <div
        v-for="step in workflowSteps"
        :key="step.key"
        class="food-recipe-page__step"
        :class="{ active: step.activeStates.includes(workflowState) }"
      >
        <span>{{ step.no }}</span>
        <strong>{{ step.title }}</strong>
      </div>
      <div class="food-recipe-page__steps-line"></div>
    </div>
    <span class="food-recipe-page__state-badge" data-testid="workflow-state">
      {{ workflowStateText }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  workflowState: {
    type: String,
    required: true,
  },
})

const workflowSteps = [
  { key: 'upload', no: '01', title: '上传图片', activeStates: ['idle', 'selecting', 'uploading'] },
  { key: 'recognize', no: '02', title: '确认食材', activeStates: ['recognized'] },
  { key: 'recipe', no: '03', title: '生成菜谱', activeStates: ['confirmed'] },
]

const workflowStateText = computed(() => ({
  idle: '等待上传',
  selecting: '图片已选好',
  uploading: '正在识别',
  recognized: '请确认食材',
  confirming: '正在保存',
  confirmed: '可以生成菜谱啦～',
  error: '请重试',
}[props.workflowState] || '准备中'))
</script>

<style lang="scss" scoped>
.food-recipe-page__toolbar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px clamp(18px, 4vw, 72px);
  border-bottom: 1px solid rgba(121, 82, 45, 0.08);
}

.food-recipe-page__steps {
  display: flex;
  align-items: center;
  gap: 0;
  position: relative;
}

.food-recipe-page__step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  border-radius: 999px;
  position: relative;
  z-index: 1;
  transition: background-color 0.25s ease;

  &.active {
    background: rgba(255, 241, 210, 0.8);

    span {
      background: #e96d3b;
      color: #fffaf0;
    }

    strong {
      color: #d76626;
    }
  }

  span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #f7db9a;
    color: #7c4c20;
    font-size: 11px;
    font-weight: 900;
    transition: background-color 0.25s ease, color 0.25s ease;
  }

  strong {
    font-size: 14px;
    font-weight: 700;
    color: #8a6a50;
    transition: color 0.25s ease;
  }
}

.food-recipe-page__steps-line {
  position: absolute;
  top: 50%;
  left: 40px;
  right: 40px;
  height: 2px;
  background: rgba(121, 82, 45, 0.12);
  transform: translateY(-50%);
  z-index: 0;
  border-radius: 1px;
}

.food-recipe-page__state-badge {
  display: none;
}

@media (max-width: 640px) {
  .food-recipe-page__toolbar {
    padding: 10px 14px;
  }
}
</style>
