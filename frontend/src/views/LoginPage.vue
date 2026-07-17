<template>
  <div class="login-page">
    <section class="login-visual">
      <router-link class="login-brand" to="/login">
        <span>🍳</span>
        <strong>FridgeChef</strong>
      </router-link>
      <h1>{{ visualTitle }}</h1>
      <p>{{ visualCopy }}</p>
      <img src="/login-hero.jpg" alt="新鲜食材" />
    </section>

    <section class="login-card">
      <div class="login-header">
        <span class="login-kicker">{{ isAdminLogin ? 'Admin login' : 'Welcome back' }}</span>
        <h2>{{ isAdminLogin ? '管理者登录' : '账号登录' }}</h2>
        <p>{{ loginCopy }}</p>
      </div>

      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="loginRules"
        label-width="0"
        size="large"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="用户名"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            show-password
            @keyup.enter="handleLogin"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <span>还没有账号？</span>
        <router-link to="/register">立即注册</router-link>
      </div>
    </section>

    <button
      class="admin-toggle"
      type="button"
      :title="isAdminLogin ? '切换为用户端登录' : '切换为管理端登录'"
      @click="toggleMode"
    >
      <el-icon><component :is="isAdminLogin ? User : Setting" /></el-icon>
      <span>{{ isAdminLogin ? '用户端' : '管理端' }}</span>
    </button>
  </div>
</template>

<script setup>
import { computed, ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, Setting, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { ACCESS_MODES, isManagerPath, normalizeAccessMode } from '@/utils/accessMode'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)

const selectedMode = computed(() => normalizeAccessMode(route.query.mode || userStore.accessMode))
const isAdminLogin = computed(() => selectedMode.value === ACCESS_MODES.ADMIN)

const visualTitle = computed(() =>
  isAdminLogin.value ? '登录管理端，掌握模型训练与数据变化' : '开始你的专属美食之旅'
)
const visualCopy = computed(() =>
  isAdminLogin.value
    ? '管理者可在日常食物工作流之外，进入模型训练和数据看板。'
    : '识别食材、确认清单、生成家常食谱，把每天吃什么变得轻松一点。'
)
const loginCopy = computed(() =>
  isAdminLogin.value
    ? '请使用已开通管理者入口权限的账号登录。'
    : '输入用户名和密码即可开始使用。'
)

const loginForm = reactive({
  username: '',
  password: '',
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度在 3-50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' },
  ],
}

function getRedirectQuery() {
  const redirect = route.query.redirect
  return Array.isArray(redirect) ? redirect[0] : redirect
}

function getRedirectTarget(mode) {
  const redirect = getRedirectQuery()
  if (mode === ACCESS_MODES.ADMIN) return redirect && isManagerPath(redirect) ? redirect : '/dashboard'
  return redirect && !isManagerPath(redirect) ? redirect : '/start'
}

function toggleMode() {
  const next = isAdminLogin.value ? ACCESS_MODES.USER : ACCESS_MODES.ADMIN
  userStore.setAccessMode(next)
  router.replace({
    path: route.path,
    query: {
      ...route.query,
      mode: next,
      redirect: getRedirectTarget(next),
    },
  })
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const mode = selectedMode.value
    userStore.setAccessMode(mode)
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password,
    })

    if (mode === ACCESS_MODES.ADMIN && !userStore.canUseAdminMode) {
      await userStore.logout()
      ElMessage.error('该账号没有管理者入口权限，请联系管理员开通。')
      return
    }

    ElMessage.success(mode === ACCESS_MODES.ADMIN ? '管理者登录成功' : '登录成功')
    router.push(getRedirectTarget(mode))
  } catch {
    // 错误已在 Axios 拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  width: 100%;
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  align-items: center;
  gap: clamp(28px, 5vw, 72px);
  padding: clamp(28px, 5vw, 70px);
  padding-right: clamp(28px, 5vw, 100px);
  box-sizing: border-box;
  position: relative;
  background:
    radial-gradient(circle at 10% 12%, rgba(255, 213, 118, 0.42), transparent 28%),
    radial-gradient(circle at 88% 8%, rgba(137, 169, 79, 0.18), transparent 24%),
    linear-gradient(180deg, #fff8ea 0%, #fffdf7 48%, #f8efe3 100%);
  color: #3a2a1d;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
}

.login-visual {
  min-width: 0;

  h1 {
    max-width: 620px;
    margin: 34px 0 0;
    color: #2e2116;
    font-family: Georgia, "Songti SC", serif;
    font-size: clamp(38px, 6vw, 70px);
    font-weight: 500;
    line-height: 1.04;
    letter-spacing: -0.055em;
  }

  p {
    max-width: 500px;
    margin: 20px 0 0;
    color: #76573f;
    font-size: 16px;
    line-height: 1.85;
  }

  img {
    width: min(760px, 100%);
    height: 300px;
    margin-top: 30px;
    border-radius: 34px;
    object-fit: cover;
    box-shadow: 0 24px 70px rgba(102, 68, 35, 0.18);
  }
}

.login-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #31512f;
  text-decoration: none;

  span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 12px;
    background: #fff3d8;
    font-size: 20px;
  }

  strong {
    font-size: 22px;
    font-weight: 900;
  }
}

.login-card {
  width: 100%;
  padding: 36px;
  box-sizing: border-box;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 24px 70px rgba(102, 68, 35, 0.14);
  backdrop-filter: blur(18px);
}

.login-header {
  text-align: left;
  margin-bottom: 28px;

  h2 {
    margin: 6px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 30px;
    font-weight: 500;
  }

  p {
    margin: 8px 0 0;
    font-size: 13px;
    color: #856449;
    line-height: 1.7;
  }
}

.login-kicker {
  color: #b56a26;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.login-card :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 16px;
  box-shadow: 0 0 0 1px rgba(121, 82, 45, 0.14) inset;
}

.login-btn {
  width: 100%;
  height: 46px;
  border: 0;
  border-radius: 16px;
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  font-weight: 900;
  box-shadow: 0 14px 30px rgba(229, 104, 52, 0.24);
}

.login-footer {
  text-align: center;
  font-size: 13px;
  color: #856449;

  a {
    color: #d76626;
    margin-left: 4px;
    font-weight: 800;

    &:hover {
      text-decoration: underline;
    }
  }
}

.admin-toggle {
  position: absolute;
  top: 28px;
  right: 28px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid rgba(121, 82, 45, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(12px);
  color: #6f5038;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;

  &:hover {
    background: #fff1d2;
    border-color: rgba(233, 109, 59, 0.4);
    color: #d76626;
  }
}

@media (max-width: 960px) {
  .login-page {
    grid-template-columns: 1fr;
    padding-right: clamp(20px, 5vw, 70px);
  }

  .login-card {
    max-width: 520px;
  }

  .admin-toggle {
    top: 18px;
    right: 18px;
  }
}

@media (max-width: 560px) {
  .login-page {
    padding: 20px;
    padding-right: 20px;
  }

  .login-card {
    padding: 26px;
  }
}
</style>