<template>
  <div class="login-page">
    <section class="login-visual">
      <router-link class="login-brand" to="/login">
        <span>🍳</span>
        <strong>FridgeChef</strong>
      </router-link>
      <h1>登录后，开启你的专属美食之旅</h1>
      <p>识别食材、确认清单、生成家常食谱，把每天吃什么变得轻松一点。</p>
      <img src="/food-hero.jpg" alt="番茄鸡蛋与日常食材" />
    </section>

    <section class="login-card">
      <div class="login-header">
        <span class="login-kicker">Welcome back</span>
        <h2>欢迎回来</h2>
        <p>登录 FridgeChef，继续你的日常美食计划。</p>
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
            登录并进入开始页
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <span>还没有账号？</span>
        <router-link to="/register">立即注册</router-link>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)

/** 登录表单 */
const loginForm = reactive({
  username: '',
  password: '',
})

/** 表单验证规则 */
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

/** 处理登录 */
async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password,
    })
    ElMessage.success('登录成功')
    // 登录后跳转（如果有 redirect 参数则跳转到目标页）
    const redirect = route.query.redirect || '/start'
    router.push(redirect)
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
  grid-template-columns: minmax(0, 1fr) 460px;
  align-items: center;
  gap: clamp(28px, 5vw, 72px);
  padding: clamp(28px, 5vw, 70px);
  box-sizing: border-box;
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
  padding: 40px;
  box-sizing: border-box;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 24px 70px rgba(102, 68, 35, 0.14);
  backdrop-filter: blur(18px);
}

.login-header {
  text-align: left;
  margin-bottom: 32px;

  h2 {
    margin: 6px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 34px;
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

@media (max-width: 960px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .login-card {
    max-width: 520px;
  }
}

@media (max-width: 560px) {
  .login-page {
    padding: 20px;
  }

  .login-card {
    padding: 26px;
  }
}
</style>
