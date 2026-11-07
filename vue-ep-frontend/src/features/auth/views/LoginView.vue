<template>
  <div class="login-page" :class="{ ready: pageReady, success: loginSuccess }">
    <div class="bg-layer" aria-hidden="true">
      <div class="bg-beam"></div>
      <div class="bg-orb bg-orb--teal"></div>
      <div class="bg-orb bg-orb--gold"></div>
      <div class="bg-grid"></div>
      <div class="bg-pattern"></div>
      <div
        v-for="(p, i) in floatParticles"
        :key="'p-' + i"
        class="bg-particle"
        :style="{ left: p.x + '%', top: p.y + '%', animationDelay: p.d + 's', animationDuration: p.dur + 's' }"
      ></div>
      <div
        v-for="(lantern, i) in floatLanterns"
        :key="'l-' + i"
        class="float-lantern"
        :style="{ left: lantern.left + '%', top: lantern.top + '%', animationDelay: i * 0.8 + 's' }"
      >
        <div class="float-lantern-body"></div>
        <div class="float-lantern-glow"></div>
      </div>
    </div>
    <div class="login-shell">
      <aside class="brand-panel">
        <div class="panel-ornament panel-ornament--tl"></div>
        <div class="panel-ornament panel-ornament--br"></div>

        <div class="brand-mark">
          <span class="brand-icon">遗</span>
          <div>
            <h1 class="brand-title">时空匠影</h1>
            <p class="brand-sub">全景研学工作站</p>
            <div class="title-ornament"><span></span><span></span><span></span></div>
          </div>
        </div>

        <div class="stat-row">
          <div v-for="s in statItems" :key="s.label" class="stat-item">
            <span class="stat-value">{{ s.value }}</span>
            <span class="stat-label">{{ s.label }}</span>
          </div>
        </div>

        <p class="brand-lead">
          汇聚非遗地图、知识图谱与 AI 向导，为研学提供可探索、可对话、可沉淀的数字空间。
        </p>

        <ul class="feature-cards">
          <li v-for="f in featureList" :key="f.label" class="feature-card">
            <el-icon class="feature-icon"><component :is="f.icon" /></el-icon>
            <div>
              <span class="feature-label">{{ f.label }}</span>
              <span class="feature-desc">{{ f.desc }}</span>
            </div>
          </li>
        </ul>

        <div class="heritage-timeline">
          <div class="timeline-line"></div>
          <div
            v-for="(node, i) in timelineNodes"
            :key="node.name"
            class="timeline-node"
            :class="{ active: litNode === i }"
            @mouseenter="litNode = i"
          >
            <span class="timeline-dot"></span>
            <span class="timeline-era">{{ node.era }}</span>
            <span class="timeline-name">{{ node.name }}</span>
          </div>
        </div>

        <div class="heritage-ticker" aria-hidden="true">
          <span
            v-for="(name, i) in heritageNames"
            :key="name"
            class="ticker-item"
            :class="{ active: tickerIdx === i }"
          >{{ name }}</span>
          <p v-if="heritageNames[tickerIdx]" class="ticker-tip">{{ heritageTips[tickerIdx] }}</p>
        </div>

        <div class="marquee-wrap" aria-hidden="true">
          <div class="marquee-track">
            <span v-for="(name, i) in marqueeNames" :key="'a-' + i" class="marquee-tag">{{ name }}</span>
            <span v-for="(name, i) in marqueeNames" :key="'b-' + i" class="marquee-tag">{{ name }}</span>
          </div>
        </div>

        <p class="brand-foot">传承千年匠心 · 共护非遗记忆</p>
      </aside>

      <div class="shell-divider" aria-hidden="true">
        <span class="divider-gem">◆</span>
      </div>

      <main class="form-panel">
        <div class="form-card">
          <div class="form-card-border"></div>
          <span class="corner corner--tl"></span>
          <span class="corner corner--tr"></span>
          <span class="corner corner--bl"></span>
          <span class="corner corner--br"></span>
          <div class="form-seal" aria-hidden="true"><span>匠</span></div>

          <div class="form-head">
            <p class="form-welcome">欢迎回来</p>
            <h2 class="form-heading">{{ mode === 'login' ? '登录工作站' : '注册账号' }}</h2>
          </div>

          <el-tabs v-model="mode" class="login-tabs">
            <el-tab-pane label="登 录" name="login" />
            <el-tab-pane label="注 册" name="register" />
          </el-tabs>

          <el-alert
            v-if="errorMsg"
            :title="errorMsg"
            type="error"
            show-icon
            :closable="false"
            class="form-alert"
          />
          <el-alert
            v-if="successMsg"
            :title="successMsg"
            type="success"
            show-icon
            :closable="false"
            class="form-alert"
          />

          <el-form v-if="mode === 'login'" class="auth-form" @submit.prevent="doLogin">
            <el-form-item>
              <el-input v-model="username" placeholder="输入账号" size="large" clearable>
                <template #prefix><el-icon><User /></el-icon></template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="password"
                type="password"
                placeholder="输入密码"
                size="large"
                show-password
                @keyup.enter="doLogin"
              >
                <template #prefix><el-icon><Lock /></el-icon></template>
              </el-input>
            </el-form-item>
            <div class="form-extras">
              <el-checkbox v-model="rememberMe" size="small">记住我</el-checkbox>
            </div>
            <el-button type="primary" size="large" :loading="loading" class="submit-btn" @click="doLogin">
              登 堂 入 室
            </el-button>
            <p class="switch-tip">
              还没有账号？
              <a href="#" @click.prevent="mode = 'register'">立即注册</a>
            </p>
          </el-form>

          <el-form v-else class="auth-form" @submit.prevent="doRegister">
            <el-form-item>
              <el-input v-model="regUsername" placeholder="设置账号（唯一）" size="large" clearable>
                <template #prefix><el-icon><User /></el-icon></template>
              </el-input>
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="regPassword"
                type="password"
                placeholder="设置密码（至少6位）"
                size="large"
                show-password
                @keyup.enter="doRegister"
              >
                <template #prefix><el-icon><Lock /></el-icon></template>
              </el-input>
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="submit-btn register-btn"
              @click="doRegister"
            >
              缔 结 契 约
            </el-button>
            <p class="switch-tip">
              已有账号？
              <a href="#" @click.prevent="mode = 'login'">返回登录</a>
            </p>
          </el-form>

          <p class="form-footer">非遗数字文化平台 · 传承千年匠心</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { User, Lock, MapLocation, Share, ChatDotRound, Document } from '@element-plus/icons-vue'
import { useAuthForm } from '@/features/auth/composables/useAuthForm'

const heritageNames = [
  '皮影戏', '剪纸', '昆曲', '景泰蓝', '古琴', '苏绣', '舞狮', '篆刻',
]
const heritageTips = [
  '光影叙事，千年不绝',
  '镂空成趣，民间智慧',
  '水磨腔韵，百戏之祖',
  '铜胎掐丝，皇家工艺',
  '丝桐清韵，文人精神',
  '针尖锦绣，江南瑰宝',
  '鼓阵铿锵，岭南风采',
  '金石留痕，方寸乾坤',
]
const marqueeNames = [...heritageNames, '打铁花', '木偶戏', '龙舟', '苗绣', '蜡染']

const timelineNodes = [
  { era: '唐', name: '皮影' },
  { era: '宋', name: '剪纸' },
  { era: '明', name: '昆曲' },
  { era: '清', name: '景泰蓝' },
  { era: '今', name: '数字焕新' },
]

const featureList = [
  { label: '非遗地图', desc: '地标检索与路线', icon: MapLocation },
  { label: '知识图谱', desc: '传承关系可视', icon: Share },
  { label: '星火向导', desc: '多模态智能问答', icon: ChatDotRound },
  { label: '研学报告', desc: '行为数据汇总', icon: Document },
]

const statItems = [
  { value: '360+', label: '非遗节点' },
  { value: 'AI', label: '研学向导' },
  { value: '全链', label: '数字焕新' },
]

const floatParticles = Array.from({ length: 18 }, (_, i) => ({
  x: (i * 17 + 5) % 95,
  y: (i * 23 + 10) % 90,
  d: (i % 5) * 0.6,
  dur: 4 + (i % 4),
}))

const floatLanterns = [
  { left: 6, top: 18 },
  { left: 92, top: 22 },
  { left: 4, top: 72 },
  { left: 94, top: 68 },
]

const pageReady = ref(false)
const loginSuccess = ref(false)
const tickerIdx = ref(0)
const litNode = ref(0)
let tickerTimer = null
let nodeTimer = null

const {
  mode,
  loading,
  errorMsg,
  successMsg,
  username,
  password,
  regUsername,
  regPassword,
  rememberMe,
  doLogin,
  doRegister,
} = useAuthForm({
  successDelay: 650,
  onSuccess() {
    loginSuccess.value = true
  },
})

onMounted(() => {
  requestAnimationFrame(() => { pageReady.value = true })
  tickerTimer = setInterval(() => {
    tickerIdx.value = (tickerIdx.value + 1) % heritageNames.length
    litNode.value = tickerIdx.value % timelineNodes.length
  }, 2800)
  nodeTimer = setInterval(() => {
    litNode.value = (litNode.value + 1) % timelineNodes.length
  }, 4000)
})

onUnmounted(() => {
  if (tickerTimer) clearInterval(tickerTimer)
  if (nodeTimer) clearInterval(nodeTimer)
})
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--color-bg-base);
  color: var(--color-text-primary);
}

.bg-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
  animation: orbDrift 18s ease-in-out infinite alternate;
}

.bg-orb--teal {
  width: 420px;
  height: 420px;
  background: rgba(61, 158, 140, 0.35);
  top: -8%;
  left: -6%;
}

.bg-orb--gold {
  width: 360px;
  height: 360px;
  background: rgba(201, 168, 76, 0.22);
  bottom: -10%;
  right: -4%;
  animation-delay: -6s;
}

@keyframes orbDrift {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(30px, -24px) scale(1.08); }
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 70% 60% at 50% 50%, black, transparent);
}

.bg-pattern {
  position: absolute;
  inset: 0;
  opacity: 0.04;
  background-image: url("data:image/svg+xml,%3Csvg width='80' height='80' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 40h80M40 0v80' stroke='%23c9a84c' stroke-width='0.6' fill='none'/%3E%3C/svg%3E");
}

.bg-beam {
  position: absolute;
  top: -20%;
  left: 30%;
  width: 40%;
  height: 50%;
  background: radial-gradient(ellipse at center, rgba(201, 168, 76, 0.12), transparent 70%);
  pointer-events: none;
}

.bg-particle {
  position: absolute;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(201, 168, 76, 0.5);
  box-shadow: 0 0 6px rgba(61, 158, 140, 0.4);
  animation: particleFloat ease-in-out infinite alternate;
}

@keyframes particleFloat {
  from { transform: translateY(0) scale(1); opacity: 0.35; }
  to { transform: translateY(-12px) scale(1.2); opacity: 0.75; }
}

.float-lantern {
  position: absolute;
  width: 28px;
  transform: translate(-50%, -50%);
  animation: lanternFloat 5s ease-in-out infinite;
  opacity: 0.45;
}

.float-lantern-body {
  width: 22px;
  height: 28px;
  margin: 0 auto;
  border-radius: 5px 5px 8px 8px;
  background: linear-gradient(180deg, rgba(201, 168, 76, 0.4), rgba(192, 57, 43, 0.2));
  border: 1px solid rgba(201, 168, 76, 0.3);
}

.float-lantern-glow {
  position: absolute;
  inset: -12px;
  background: radial-gradient(circle, rgba(61, 158, 140, 0.25), transparent 70%);
  animation: glowPulse 3s ease-in-out infinite;
}

@keyframes lanternFloat {
  0%, 100% { transform: translate(-50%, -50%) rotate(-4deg); }
  50% { transform: translate(-50%, calc(-50% - 8px)) rotate(4deg); }
}

@keyframes glowPulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.login-shell {
  position: relative;
  z-index: 1;
  display: flex;
  min-height: 100vh;
  max-width: 1180px;
  margin: 0 auto;
  padding: 48px 28px;
  gap: 0;
  align-items: center;
  justify-content: center;
}

.shell-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  flex-shrink: 0;
  align-self: stretch;
  position: relative;
}

.shell-divider::before {
  content: '';
  position: absolute;
  top: 12%;
  bottom: 12%;
  left: 50%;
  width: 1px;
  background: linear-gradient(180deg, transparent, rgba(201, 168, 76, 0.35), rgba(61, 158, 140, 0.35), transparent);
}

.divider-gem {
  position: relative;
  z-index: 1;
  font-size: 10px;
  color: rgba(201, 168, 76, 0.55);
  text-shadow: 0 0 12px rgba(61, 158, 140, 0.4);
}

.brand-panel {
  position: relative;
  flex: 1;
  max-width: 460px;
  padding-right: 12px;
  opacity: 0;
  transform: translateX(-16px);
  transition: opacity 0.7s ease, transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}

.panel-ornament {
  position: absolute;
  width: 48px;
  height: 48px;
  border: 1px solid rgba(201, 168, 76, 0.2);
  pointer-events: none;
  opacity: 0.6;
}

.panel-ornament--tl {
  top: 0;
  left: 0;
  border-right: none;
  border-bottom: none;
  border-radius: 8px 0 0 0;
}

.panel-ornament--br {
  bottom: 0;
  right: 0;
  border-left: none;
  border-top: none;
  border-radius: 0 0 8px 0;
}

.login-page.ready .brand-panel {
  opacity: 1;
  transform: translateX(0);
}

.brand-mark {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.brand-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(145deg, var(--color-accent-teal), #2a7066);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 8px 28px rgba(61, 158, 140, 0.4);
}

.brand-title {
  font-family: var(--font-serif);
  font-size: clamp(24px, 3vw, 32px);
  letter-spacing: 0.28em;
  text-indent: 0.28em;
  font-weight: 600;
}

.brand-sub {
  font-size: 12px;
  color: var(--color-text-muted);
  letter-spacing: 0.2em;
  margin-top: 6px;
}

.title-ornament {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.title-ornament span {
  display: block;
  height: 2px;
  border-radius: 1px;
  background: linear-gradient(90deg, var(--color-accent-teal), var(--color-accent-gold));
}

.title-ornament span:nth-child(1) { width: 28px; }
.title-ornament span:nth-child(2) { width: 12px; opacity: 0.6; }
.title-ornament span:nth-child(3) { width: 8px; opacity: 0.35; }

.stat-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.stat-item {
  flex: 1;
  padding: 10px 8px;
  text-align: center;
  background: rgba(28, 31, 39, 0.55);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.stat-value {
  display: block;
  font-family: var(--font-serif);
  font-size: 16px;
  color: var(--color-accent-gold);
  letter-spacing: 0.1em;
}

.stat-label {
  display: block;
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 4px;
}

.brand-lead {
  font-size: 14px;
  line-height: 1.75;
  color: var(--color-text-secondary);
  margin-bottom: 28px;
}

.feature-cards {
  list-style: none;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 22px;
}

.feature-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: rgba(28, 31, 39, 0.5);
  transition: border-color 0.25s, background 0.25s, transform 0.25s;
}

.feature-card:hover {
  border-color: rgba(61, 158, 140, 0.45);
  background: rgba(61, 158, 140, 0.08);
  transform: translateY(-2px);
}

.feature-icon {
  font-size: 18px;
  color: var(--color-accent-teal);
  margin-top: 2px;
  flex-shrink: 0;
}

.feature-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.feature-desc {
  display: block;
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.heritage-timeline {
  position: relative;
  padding-left: 20px;
  margin-bottom: 18px;
}

.timeline-line {
  position: absolute;
  left: 5px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: linear-gradient(180deg, var(--color-accent-gold), var(--color-accent-teal));
  opacity: 0.45;
  border-radius: 1px;
}

.timeline-node {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  cursor: default;
  transition: opacity 0.3s;
  opacity: 0.55;
}

.timeline-node.active {
  opacity: 1;
}

.timeline-dot {
  position: absolute;
  left: -20px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-bg-base);
  border: 2px solid var(--color-border);
  transition: border-color 0.3s, box-shadow 0.3s;
}

.timeline-node.active .timeline-dot {
  border-color: var(--color-accent-gold);
  box-shadow: 0 0 10px rgba(201, 168, 76, 0.5);
}

.timeline-era {
  font-size: 10px;
  color: var(--color-text-muted);
  min-width: 24px;
}

.timeline-name {
  font-family: var(--font-serif);
  font-size: 13px;
  letter-spacing: 0.12em;
  color: var(--color-text-secondary);
}

.timeline-node.active .timeline-name {
  color: var(--color-accent-gold);
}

.heritage-ticker {
  position: relative;
  min-height: 52px;
  margin-bottom: 14px;
  overflow: hidden;
}

.ticker-tip {
  margin-top: 32px;
  font-size: 11px;
  color: var(--color-text-muted);
  letter-spacing: 0.12em;
  animation: tipIn 0.4s ease;
}

@keyframes tipIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.marquee-wrap {
  overflow: hidden;
  margin-bottom: 16px;
  mask-image: linear-gradient(90deg, transparent, black 8%, black 92%, transparent);
}

.marquee-track {
  display: flex;
  gap: 10px;
  width: max-content;
  animation: marqueeScroll 28s linear infinite;
}

.marquee-tag {
  flex-shrink: 0;
  font-size: 11px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid rgba(201, 168, 76, 0.2);
  color: var(--color-text-muted);
  background: rgba(22, 25, 32, 0.6);
}

@keyframes marqueeScroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

.ticker-item {
  position: absolute;
  left: 0;
  font-family: var(--font-serif);
  font-size: 18px;
  letter-spacing: 0.35em;
  color: var(--color-accent-gold);
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 0.5s ease, transform 0.5s ease;
}

.ticker-item.active {
  opacity: 1;
  transform: translateY(0);
}

.brand-foot {
  font-size: 11px;
  color: var(--color-text-muted);
  letter-spacing: 0.15em;
}

.form-panel {
  flex: 0 0 auto;
  width: 100%;
  max-width: 420px;
}

.form-card {
  position: relative;
  padding: 32px 30px 26px;
  background: rgba(22, 25, 32, 0.88);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(16px);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.45);
  opacity: 0;
  transform: translateY(18px);
  transition:
    opacity 0.65s ease 0.15s,
    transform 0.65s cubic-bezier(0.22, 1, 0.36, 1) 0.15s,
    box-shadow 0.4s ease;
}

.login-page.ready .form-card {
  opacity: 1;
  transform: translateY(0);
}

.login-page.success .form-card {
  box-shadow:
    0 0 0 1px rgba(201, 168, 76, 0.5),
    0 24px 64px rgba(61, 158, 140, 0.2);
}

.form-card-border {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px;
  background: linear-gradient(
    145deg,
    rgba(201, 168, 76, 0.45),
    rgba(61, 158, 140, 0.25) 50%,
    rgba(201, 168, 76, 0.15)
  );
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.corner {
  position: absolute;
  width: 18px;
  height: 18px;
  border-color: rgba(201, 168, 76, 0.45);
  border-style: solid;
  pointer-events: none;
  opacity: 0.7;
}

.corner--tl { top: 10px; left: 10px; border-width: 2px 0 0 2px; }
.corner--tr { top: 10px; right: 10px; border-width: 2px 2px 0 0; }
.corner--bl { bottom: 10px; left: 10px; border-width: 0 0 2px 2px; }
.corner--br { bottom: 10px; right: 10px; border-width: 0 2px 2px 0; }

.form-seal {
  position: absolute;
  right: 14px;
  bottom: 12px;
  width: 36px;
  height: 36px;
  border: 2px solid rgba(192, 57, 43, 0.45);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotate(-8deg);
  opacity: 0.35;
  pointer-events: none;
}

.form-seal span {
  font-family: var(--font-serif);
  font-size: 16px;
  color: rgba(201, 168, 76, 0.65);
  font-weight: 700;
}

.form-welcome {
  font-size: 12px;
  color: var(--color-accent-teal);
  letter-spacing: 0.25em;
  margin-bottom: 6px;
}

.form-heading {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.12em;
  margin-bottom: 8px;
}

.login-tabs {
  margin-bottom: 16px;
}

.login-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.login-tabs :deep(.el-tabs__nav-wrap::after) {
  background-color: var(--color-border);
}

.login-tabs :deep(.el-tabs__item) {
  color: var(--color-text-secondary);
  letter-spacing: 0.15em;
}

.login-tabs :deep(.el-tabs__item.is-active) {
  color: var(--color-accent-teal);
}

.login-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--color-accent-teal);
}

.form-alert {
  margin-bottom: 12px;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.form-extras {
  margin-bottom: 12px;
  font-size: 12px;
}

.submit-btn {
  width: 100%;
  height: 44px;
  letter-spacing: 0.35em;
  font-size: 15px;
}

.register-btn {
  background: linear-gradient(135deg, #c9a84c, #a88b3a) !important;
  border-color: #c9a84c !important;
}

.switch-tip {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 14px;
}

.switch-tip a {
  color: var(--color-accent-teal);
  text-decoration: none;
}

.switch-tip a:hover {
  color: var(--color-accent-gold-light);
}

.form-footer {
  text-align: center;
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 18px;
}


@media (max-width: 900px) {
  .login-shell {
    flex-direction: column;
    padding: 72px 20px 32px;
    gap: 28px;
  }

  .shell-divider {
    display: none;
  }

  .brand-panel {
    max-width: 100%;
    text-align: center;
    padding-right: 0;
  }

  .brand-mark,
  .stat-row {
    justify-content: center;
  }

  .stat-row {
    max-width: 360px;
    margin-left: auto;
    margin-right: auto;
  }

  .feature-cards {
    max-width: 400px;
    margin-left: auto;
    margin-right: auto;
  }

  .heritage-timeline {
    max-width: 280px;
    margin-left: auto;
    margin-right: auto;
    text-align: left;
  }

  .heritage-ticker {
    text-align: center;
  }

  .ticker-item {
    left: 50%;
    transform: translateX(-50%) translateY(8px);
  }

  .ticker-item.active {
    transform: translateX(-50%) translateY(0);
  }

  .ticker-tip {
    text-align: center;
  }

  .float-lantern {
    opacity: 0.25;
  }

  .form-panel {
    max-width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bg-orb,
  .bg-particle,
  .float-lantern,
  .marquee-track,
  .brand-panel,
  .form-card,
  .ticker-item {
    animation: none !important;
    transition: none !important;
  }

  .login-page.ready .brand-panel,
  .login-page.ready .form-card {
    opacity: 1;
    transform: none;
  }

  .marquee-track {
    transform: none;
  }
}
</style>
