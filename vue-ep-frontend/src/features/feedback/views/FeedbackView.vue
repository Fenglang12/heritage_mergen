<template>
  <div class="feedback-root">
    <!-- Particle background canvas -->
    <canvas ref="particleCanvas" class="particle-canvas"></canvas>

    <!-- ── 左：提交反馈 ─────────────────────────────────────── -->
    <div class="fb-left">
      <div class="panel-title">
        <el-icon><ChatDotRound /></el-icon> 提交反馈
      </div>
      <p class="panel-sub">您的每一条建议都是我们进步的动力</p>

      <el-form :model="form" label-width="80px" size="default" class="fb-form">
        <el-form-item label="反馈类型">
          <!-- Styled card-style type selector -->
          <div class="type-selector">
            <div
              v-for="t in feedbackTypes"
              :key="t.value"
              class="type-card"
              :class="['type-card--' + t.value, { active: form.type === t.value }]"
              @click="form.type = t.value"
            >
              <el-icon class="type-card-icon"><component :is="t.icon" /></el-icon>
              <span class="type-card-label">{{ t.label }}</span>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="反馈标题" required>
          <el-input
            v-model="form.title"
            placeholder="请简要描述您的反馈（最多100字）"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="详细描述" required>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="6"
            placeholder="请详细描述您遇到的问题或建议……"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="doSubmit" style="width:100%">
            <el-icon><Promotion /></el-icon> 提交反馈
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="submitted"
        title="反馈已提交，感谢您的宝贵意见！管理员将尽快处理。"
        type="success"
        show-icon
        :closable="false"
        style="margin-top:12px"
      />
    </div>

    <!-- ── 右：我的反馈记录 ─────────────────────────────────── -->
    <div class="fb-right">
      <div class="panel-title">
        <el-icon><Tickets /></el-icon> 我的反馈记录
      </div>

      <div class="fb-list" v-loading="listLoading">
        <div v-if="feedbacks.length === 0 && !listLoading" class="empty-hint">
          <el-empty description="暂无反馈记录" :image-size="70" />
        </div>

        <div v-for="fb in feedbacks" :key="fb.id" class="fb-card">
          <div class="fb-card-top">
            <el-tag :type="typeColor(fb.type)" size="small">{{ typeLabel(fb.type) }}</el-tag>
            <el-tag :type="statusColor(fb.status)" size="small" style="margin-left:6px">
              {{ statusLabel(fb.status) }}
            </el-tag>
            <span class="fb-time">{{ fb.created_at }}</span>
          </div>
          <div class="fb-card-title">{{ fb.title }}</div>
          <div class="fb-card-content">{{ fb.content }}</div>

          <div v-if="fb.admin_reply" class="fb-reply">
            <div class="reply-label"><el-icon><Service /></el-icon> 官方回复</div>
            <div class="reply-content">{{ fb.admin_reply }}</div>
            <div class="reply-time">{{ fb.replied_at }}</div>
          </div>
        </div>
      </div>

      <div class="pagination-bar" v-if="totalPages > 1">
        <el-pagination
          small background layout="prev, pager, next"
          :total="totalCount" :page-size="10"
          v-model:current-page="currentPage"
          @current-change="loadFeedbacks"
        />
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Tickets, Promotion, Service, Star, Warning, Opportunity, More } from '@element-plus/icons-vue'
import { submitFeedback, getMyFeedbacks } from '@/api'

const feedbackTypes = [
  { value: 'general',    label: '综合',   icon: Star },
  { value: 'bug',        label: '问题',   icon: Warning },
  { value: 'suggestion', label: '建议',   icon: Opportunity },
  { value: 'other',      label: '其他',   icon: More },
]

const form = ref({ type: 'general', title: '', content: '' })
const submitting = ref(false)
const submitted  = ref(false)

async function doSubmit() {
  if (!form.value.title.trim())   { ElMessage.error('请填写反馈标题'); return }
  if (!form.value.content.trim()) { ElMessage.error('请填写详细描述'); return }
  submitting.value = true
  submitted.value  = false
  try {
    const res = await submitFeedback(form.value)
    if (res.data.status === 'success') {
      submitted.value = true
      form.value = { type: 'general', title: '', content: '' }
      loadFeedbacks()
    } else {
      ElMessage.error(res.data.msg)
    }
  } finally {
    submitting.value = false
  }
}

const feedbacks    = ref([])
const listLoading  = ref(false)
const currentPage  = ref(1)
const totalCount   = ref(0)
const totalPages   = ref(0)

async function loadFeedbacks(page = 1) {
  listLoading.value = true
  currentPage.value = page
  try {
    const res = await getMyFeedbacks(page)
    feedbacks.value  = res.data.data
    totalCount.value = res.data.total
    totalPages.value = res.data.pages
  } finally {
    listLoading.value = false
  }
}

const typeLabel  = (t) => ({ general:'综合', bug:'问题', suggestion:'建议', other:'其他' }[t] || t)
const typeColor  = (t) => ({ general:'info', bug:'danger', suggestion:'success', other:'' }[t] || '')
const statusLabel = (s) => ({ 0:'待处理', 1:'已处理', 2:'已忽略' }[s] || '未知')
const statusColor = (s) => ({ 0:'warning', 1:'success', 2:'info' }[s] || '')

// ── Particle background ──
const particleCanvas = ref(null)
let animId = null

function initParticles() {
  const canvas = particleCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  let W = canvas.width  = canvas.offsetWidth
  let H = canvas.height = canvas.offsetHeight

  const COLORS = ['rgba(61,158,140,', 'rgba(201,168,76,', 'rgba(192,57,43,']
  const count = Math.floor((W * H) / 14000)

  const particles = Array.from({ length: count }, () => ({
    x: Math.random() * W,
    y: Math.random() * H,
    r: Math.random() * 1.5 + 0.4,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    alpha: Math.random() * 0.5 + 0.15,
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
  }))

  const onResize = () => {
    W = canvas.width  = canvas.offsetWidth
    H = canvas.height = canvas.offsetHeight
  }
  window.addEventListener('resize', onResize)

  const LINK_DIST = 90

  function draw() {
    ctx.clearRect(0, 0, W, H)

    // draw links
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const d  = Math.sqrt(dx * dx + dy * dy)
        if (d < LINK_DIST) {
          ctx.beginPath()
          ctx.strokeStyle = `rgba(61,158,140,${0.12 * (1 - d / LINK_DIST)})`
          ctx.lineWidth = 0.6
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.stroke()
        }
      }
    }

    // draw dots
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy
      if (p.x < 0) p.x = W; if (p.x > W) p.x = 0
      if (p.y < 0) p.y = H; if (p.y > H) p.y = 0
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = p.color + p.alpha + ')'
      ctx.fill()
    }

    animId = requestAnimationFrame(draw)
  }

  draw()

  return () => {
    cancelAnimationFrame(animId)
    window.removeEventListener('resize', onResize)
  }
}

let cleanupParticles = null
onMounted(() => {
  loadFeedbacks()
  cleanupParticles = initParticles()
})
onBeforeUnmount(() => {
  if (cleanupParticles) cleanupParticles()
})
</script>

<style scoped>
.feedback-root {
  position: relative;
  display: flex; gap: 0; height: 100%; overflow: hidden;
  background: var(--color-bg-base);
}

.particle-canvas {
  position: absolute;
  inset: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 0;
}

.fb-left, .fb-right { position: relative; z-index: 1; }

.fb-left {
  width: 420px; flex-shrink: 0; padding: 24px;
  border-right: 1px solid var(--color-border);
  overflow-y: auto; background: rgba(22,25,32,0.88);
  backdrop-filter: blur(6px);
}
.fb-right {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
  background: rgba(14,16,21,0.7);
  backdrop-filter: blur(4px);
}

.panel-title {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-serif); font-size: 17px;
  color: var(--color-accent-gold); margin-bottom: 6px;
}
.panel-sub { font-size: 13px; color: var(--color-text-muted); margin-bottom: 20px; }

.fb-form { margin-top: 8px; }

/* ── Feedback type card selector ── */
.type-selector {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  width: 100%;
}

.type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 6px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  cursor: pointer;
  transition: color 0.22s ease, background-color 0.22s ease, border-color 0.22s ease;
  user-select: none;
}

.type-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.type-card-icon { font-size: 18px; transition: color 0.22s; }
.type-card-label { font-size: 12px; font-weight: 500; color: var(--color-text-secondary); transition: color 0.22s; }

/* type-specific accent colors */
.type-card--general       { border-color: rgba(61,158,140,0.25); }
.type-card--general .type-card-icon { color: var(--color-accent-teal); }
.type-card--general.active {
  background: rgba(61,158,140,0.15);
  border-color: var(--color-accent-teal);
  box-shadow: none;
}

.type-card--bug           { border-color: rgba(192,57,43,0.25); }
.type-card--bug .type-card-icon { color: var(--color-accent-red); }
.type-card--bug.active {
  background: rgba(192,57,43,0.12);
  border-color: var(--color-accent-red);
  box-shadow: none;
}

.type-card--suggestion    { border-color: rgba(201,168,76,0.25); }
.type-card--suggestion .type-card-icon { color: var(--color-accent-gold); }
.type-card--suggestion.active {
  background: rgba(201,168,76,0.12);
  border-color: var(--color-accent-gold);
  box-shadow: none;
}

.type-card--other         { border-color: rgba(138,143,168,0.2); }
.type-card--other .type-card-icon { color: var(--color-text-secondary); }
.type-card--other.active {
  background: rgba(138,143,168,0.1);
  border-color: var(--color-text-secondary);
  box-shadow: none;
}

.type-card.active .type-card-label { color: var(--color-text-primary); font-weight: 600; }

/* ── List panel ── */
.fb-list {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.fb-card {
  background: var(--color-bg-card); border-radius: var(--radius-md);
  border: 1px solid var(--color-border); padding: 14px 16px;
  display: flex; flex-direction: column; gap: 8px;
}
.fb-card-top { display: flex; align-items: center; }
.fb-time { margin-left: auto; font-size: 11px; color: var(--color-text-muted); }
.fb-card-title { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.fb-card-content {
  font-size: 13px; color: var(--color-text-secondary); line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}

.fb-reply {
  background: var(--color-bg-hover); border-left: 3px solid var(--color-accent-teal);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0; padding: 8px 12px;
  display: flex; flex-direction: column; gap: 4px;
}
.reply-label { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--color-accent-teal); font-weight: 600; }
.reply-content { font-size: 13px; color: var(--color-text-primary); line-height: 1.5; }
.reply-time { font-size: 11px; color: var(--color-text-muted); text-align: right; }

.empty-hint { text-align: center; padding: 40px 0; }

.pagination-bar {
  display: flex; justify-content: center; padding: 10px;
  border-top: 1px solid var(--color-border); flex-shrink: 0;
}
</style>
