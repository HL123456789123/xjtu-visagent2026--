<template>
  <div class="chat-page">
    <!-- 左侧会话列表 -->
    <div class="session-list">
      <div class="session-header">
        <h3>对话会话</h3>
        <el-button type="primary" size="small" @click="createSession">
          <el-icon><Plus /></el-icon>新建会话
        </el-button>
      </div>
      <div class="session-items">
        <div
          v-for="session in sessions"
          :key="session.id"
          :class="['session-item', { active: currentSession?.id === session.id }]"
          @click="selectSession(session)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span class="session-title">{{ session.title || '新对话' }}</span>
          <el-button
            type="danger"
            size="small"
            link
            @click.stop="deleteSession(session.id)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 右侧对话区域 -->
    <div class="chat-container">
      <!-- 对话头部 -->
      <div class="chat-header">
        <h3>{{ currentSession?.title || '智能对话' }}</h3>
        <span class="session-info">
          基于 LangGraph 多Agent 协作
        </span>
      </div>

      <!-- 消息列表 -->
      <div class="message-list" ref="messageListRef">
        <div v-if="messages.length === 0" class="empty-state">
          <el-icon :size="64"><ChatDotRound /></el-icon>
          <p>开始新的对话</p>
          <p class="hint">输入问题，智能助手将为您解答</p>
        </div>
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message-item', msg.role]"
        >
          <!-- AI 头像 -->
          <div v-if="msg.role === 'assistant'" class="avatar ai-avatar">
            <el-icon><Monitor /></el-icon>
          </div>
          <!-- 消息内容 -->
          <div class="message-content">
            <!-- 消息文本 -->
            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
            <!-- 时间 -->
            <div class="message-time">{{ formatTime(msg.created_at) }}</div>
          </div>
          <!-- 用户头像 -->
          <div v-if="msg.role === 'user'" class="avatar user-avatar">
            <el-icon><User /></el-icon>
          </div>
        </div>
        <!-- 加载状态 -->
        <div v-if="loading" class="message-item assistant">
          <div class="avatar ai-avatar">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="message-content">
            <div class="loading-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 503 服务不可用提示 (V1) -->
      <div v-if="serviceUnavailable" class="service-unavailable-banner" data-testid="service-unavailable-banner">
        <span>智能服务暂时不可用，请稍后重试。</span>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
          @keydown.enter.exact.prevent="sendMessage"
          :disabled="loading"
        />
        <el-button
          type="primary"
          :loading="loading"
          @click="sendMessage"
          :disabled="!inputMessage.trim()"
        >
          <el-icon><Promotion /></el-icon>发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { Plus, ChatDotRound, Delete, Monitor, User, Promotion } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createChatSession,
  createSessionApi,
  getSessionsApi,
  getMessagesApi,
  deleteSessionApi,
  sendChatMessage,
} from '@/api/chat'
import { renderMarkdown } from '@/utils/markdown'
import { formatTime } from '@/utils/format'

const props = defineProps({
  recipeId: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits(['recipe-updated', 'service-unavailable'])

// 会话列表
const sessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const messageListRef = ref(null)
const serviceUnavailable = ref(false)

// 加载会话列表
async function loadSessions() {
  try {
    const res = await getSessionsApi({ page: 1, page_size: 100 })
    sessions.value = res.data?.items || []
  } catch (error) {
    console.error('加载会话列表失败:', error)
  }
}

// 创建新会话（V1: 只传 recipe_id）
async function createSession() {
  try {
    let res
    if (props.recipeId) {
      // V1: POST /api/chat/sessions 只传 recipe_id
      res = await createChatSession(props.recipeId)
    } else {
      // 兼容：无 recipeId 时使用旧版接口
      res = await createSessionApi({ title: `对话 ${sessions.value.length + 1}` })
    }
    if (res.data) {
      const session = {
        id: res.data.session_id,
        recipe_id: res.data.recipe_id,
        session_uuid: res.data.session_uuid,
        title: res.data.title || `对话 ${sessions.value.length + 1}`,
        message_count: 0,
        last_message_at: new Date().toISOString(),
        created_at: res.data.created_at || new Date().toISOString()
      }
      sessions.value.unshift(session)
      await selectSession(session)
    }
  } catch (error) {
    ElMessage.error('创建会话失败')
  }
}

// 选择会话
async function selectSession(session) {
  currentSession.value = session
  messages.value = []
  try {
    const res = await getMessagesApi(session.id, { limit: 100 })
    messages.value = res.data?.messages || []
    scrollToBottom()
  } catch (error) {
    console.error('加载消息失败:', error)
  }
}

// 删除会话
async function deleteSession(sessionId) {
  try {
    await ElMessageBox.confirm('确定删除这个会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteSessionApi(sessionId)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    if (currentSession.value?.id === sessionId) {
      currentSession.value = null
      messages.value = []
    }
    ElMessage.success('会话已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除会话失败')
    }
  }
}

// 发送消息
async function sendMessage() {
  const message = inputMessage.value.trim()
  if (!message || loading.value) return

  // 如果没有会话，先创建
  if (!currentSession.value) {
    try {
      await createSession()
      // 创建会话失败则中止
      if (!currentSession.value) return
      doSendMessage(message)
    } catch (error) {
      ElMessage.error('创建会话失败')
      return
    }
  } else {
    doSendMessage(message)
  }
}

function doSendMessage(message) {
  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: message,
    created_at: new Date().toISOString()
  })
  inputMessage.value = ''
  loading.value = true
  serviceUnavailable.value = false
  scrollToBottom()

  // V1: POST /api/chat/sessions/{session_id}/messages
  // 请求体只传 content，SSE 只解析 token/recipe_updated/done/error
  const stop = sendChatMessage(
    currentSession.value.id,
    message,
    {
      onToken: (payload) => {
        // token 事件: {"content":"..."}
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg?.role === 'assistant') {
          lastMsg.content += payload.content
        } else {
          messages.value.push({
            role: 'assistant',
            content: payload.content,
            created_at: new Date().toISOString()
          })
        }
        scrollToBottom()
      },
      onRecipeUpdated: (payload) => {
        // recipe_updated 事件: {"recipe_id":101,"version":2}
        // 受控刷新：emit 事件交由父组件决策是否重新 GET
        emit('recipe-updated', {
          recipe_id: payload.recipe_id,
          version: payload.version,
        })
      },
      onDone: () => {
        loading.value = false
      },
      onError: (payload) => {
        loading.value = false
        // 503 / LLM_UNAVAILABLE
        if (payload?.code === 'LLM_UNAVAILABLE' || payload?.code === 'HTTP_ERROR') {
          serviceUnavailable.value = true
          emit('service-unavailable', payload)
          ElMessage.error(payload.message || '智能服务暂时不可用')
        } else {
          ElMessage.error(payload?.message || '处理消息时出现错误')
        }
      },
    }
  )
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 使用公共的 formatTime 函数

// 监听消息变化，自动滚动
watch(messages, () => {
  scrollToBottom()
}, { deep: true })

onMounted(() => {
  loadSessions()
})
</script>

<style lang="scss" scoped>
.chat-page {
  display: flex;
  height: calc(100vh - #{$header-height} - 40px);
  background: $bg-color;
}

.session-list {
  width: 280px;
  background: $bg-color-white;
  border-right: 1px solid $border-color;
  display: flex;
  flex-direction: column;

  .session-header {
    padding: $spacing-md;
    border-bottom: 1px solid $border-color;
    display: flex;
    justify-content: space-between;
    align-items: center;

    h3 {
      margin: 0;
      font-size: 16px;
      color: $text-primary;
    }
  }

  .session-items {
    flex: 1;
    overflow-y: auto;
    padding: $spacing-sm;
  }

  .session-item {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    padding: $spacing-sm $spacing-md;
    border-radius: $border-radius-md;
    cursor: pointer;
    transition: background 0.2s;

    &:hover {
      background: $bg-color;
    }

    &.active {
      background: $bg-color-light-blue;
      color: $primary-color;
    }

    .session-title {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: $bg-color-white;
}

.chat-header {
  padding: $spacing-md $spacing-lg;
  border-bottom: 1px solid $border-color;

  h3 {
    margin: 0;
    font-size: 18px;
    color: $text-primary;
  }

  .session-info {
    font-size: 12px;
    color: $text-secondary;
  }
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-lg;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: $text-secondary;

  p {
    margin: $spacing-md 0 0;
    font-size: 16px;
  }

  .hint {
    font-size: 14px;
    color: $text-placeholder;
  }
}

.message-item {
  display: flex;
  gap: $spacing-md;
  margin-bottom: $spacing-lg;

  &.user {
    justify-content: flex-end;

    .message-content {
      background: $primary-color;
      color: $bg-color-white;
      border-radius: $border-radius-lg $border-radius-lg 0 $border-radius-lg;
    }
  }

  &.assistant {
    justify-content: flex-start;

    .message-content {
      background: $bg-color;
      color: $text-primary;
      border-radius: $border-radius-lg $border-radius-lg $border-radius-lg 0;
    }
  }
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.ai-avatar {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: $bg-color-white;
  }

  &.user-avatar {
    background: $primary-color;
    color: $bg-color-white;
  }
}

.message-content {
  max-width: 70%;
  padding: $spacing-md;

  .message-text {
    line-height: 1.6;
    word-break: break-word;

    :deep(p) {
      margin: 0 0 $spacing-sm;
    }

    :deep(code) {
      background: rgba(0, 0, 0, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
    }

    :deep(pre) {
      background: $code-bg;
      color: $code-text;
      padding: $spacing-md;
      border-radius: $border-radius-md;
      overflow-x: auto;
    }
  }

  .message-time {
    font-size: 12px;
    color: $text-secondary;
    margin-top: $spacing-xs;
  }
}

.loading-dots {
  display: flex;
  gap: 6px;
  padding: $spacing-sm;

  span {
    width: 8px;
    height: 8px;
    background: $text-secondary;
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;

    &:nth-child(1) { animation-delay: -0.32s; }
    &:nth-child(2) { animation-delay: -0.16s; }
  }
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.service-unavailable-banner {
  padding: $spacing-md $spacing-lg;
  border-top: 1px solid #ffd3cc;
  background: #fff7f6;
  color: $danger-color;
  font-size: 14px;
  text-align: center;
}

.input-area {
  padding: $spacing-md $spacing-lg;
  border-top: 1px solid $border-color;
  display: flex;
  gap: $spacing-md;

  .el-input {
    flex: 1;
  }

  .el-button {
    align-self: flex-end;
  }
}
</style>
