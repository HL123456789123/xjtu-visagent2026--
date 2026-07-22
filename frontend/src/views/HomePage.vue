<template>
  <section class="home-page" data-testid="home-page">
    <div
      class="home-hero"
      @mouseenter="pauseCarousel"
      @mouseleave="startCarousel"
      @focusin="pauseCarousel"
      @focusout="startCarousel"
    >
      <div class="home-hero__media" aria-hidden="true">
        <img
          v-for="(slide, index) in slides"
          :key="slide.src"
          :class="['home-hero__image', { 'is-active': index === activeSlide }]"
          :src="slide.src"
          :alt="slide.alt"
          :loading="index === 0 ? 'eager' : 'lazy'"
        />
      </div>
      <div class="home-hero__shade"></div>

      <div class="home-hero__content">
        <p class="home-hero__brand">VisAgent · 拍食寻味</p>
        <h1>
          <span>拍下手边的新鲜食材，</span>
          <span>一键收获美味菜谱</span>
        </h1>
        <p class="home-hero__copy">识别食材、确认清单、生成菜谱，还能通过对话不断调整。</p>
        <router-link class="home-hero__primary" to="/food-recipes">
          <el-icon><Camera /></el-icon>
          开始识别食材
        </router-link>
      </div>

      <div class="home-hero__controls" aria-label="菜品图片轮播">
        <button type="button" aria-label="上一张菜品图片" @click="previousSlide">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <div class="home-hero__dots">
          <button
            v-for="(slide, index) in slides"
            :key="`${slide.src}-dot`"
            type="button"
            :class="{ 'is-active': index === activeSlide }"
            :aria-label="`查看第 ${index + 1} 张菜品图片`"
            :aria-current="index === activeSlide ? 'true' : undefined"
            @click="selectSlide(index)"
          ></button>
        </div>
        <button type="button" aria-label="下一张菜品图片" @click="nextSlide">
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>
    </div>

    <div class="home-shortcuts" aria-label="常用入口">
      <div class="home-shortcuts__heading">
        <strong>继续探索</strong>
        <span>从记录、数据或个人偏好继续使用</span>
      </div>
      <nav class="home-actions">
        <router-link v-for="item in visibleActions" :key="item.path" class="home-action" :to="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>
            <strong>{{ item.title }}</strong>
            <small>{{ item.description }}</small>
          </span>
          <el-icon class="home-action__arrow"><ArrowRight /></el-icon>
        </router-link>
      </nav>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  Clock,
  Cpu,
  DataAnalysis,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const activeSlide = ref(0)
let carouselTimer = null

const slides = [
  { src: '/food-carousel-1.jpg', alt: '咖喱饭与新鲜配菜' },
  { src: '/food-carousel-tomato-beef.jpg', alt: '番茄牛肉家常菜' },
  { src: '/food-carousel-tofu.jpg', alt: '豆腐青菜菌菇家常菜' },
]

const actions = [
  { path: '/history', title: '历史记录', description: '找回菜谱与对话', icon: Clock },
  { path: '/dashboard', title: '数据看板', description: '查看个人烹饪数据', icon: DataAnalysis },
  { path: '/profile', title: '个人中心', description: '维护资料与偏好', icon: User },
]

const visibleActions = computed(() => {
  const items = [...actions]
  if (userStore.isAdmin) {
    items.push(
      { path: '/admin/models', title: '模型管理', description: '管理识别模型', icon: Cpu },
      { path: '/admin/users', title: '用户管理', description: '维护账号与角色', icon: UserFilled },
    )
  }
  return items
})

function prefersReducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

function selectSlide(index) {
  activeSlide.value = index
}

function previousSlide() {
  activeSlide.value = (activeSlide.value - 1 + slides.length) % slides.length
}

function nextSlide() {
  activeSlide.value = (activeSlide.value + 1) % slides.length
}

function pauseCarousel() {
  if (carouselTimer) window.clearInterval(carouselTimer)
  carouselTimer = null
}

function startCarousel() {
  if (carouselTimer || prefersReducedMotion()) return
  carouselTimer = window.setInterval(() => {
    activeSlide.value = (activeSlide.value + 1) % slides.length
  }, 2000)
}

onMounted(startCarousel)
onBeforeUnmount(pauseCarousel)
</script>

<style lang="scss" scoped>
.home-page {
  display: grid;
  gap: 26px;
  margin: 0 auto;
  max-width: 1440px;
}

.home-hero {
  position: relative;
  min-height: 500px;
  overflow: hidden;
  color: #fff;
  background: #28362a;
  isolation: isolate;
}

.home-hero__media,
.home-hero__shade,
.home-hero__image {
  position: absolute;
  inset: 0;
}

.home-hero__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transform: scale(1.025);
  transition: opacity 0.65s ease, transform 5s ease;

  &.is-active {
    opacity: 1;
    transform: scale(1);
  }
}

.home-hero__shade {
  z-index: 1;
  background: rgba(27, 25, 20, 0.5);
}

.home-hero__content {
  position: relative;
  z-index: 2;
  display: flex;
  min-height: 500px;
  max-width: 720px;
  box-sizing: border-box;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  padding: 54px 64px 72px;

  h1 {
    max-width: 680px;
    margin: 0;
    font-family: Georgia, "Songti SC", serif;
    font-size: 52px;
    font-weight: 600;
    line-height: 1.22;

    span {
      display: block;
      white-space: nowrap;
    }
  }
}

.home-hero__brand {
  margin: 0 0 14px;
  color: #ffe09b;
  font-size: 14px;
  font-weight: 900;
}

.home-hero__copy {
  max-width: 580px;
  margin: 20px 0 28px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 17px;
  line-height: 1.8;
}

.home-hero__primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 46px;
  box-sizing: border-box;
  border-radius: 6px;
  background: #f07a3e;
  color: #fff;
  padding: 0 20px;
  text-decoration: none;
  font-weight: 800;
  transition: background 0.2s ease, transform 0.2s ease;

  &:hover {
    background: #d95e29;
    transform: translateY(-2px);
  }
}

.home-hero__controls {
  position: absolute;
  right: 24px;
  bottom: 22px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 12px;

  > button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border: 1px solid rgba(255, 255, 255, 0.55);
    border-radius: 50%;
    background: rgba(28, 26, 21, 0.5);
    color: #fff;
    cursor: pointer;
  }
}

.home-hero__dots {
  display: flex;
  align-items: center;
  gap: 7px;

  button {
    width: 8px;
    height: 8px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.55);
    cursor: pointer;
    transition: width 0.2s ease, background 0.2s ease;

    &.is-active {
      width: 24px;
      border-radius: 4px;
      background: #ffe09b;
    }
  }
}

.home-shortcuts {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  padding: 0 2px 12px;
}

.home-shortcuts__heading {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: #3a2a1d;

  strong {
    font-size: 20px;
  }

  span {
    color: #806a55;
    font-size: 13px;
    line-height: 1.6;
  }
}

.home-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  border-top: 1px solid rgba(121, 82, 45, 0.14);
}

.home-action {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 10px;
  min-height: 82px;
  border-bottom: 1px solid rgba(121, 82, 45, 0.14);
  color: #4c3a2c;
  padding: 0 16px;
  text-decoration: none;
  transition: background 0.2s ease, transform 0.2s ease;

  &:hover {
    background: rgba(255, 248, 234, 0.86);
    transform: translateY(-2px);

    .home-action__arrow {
      transform: translateX(3px);
    }
  }

  > .el-icon:first-child {
    color: #d76626;
    font-size: 22px;
  }

  span {
    display: grid;
    gap: 3px;
  }

  small {
    color: #806a55;
    font-size: 12px;
  }
}

.home-action__arrow {
  color: #9a806b;
  transition: transform 0.2s ease;
}

@media (max-width: 820px) {
  .home-hero,
  .home-hero__content {
    min-height: 440px;
  }

  .home-hero__content {
    padding: 40px 30px 76px;

    h1 {
      font-size: 38px;
    }
  }

}

@media (max-width: 520px) {
  .home-hero,
  .home-hero__content {
    min-height: 460px;
  }

  .home-hero__content {
    padding: 34px 20px 82px;

    h1 {
      font-size: 28px;
    }
  }

  .home-hero__copy {
    font-size: 15px;
  }

  .home-hero__controls {
    right: 16px;
    bottom: 16px;
  }
}

@media (max-width: 400px) {
  .home-hero__content h1 {
    font-size: 24px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-hero__image,
  .home-hero__primary,
  .home-action,
  .home-action__arrow,
  .home-hero__dots button {
    transition: none;
  }
}
</style>
