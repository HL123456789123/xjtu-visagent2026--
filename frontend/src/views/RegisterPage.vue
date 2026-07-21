<template>
  <div class="register-page">
    <section class="register-visual">
      <router-link class="register-brand" to="/login">
        <span aria-hidden="true"><el-icon><KnifeFork /></el-icon></span>
        <strong>VisAgent · 拍食寻味</strong>
      </router-link>
      <h1>创建账号，保存你的每日美食灵感</h1>
      <p>把识别到的食材、生成过的菜谱和日常偏好沉淀成你的个人厨房助手。</p>
      <img src="/food-carousel-tofu.jpg" alt="豆腐青菜菌菇家常菜" />
    </section>

    <section class="register-card">
      <div class="register-header">
        <span class="register-kicker">Join us</span>
        <h2>创建账号</h2>
        <p>加入拍食寻味，开始整理你的专属食材和菜谱。</p>
      </div>

      <el-form
        ref="formRef"
        :model="registerForm"
        :rules="registerRules"
        label-width="0"
        size="large"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="用户名"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="email">
          <el-input
            v-model="registerForm.email"
            placeholder="邮箱"
          >
            <template #prefix>
              <el-icon><Message /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="密码（至少 6 位）"
            show-password
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="确认密码"
            show-password
            @keyup.enter="handleRegister"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="register-btn"
            :loading="loading"
            @click="handleRegister"
          >
            注册并去登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="register-footer">
        <span>已有账号？</span>
        <router-link to="/login">立即登录</router-link>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { KnifeFork, User, Lock, Message } from '@element-plus/icons-vue'
import { registerApi } from '@/api/auth'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

/** 注册表单 */
const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

/** 确认密码验证器 */
const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

/** 表单验证规则 */
const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度在 3-50 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

/** 处理注册 */
async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await registerApi({
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password,
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch {
    // 错误已在 Axios 拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.register-page {
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

.register-visual {
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

.register-brand {
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

.register-card {
  width: 100%;
  padding: 40px;
  box-sizing: border-box;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 24px 70px rgba(102, 68, 35, 0.14);
  backdrop-filter: blur(18px);
}

.register-header {
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

.register-kicker {
  color: #b56a26;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.register-card :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 16px;
  box-shadow: 0 0 0 1px rgba(121, 82, 45, 0.14) inset;
}

.register-btn {
  width: 100%;
  height: 46px;
  border: 0;
  border-radius: 16px;
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  font-weight: 900;
  box-shadow: 0 14px 30px rgba(229, 104, 52, 0.24);
}

.register-footer {
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
  .register-page {
    grid-template-columns: 1fr;
  }

  .register-card {
    max-width: 520px;
  }
}

@media (max-width: 560px) {
  .register-page {
    padding: 20px;
  }

  .register-card {
    padding: 26px;
  }
}
</style>
