<template>
  <div class="heritage-loading" :class="`heritage-loading--${variant}`">
    <div class="heritage-loading__hero">
      <div class="heritage-loading__ring" aria-hidden="true">
        <span class="heritage-loading__ring-track" />
        <span class="heritage-loading__ring-spin" />
      </div>
      <div class="heritage-loading__icon-wrap">
        <el-icon class="heritage-loading__icon"><component :is="iconComponent" /></el-icon>
      </div>
    </div>

    <p class="heritage-loading__title">{{ config.title }}</p>
    <p class="heritage-loading__subtitle">{{ config.subtitle }}</p>

    <div class="heritage-loading__steps" v-if="config.steps?.length">
      <div
        v-for="(step, i) in config.steps"
        :key="i"
        class="heritage-loading__step"
        :class="{ active: activeStep >= i, done: activeStep > i }"
      >
        <span class="heritage-loading__step-dot" />
        <span class="heritage-loading__step-text">{{ step }}</span>
      </div>
    </div>

    <div class="heritage-loading__shimmer" aria-hidden="true">
      <span
        v-for="(w, i) in shimmerWidths"
        :key="i"
        class="heritage-loading__bar"
        :style="{ width: w }"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Location, Picture, VideoPlay } from '@element-plus/icons-vue'

const props = defineProps({
  /** map-ip | image-source | video-source */
  variant: {
    type: String,
    default: 'image-source',
    validator: (v) => ['map-ip', 'image-source', 'video-source'].includes(v),
  },
})

const VARIANT_CONFIG = {
  'map-ip': {
    title: '正在定位',
    subtitle: '读取浏览器坐标，检索同城非遗相关地标…',
    steps: ['获取精确定位', '匹配城市地标', '写入地图标注'],
    icon: Location,
  },
  'image-source': {
    title: '识图分析中',
    subtitle: '识别非遗条目，匹配发源地并在地图打点…',
    steps: ['解析画面', '检索知识库', '标注地图坐标'],
    icon: Picture,
  },
  'video-source': {
    title: '视频理解中',
    subtitle: '分析视频中的非遗内容，约需 30–90 秒…',
    steps: ['读取视频帧', '内容理解', '生成溯源与地标'],
    icon: VideoPlay,
  },
}

const shimmerWidths = ['72%', '94%', '86%', '58%', '78%']

const config = computed(() => VARIANT_CONFIG[props.variant] || VARIANT_CONFIG['image-source'])
const iconComponent = computed(() => config.value.icon)

const activeStep = ref(0)
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    const max = (config.value.steps?.length || 1) - 1
    activeStep.value = activeStep.value >= max ? 0 : activeStep.value + 1
  }, 2200)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.heritage-loading {
  position: relative;
  padding: 22px 18px 20px;
  border-radius: var(--radius-md);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.heritage-loading--video-source {
  border-color: rgba(201, 168, 76, 0.28);
}

.heritage-loading__hero {
  position: relative;
  width: 56px;
  height: 56px;
  margin: 0 auto 14px;
}

.heritage-loading__ring {
  position: absolute;
  inset: 0;
}

.heritage-loading__ring-track {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid rgba(61, 158, 140, 0.15);
}

.heritage-loading--video-source .heritage-loading__ring-track {
  border-color: rgba(201, 168, 76, 0.2);
}

.heritage-loading__ring-spin {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: var(--color-accent-teal);
  border-right-color: rgba(61, 158, 140, 0.35);
  animation: hl-ring 1.1s linear infinite;
}

.heritage-loading--video-source .heritage-loading__ring-spin {
  border-top-color: var(--color-accent-gold);
  border-right-color: rgba(201, 168, 76, 0.35);
}

.heritage-loading__icon-wrap {
  position: absolute;
  inset: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(61, 158, 140, 0.1);
}

.heritage-loading--video-source .heritage-loading__icon-wrap {
  background: rgba(201, 168, 76, 0.1);
}

.heritage-loading__icon {
  font-size: 22px;
  color: var(--color-accent-teal);
  animation: hl-icon-pulse 2s ease-in-out infinite;
}

.heritage-loading--video-source .heritage-loading__icon {
  color: var(--color-accent-gold-light);
}

.heritage-loading__title {
  text-align: center;
  font-family: var(--font-serif);
  font-size: 15px;
  letter-spacing: 1px;
  color: var(--color-text-primary);
  margin-bottom: 6px;
}

.heritage-loading__subtitle {
  text-align: center;
  font-size: 11px;
  line-height: 1.55;
  color: var(--color-text-muted);
  padding: 0 6px;
  margin-bottom: 14px;
}

.heritage-loading__steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--color-border-soft);
}

.heritage-loading__step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-muted);
  transition: color 0.35s ease;
}

.heritage-loading__step.active {
  color: var(--color-accent-teal);
}

.heritage-loading--video-source .heritage-loading__step.active {
  color: var(--color-accent-gold-light);
}

.heritage-loading__step.done {
  color: var(--color-text-secondary);
  opacity: 0.65;
}

.heritage-loading__step-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-border);
  flex-shrink: 0;
  transition: background 0.35s, box-shadow 0.35s;
}

.heritage-loading__step.active .heritage-loading__step-dot {
  background: var(--color-accent-teal);
  /* no glow */
  animation: hl-dot-pulse 1.4s ease-in-out infinite;
}

.heritage-loading--video-source .heritage-loading__step.active .heritage-loading__step-dot {
  background: var(--color-accent-gold);
  /* no glow */
}

.heritage-loading__step-text {
  line-height: 1.4;
}

.heritage-loading__shimmer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.heritage-loading__bar {
  display: block;
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    rgba(42, 46, 56, 0.9) 0%,
    rgba(61, 158, 140, 0.18) 45%,
    rgba(74, 79, 98, 0.5) 55%,
    rgba(42, 46, 56, 0.9) 100%
  );
  background-size: 200% 100%;
  animation: hl-shimmer 1.6s ease-in-out infinite;
}

.heritage-loading--video-source .heritage-loading__bar {
  background: linear-gradient(
    90deg,
    rgba(42, 46, 56, 0.9) 0%,
    rgba(201, 168, 76, 0.15) 45%,
    rgba(74, 79, 98, 0.5) 55%,
    rgba(42, 46, 56, 0.9) 100%
  );
  background-size: 200% 100%;
}

.heritage-loading__bar:nth-child(2) { animation-delay: 0.15s; }
.heritage-loading__bar:nth-child(3) { animation-delay: 0.3s; }
.heritage-loading__bar:nth-child(4) { animation-delay: 0.45s; }
.heritage-loading__bar:nth-child(5) { animation-delay: 0.6s; }

@keyframes hl-ring {
  to { transform: rotate(360deg); }
}

@keyframes hl-icon-pulse {
  0%, 100% { opacity: 0.85; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.06); }
}

@keyframes hl-dot-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.25); }
}

@keyframes hl-shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
</style>
