<template>
  <div class="main-layout">
    <!-- 顶部导航 -->
    <AppHeader />

    <!-- 侧边栏 + 内容区 -->
    <div class="layout-body">
      <AppSidebar />

      <!-- 主内容区 -->
      <main class="layout-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'
</script>

<style lang="scss" scoped>
.main-layout {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 12% 10%, rgba(255, 213, 118, 0.34), transparent 28%),
    linear-gradient(180deg, #fff8ea 0%, #fffdf7 46%, #f8efe3 100%);
}

.layout-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.layout-content {
  flex: 1;
  background: transparent;
  overflow-y: auto;
  padding: $spacing-lg;
}
</style>
