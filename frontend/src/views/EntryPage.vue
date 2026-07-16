<template>
  <main class="entry-page">
    <section class="entry-shell">
      <div class="entry-copy">
        <router-link class="entry-brand" to="/entry">
          <span>🍳</span>
          <strong>FridgeChef</strong>
        </router-link>
        <span class="entry-kicker">Choose workspace</span>
        <h1>选择你的进入方式</h1>
        <p>用户端保留日常美食工作流；管理端在此基础上开放模型训练和数据看板。</p>
      </div>

      <div class="entry-panel" aria-label="入口选择">
        <button class="entry-option" type="button" @click="chooseMode(ACCESS_MODES.USER)">
          <span class="entry-option__icon">
            <el-icon><User /></el-icon>
          </span>
          <span>
            <strong>用户入口</strong>
            <small>进入食物识别、智能对话和历史记录。</small>
          </span>
        </button>

        <button class="entry-option entry-option--admin" type="button" @click="chooseMode(ACCESS_MODES.ADMIN)">
          <span class="entry-option__icon">
            <el-icon><DataAnalysis /></el-icon>
          </span>
          <span>
            <strong>管理者入口</strong>
            <small>在用户功能外，查看数据看板并管理模型训练。</small>
          </span>
        </button>

        <p v-if="userStore.isLoggedIn" class="entry-current">
          当前账号：{{ userStore.username }}
        </p>
      </div>
    </section>
  </main>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { ACCESS_MODES, isManagerPath } from '@/utils/accessMode'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

function getRedirectQuery() {
  const redirect = route.query.redirect
  return Array.isArray(redirect) ? redirect[0] : redirect
}

function getTargetPath(mode) {
  const redirect = getRedirectQuery()
  if (mode === ACCESS_MODES.ADMIN) return redirect || '/dashboard'
  return redirect && !isManagerPath(redirect) ? redirect : '/start'
}

async function ensureCurrentUser() {
  if (!userStore.isLoggedIn) return
  if (userStore.roles.length > 0 && userStore.permissions.length > 0) return
  await userStore.fetchUserInfo()
}

async function chooseMode(mode) {
  const targetPath = getTargetPath(mode)
  userStore.setAccessMode(mode)

  if (!userStore.isLoggedIn) {
    router.push({
      path: '/login',
      query: { mode, redirect: targetPath },
    })
    return
  }

  try {
    await ensureCurrentUser()
  } catch {
    router.push({
      path: '/login',
      query: { mode, redirect: targetPath },
    })
    return
  }

  if (mode === ACCESS_MODES.ADMIN && !userStore.canUseAdminMode) {
    userStore.setAccessMode(ACCESS_MODES.USER)
    ElMessage.warning('当前账号没有管理者入口权限，请联系管理员开通。')
    return
  }

  router.push(targetPath)
}
</script>

<style lang="scss" scoped>
.entry-page {
  min-height: 100vh;
  box-sizing: border-box;
  display: grid;
  place-items: center;
  padding: clamp(22px, 5vw, 72px);
  background:
    linear-gradient(90deg, rgba(39, 30, 20, 0.76), rgba(39, 30, 20, 0.38)),
    url('/food-hero.jpg') center / cover;
  color: #fffaf0;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
}

.entry-shell {
  width: min(1040px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  align-items: center;
  gap: clamp(28px, 6vw, 80px);
}

.entry-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #fffaf0;
  text-decoration: none;

  span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: rgba(255, 243, 216, 0.18);
    font-size: 20px;
  }

  strong {
    font-size: 22px;
    font-weight: 900;
  }
}

.entry-kicker {
  display: block;
  margin-top: 54px;
  color: #ffd991;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.entry-copy h1 {
  max-width: 620px;
  margin: 14px 0 0;
  font-family: Georgia, "Songti SC", serif;
  font-size: clamp(42px, 7vw, 78px);
  font-weight: 500;
  line-height: 1.04;
  letter-spacing: 0;
}

.entry-copy p {
  max-width: 520px;
  margin: 22px 0 0;
  color: rgba(255, 250, 240, 0.84);
  font-size: 17px;
  line-height: 1.85;
}

.entry-panel {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid rgba(255, 250, 240, 0.26);
  border-radius: 8px;
  background: rgba(255, 253, 248, 0.88);
  box-shadow: 0 24px 70px rgba(39, 30, 20, 0.28);
  backdrop-filter: blur(18px);
}

.entry-option {
  width: 100%;
  min-height: 108px;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  border: 1px solid rgba(121, 82, 45, 0.13);
  border-radius: 8px;
  background: #fffaf0;
  color: #3a2a1d;
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    border-color: rgba(233, 109, 59, 0.45);
    box-shadow: 0 14px 34px rgba(102, 68, 35, 0.16);
    transform: translateY(-2px);
  }

  strong,
  small {
    display: block;
  }

  strong {
    color: #2e2116;
    font-size: 19px;
    font-weight: 900;
  }

  small {
    margin-top: 7px;
    color: #76573f;
    font-size: 13px;
    line-height: 1.55;
  }
}

.entry-option--admin {
  background: #f6fbf4;
}

.entry-option__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 8px;
  background: #fff1d2;
  color: #d76626;
  font-size: 24px;
}

.entry-option--admin .entry-option__icon {
  background: #e8f2e1;
  color: #31512f;
}

.entry-current {
  margin: 0;
  color: #76573f;
  font-size: 13px;
  text-align: center;
}

@media (max-width: 860px) {
  .entry-shell {
    grid-template-columns: 1fr;
  }

  .entry-kicker {
    margin-top: 44px;
  }

  .entry-panel {
    max-width: 520px;
  }
}

@media (max-width: 520px) {
  .entry-page {
    padding: 18px;
  }

  .entry-option {
    grid-template-columns: 44px minmax(0, 1fr);
    padding: 14px;
  }

  .entry-option__icon {
    width: 44px;
    height: 44px;
  }
}
</style>
