<template>
  <main class="start-page">
    <section class="start-hero">
      <div class="start-hero__copy">
        <span class="start-hero__eyebrow">Daily kitchen assistant</span>
        <h1>让每一张食物照片，都变成好做的家常灵感</h1>
        <p>
          识别冰箱和餐桌上的食材，整理可用食材清单，再生成适合日常烹饪的专属食谱。
        </p>
        <button class="start-hero__button" type="button" @click="goToFoodRecipes">
          开启你的专属美食之旅
        </button>
      </div>

      <div class="start-hero__visual" aria-label="家常美食轮播图片">
        <img class="start-hero__slide" src="/food-carousel-1.jpg" alt="早餐拼盘" />
        <img class="start-hero__slide" src="/food-carousel-2.jpg" alt="芒果豆类沙拉" />
        <img class="start-hero__slide" src="/food-carousel-3.jpg" alt="家常套餐" />
        <div class="start-hero__note">
          <strong>今日推荐</strong>
          <span>早餐灵感 · 清爽沙拉 · 家常套餐</span>
        </div>
      </div>
    </section>

    <section class="start-cards" aria-label="功能说明">
      <article>
        <span>01</span>
        <h2>拍下食材</h2>
        <p>上传餐桌或冰箱照片，快速整理可用食材。</p>
      </article>
      <article>
        <span>02</span>
        <h2>确认清单</h2>
        <p>识别结果可编辑、可补充，避免遗漏关键食材。</p>
      </article>
      <article>
        <span>03</span>
        <h2>生成菜谱</h2>
        <p>根据确认食材生成日常化、好操作的家常做法。</p>
      </article>
    </section>
  </main>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function goToFoodRecipes() {
  router.push('/food-recipes')
}
</script>

<style lang="scss" scoped>
.start-page {
  min-height: calc(100vh - #{$header-height});
  overflow: hidden;
  background:
    radial-gradient(circle at 12% 10%, rgba(255, 213, 118, 0.38), transparent 28%),
    radial-gradient(circle at 88% 12%, rgba(137, 169, 79, 0.2), transparent 26%),
    linear-gradient(180deg, #fff8ea 0%, #fffdf7 46%, #f8efe3 100%);
  color: #3a2a1d;
  font-family: "Trebuchet MS", "Microsoft YaHei", "PingFang SC", sans-serif;
}

.start-hero {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(360px, 1.05fr);
  align-items: center;
  gap: clamp(28px, 5vw, 70px);
  padding: clamp(46px, 7vw, 88px) clamp(22px, 6vw, 86px) 34px;
}

.start-hero__copy {
  max-width: 680px;
}

.start-hero__eyebrow {
  color: #b56a26;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.start-hero h1 {
  margin: 14px 0 0;
  color: #2e2116;
  font-family: Georgia, "Songti SC", serif;
  font-size: clamp(38px, 6vw, 72px);
  font-weight: 500;
  line-height: 1.04;
  letter-spacing: -0.055em;
}

.start-hero p {
  max-width: 540px;
  margin: 22px 0 0;
  color: #76573f;
  font-size: 17px;
  line-height: 1.85;
}

.start-hero__button {
  height: 54px;
  margin-top: 30px;
  border: 0;
  border-radius: 18px;
  background: linear-gradient(135deg, #f1a93b, #e96d3b);
  color: #fffaf0;
  padding: 0 30px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 900;
  box-shadow: 0 18px 38px rgba(229, 104, 52, 0.28);
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 22px 46px rgba(229, 104, 52, 0.34);
  }
}

.start-hero__visual {
  position: relative;
  min-height: 420px;
  border-radius: 42px;
  overflow: hidden;
  background: #fffaf1;
  box-shadow: 0 28px 80px rgba(102, 68, 35, 0.18);

  &::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
      linear-gradient(90deg, rgba(255, 248, 234, 0.08), rgba(255, 248, 234, 0.42)),
      radial-gradient(circle at 20% 20%, rgba(255, 255, 255, 0.4), transparent 28%);
    z-index: 1;
  }

  .start-hero__slide {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    min-height: 420px;
    object-fit: cover;
    display: block;
    opacity: 0;
    animation: start-hero-carousel 12s infinite;

    &:nth-of-type(1) {
      animation-delay: 0s;
    }

    &:nth-of-type(2) {
      animation-delay: 4s;
    }

    &:nth-of-type(3) {
      animation-delay: 8s;
    }
  }
}

.start-hero__note {
  position: absolute;
  left: 28px;
  bottom: 28px;
  z-index: 2;
  display: grid;
  gap: 4px;
  max-width: 300px;
  border: 1px solid rgba(121, 82, 45, 0.12);
  border-radius: 20px;
  background: rgba(255, 253, 248, 0.9);
  padding: 16px 18px;
  box-shadow: 0 18px 40px rgba(102, 68, 35, 0.18);
  backdrop-filter: blur(14px);

  strong {
    color: #31512f;
    font-size: 15px;
  }

  span {
    color: #76573f;
    font-size: 13px;
    line-height: 1.55;
  }
}

.start-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  padding: 0 clamp(22px, 6vw, 86px) clamp(38px, 6vw, 74px);

  article {
    border: 1px solid rgba(121, 82, 45, 0.12);
    border-radius: 26px;
    background: rgba(255, 255, 255, 0.72);
    padding: 22px;
    box-shadow: 0 18px 52px rgba(102, 68, 35, 0.1);
  }

  span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: #fff1d2;
    color: #d76626;
    font-weight: 900;
  }

  h2 {
    margin: 16px 0 0;
    color: #3a2a1d;
    font-family: Georgia, "Songti SC", serif;
    font-size: 24px;
    font-weight: 500;
  }

  p {
    margin: 8px 0 0;
    color: #856449;
    font-size: 14px;
    line-height: 1.7;
  }
}

@media (max-width: 960px) {
  .start-hero {
    grid-template-columns: 1fr;
  }

  .start-cards {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .start-hero {
    padding: 34px 18px 24px;
  }

  .start-hero__visual {
    min-height: 300px;
    border-radius: 28px;

    .start-hero__slide {
      min-height: 300px;
    }
  }

  .start-cards {
    padding: 0 18px 36px;
  }
}

@keyframes start-hero-carousel {
  0%,
  30% {
    opacity: 1;
    transform: scale(1);
  }

  38%,
  100% {
    opacity: 0;
    transform: scale(1.02);
  }
}
</style>
