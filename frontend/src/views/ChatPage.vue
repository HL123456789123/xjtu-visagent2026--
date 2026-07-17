<template>
  <section class="recipe-chat" data-testid="chat-page">
    <header class="recipe-chat__header">
      <div>
        <span>Recipe Chat</span>
        <h2>菜谱对话</h2>
      </div>
      <span class="recipe-chat__session" data-testid="session-state">
        {{ sessionId ? `会话 #${sessionId}` : '等待菜谱' }}
      </span>
    </header>

    <p v-if="!recipeId" class="recipe-chat__notice">
      请先生成菜谱，再开始对话。
    </p>
    <p v-if="serviceError" class="recipe-chat__error" data-testid="chat-error">
      {{ serviceError }}
    </p>

    <div ref="messageList" class="recipe-chat__messages" data-testid="chat-messages">
      <p v-if="messages.length === 0" class="recipe-chat__empty">
        可以询问烹饪技巧，或要求修改当前菜谱。
      </p>
      <article
        v-for="(message, index) in messages"
        :key="`${message.role}-${index}`"
        :class="['recipe-chat__message', `recipe-chat__message--${message.role}`]"
      >
        <strong>{{ message.role === 'user' ? '我' : '菜谱助手' }}</strong>
        <p>{{ message.content }}</p>
      </article>
    </div>

    <form class="recipe-chat__composer" @submit.prevent="sendMessage">
      <textarea
        v-model="draft"
        rows="3"
        maxlength="4000"
        :disabled="!recipeId || loading"
        placeholder="例如：改成三人份并且少放油"
        data-testid="chat-input"
      />
      <button
        type="submit"
        :disabled="!recipeId || !draft.trim() || loading"
        data-testid="chat-send"
      >
        {{ loading ? '处理中…' : '发送' }}
      </button>
    </form>
  </section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { createChatSession, sendChatMessage } from '@/api/chat'

const props = defineProps({
  recipeId: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['recipe-updated', 'service-unavailable'])

const sessionId = ref(null)
const sessionRecipeId = ref(null)
const messages = ref([])
const draft = ref('')
const loading = ref(false)
const serviceError = ref('')
const messageList = ref(null)
let stopStream = null
let sessionPromise = null

function scrollToBottom() {
  nextTick(() => {
    if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
  })
}

async function ensureSession() {
  if (!props.recipeId) return null
  if (sessionId.value && sessionRecipeId.value === props.recipeId) return sessionId.value
  if (sessionPromise) return sessionPromise

  sessionPromise = createChatSession(props.recipeId)
    .then((response) => {
      const createdId = response?.data?.session_id
      if (!Number.isInteger(createdId)) throw new Error('会话响应缺少整数 session_id')
      sessionId.value = createdId
      sessionRecipeId.value = props.recipeId
      return createdId
    })
    .finally(() => {
      sessionPromise = null
    })
  return sessionPromise
}

async function sendMessage() {
  const content = draft.value.trim()
  if (!content || loading.value || !props.recipeId) return

  serviceError.value = ''
  try {
    const activeSessionId = await ensureSession()
    if (!activeSessionId) return
    messages.value.push({ role: 'user', content })
    draft.value = ''
    loading.value = true
    scrollToBottom()

    stopStream = sendChatMessage(activeSessionId, content, {
      onToken(payload) {
        const text = String(payload?.content || '')
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant') last.content += text
        else messages.value.push({ role: 'assistant', content: text })
        scrollToBottom()
      },
      onRecipeUpdated(payload) {
        if (Number.isInteger(payload?.recipe_id) && Number.isInteger(payload?.version)) {
          emit('recipe-updated', payload)
        }
      },
      onDone() {
        loading.value = false
        stopStream = null
      },
      onError(payload) {
        loading.value = false
        stopStream = null
        serviceError.value = payload?.message || '智能服务暂时不可用'
        if (payload?.code === 'LLM_UNAVAILABLE') {
          emit('service-unavailable', payload)
        }
      },
    })
  } catch (error) {
    loading.value = false
    serviceError.value = error?.response?.data?.message || error?.message || '会话创建失败'
  }
}

watch(
  () => props.recipeId,
  () => {
    stopStream?.()
    stopStream = null
    sessionId.value = null
    sessionRecipeId.value = null
    messages.value = []
    serviceError.value = ''
    if (props.recipeId) ensureSession().catch((error) => {
      serviceError.value = error?.response?.data?.message || error?.message || '会话创建失败'
    })
  },
  { immediate: true },
)

onBeforeUnmount(() => stopStream?.())
</script>

<style scoped>
.recipe-chat {
  display: grid;
  gap: 16px;
  min-height: 420px;
  padding: 22px;
  border: 1px solid rgba(121, 82, 45, 0.14);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.9);
}

.recipe-chat__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.recipe-chat__header span,
.recipe-chat__session {
  color: #8b6846;
  font-size: 13px;
}

.recipe-chat__header h2 {
  margin: 4px 0 0;
  color: #3a2a1d;
}

.recipe-chat__messages {
  min-height: 230px;
  max-height: 420px;
  overflow-y: auto;
  padding: 14px;
  border-radius: 18px;
  background: #fffaf1;
}

.recipe-chat__empty,
.recipe-chat__notice {
  color: #806a55;
  text-align: center;
}

.recipe-chat__error {
  margin: 0;
  color: #c44b37;
}

.recipe-chat__message {
  max-width: 82%;
  margin: 10px 0;
  padding: 12px 14px;
  border-radius: 16px;
  background: #fff;
}

.recipe-chat__message--user {
  margin-left: auto;
  background: #f8e2bd;
}

.recipe-chat__message p {
  margin: 5px 0 0;
  white-space: pre-wrap;
}

.recipe-chat__composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
}

.recipe-chat__composer textarea {
  resize: vertical;
  padding: 12px;
  border: 1px solid rgba(121, 82, 45, 0.2);
  border-radius: 14px;
}

.recipe-chat__composer button {
  align-self: end;
  padding: 12px 20px;
  border: 0;
  border-radius: 14px;
  background: #e8783d;
  color: white;
  font-weight: 700;
}

.recipe-chat__composer button:disabled {
  opacity: 0.5;
}
</style>
