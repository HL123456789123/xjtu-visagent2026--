<template>
  <div class="main-layout">
    <AppHeader />
    <main :class="['layout-content', { 'layout-content--workspace': route.name === 'FoodRecipe' }]">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import AppHeader from './AppHeader.vue'

const route = useRoute()
</script>

<style lang="scss" scoped>
.main-layout {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f3f5f0;
}

.layout-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: $spacing-lg;
}

.layout-content--workspace {
  overflow: hidden;
  padding: 0;
}

@media (max-width: 720px) {
  .layout-content {
    padding: $spacing-md;
  }
}
</style>
