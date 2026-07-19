<template>
  <section class="home-page" data-testid="home-page">
    <div class="home-hero">
      <p class="home-hero__eyebrow">FridgeChef</p>
      <h1>从冰箱里的食材开始，做一顿恰到好处的饭。</h1>
      <p>上传食物图片、确认食材，再用菜谱对话完成调整。所有入口均使用当前已注册的页面与权限。</p>
      <router-link class="home-hero__primary" to="/food-recipes">开始食物识别</router-link>
    </div>

    <div class="home-actions" aria-label="功能入口">
      <router-link v-for="item in visibleActions" :key="item.path" class="home-action" :to="item.path">
        <strong>{{ item.title }}</strong>
        <span>{{ item.description }}</span>
      </router-link>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const actions = [
  { path: '/profile', title: '个人中心', description: '查看并维护个人资料。' },
  { path: '/history', title: '历史记录', description: '从已保存的菜谱继续对话或查看版本。' },
  { path: '/dashboard', title: '数据看板', description: '查看当前账号的食材与菜谱数据。' },
]

const visibleActions = computed(() => {
  const items = actions.filter((item) => !item.permission || userStore.hasPermission(item.permission))
  if (['user:list', 'role:list', 'detection:task:view', 'training:task:view', 'dataset:view', 'model:view']
    .some((permission) => userStore.hasPermission(permission))) {
    items.push({ path: '/admin/workbench', title: '模型工作台', description: '进入检测、训练、数据与系统管理。' })
  }
  return items
})
</script>

<style lang="scss" scoped>
.home-page {
  display: grid;
  gap: $spacing-lg;
  margin: 0 auto;
  max-width: 1120px;
}

.home-hero {
  background:
    radial-gradient(circle at 85% 15%, rgba(255, 210, 121, 0.68), transparent 31%),
    linear-gradient(135deg, #fff5dd, #fffdf8 62%, #eef6df);
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 28px;
  box-shadow: 0 22px 60px rgba(102, 68, 35, 0.1);
  padding: clamp(28px, 6vw, 64px);

  h1 {
    color: #31512f;
    font-family: Georgia, "Songti SC", serif;
    font-size: clamp(30px, 5vw, 52px);
    line-height: 1.15;
    margin: 0;
    max-width: 720px;
  }

  p:not(.home-hero__eyebrow) {
    color: #76573f;
    line-height: 1.8;
    margin: $spacing-md 0 $spacing-lg;
    max-width: 650px;
  }
}

.home-hero__eyebrow {
  color: #cf652d;
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.12em;
  margin: 0 0 $spacing-sm;
  text-transform: uppercase;
}

.home-hero__primary {
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  border-radius: 14px;
  box-shadow: 0 12px 26px rgba(229, 104, 52, 0.18);
  color: #fffaf0;
  display: inline-block;
  font-weight: 800;
  padding: 12px 18px;
  text-decoration: none;
}

.home-actions {
  display: grid;
  gap: $spacing-md;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
}

.home-action {
  background: rgba(255, 253, 248, 0.88);
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 20px;
  color: #4c3a2c;
  display: grid;
  gap: 6px;
  min-height: 116px;
  padding: $spacing-lg;
  text-decoration: none;
  transition: transform 0.2s, box-shadow 0.2s;

  &:hover {
    box-shadow: 0 16px 36px rgba(102, 68, 35, 0.12);
    transform: translateY(-2px);
  }

  span {
    color: #76573f;
    font-size: 14px;
    line-height: 1.6;
  }
}
</style>
