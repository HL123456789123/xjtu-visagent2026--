<template>
  <div class="workflow-header">
    <div class="workflow-header__steps" aria-label="食材菜谱流程">
      <button
        v-for="step in steps"
        :key="step.key"
        type="button"
        :class="['workflow-header__step', { 'is-active': activeStage === step.key }]"
        :disabled="step.key === 'recipe' && !canEnterRecipe"
        :data-testid="`workflow-step-${step.key}`"
        @click="emit('stage-change', step.key)"
      >
        <span>{{ step.no }}</span>
        <strong>{{ step.title }}</strong>
      </button>
      <div class="workflow-header__line"></div>
    </div>
    <span class="workflow-header__state" data-testid="workflow-state">
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
  activeStage: {
    type: String,
    default: 'recognize',
  },
  canEnterRecipe: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['stage-change'])

const steps = [
  { key: 'recognize', no: '01', title: '图像识别与食材确认' },
  { key: 'recipe', no: '02', title: '菜谱生成与智能对话' },
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
.workflow-header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  min-height: 70px;
  padding: 0 clamp(18px, 4vw, 64px);
  border-bottom: 1px solid rgba(72, 82, 46, 0.14);
  background: rgba(255, 253, 247, 0.94);
}

.workflow-header__steps {
  position: relative;
  display: flex;
  align-items: center;
  width: min(760px, 100%);
}

.workflow-header__step {
  position: relative;
  z-index: 1;
  display: flex;
  width: 50%;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 46px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #81634c;
  cursor: pointer;
  font: inherit;
  transition: color 0.2s ease, background 0.2s ease;

  span {
    display: inline-flex;
    width: 30px;
    height: 30px;
    flex: 0 0 30px;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: #ecdcae;
    color: #6e572f;
    font-size: 12px;
    font-weight: 900;
  }

  strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 15px;
  }

  &:hover:not(:disabled) {
    background: #fff4d8;
  }

  &.is-active {
    background: #f7ebc6;
    color: #bd572b;

    span {
      background: #e96d3b;
      color: #fff;
    }
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.48;
  }
}

.workflow-header__line {
  position: absolute;
  top: 50%;
  right: 25%;
  left: 25%;
  height: 1px;
  background: rgba(121, 82, 45, 0.2);
  transform: translateY(-50%);
}

.workflow-header__state {
  position: absolute;
  right: clamp(18px, 4vw, 64px);
  color: #6b7d39;
  font-size: 12px;
  font-weight: 800;
}

@media (max-width: 800px) {
  .workflow-header {
    justify-content: flex-start;
    min-height: 66px;
    padding: 0 12px;
  }

  .workflow-header__steps {
    width: 100%;
  }

  .workflow-header__step {
    gap: 6px;

    strong {
      font-size: 12px;
    }
  }

  .workflow-header__state {
    display: none;
  }
}
</style>
