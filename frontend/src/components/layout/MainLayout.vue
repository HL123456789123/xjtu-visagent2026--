<template>
  <div class="main-layout">
    <AppHeader />
    <main class="layout-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import AppHeader from './AppHeader.vue'
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

.layout-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: $spacing-lg;
}

@media (max-width: 720px) {
  .layout-content {
    padding: $spacing-md;
  }
}
</style>
