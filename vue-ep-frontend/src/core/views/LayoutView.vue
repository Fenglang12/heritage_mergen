<template>
  <div class="layout-root">

    <!-- ── 侧边栏 ──────────────────────────────────────────── -->
    <aside class="sidebar" :class="{ collapsed }">
      <!-- Logo -->
      <div class="sidebar-logo">
        <div class="logo-icon">遗</div>
        <transition name="fade-text">
          <div v-if="!collapsed" class="logo-text">
            <span class="logo-title">时空匠影</span>
            <span class="logo-sub">研学工作站</span>
          </div>
        </transition>
      </div>

      <!-- 导航菜单 -->
      <el-menu
        :default-active="activeRoute"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="sidebar-menu"
      >
        <!-- ── 普通用户菜单（管理员不显示）── -->
        <template v-if="!auth.isAdmin">
          <div class="menu-group">
            <div class="menu-group-label" v-if="!collapsed">探 索</div>
            <el-menu-item index="/map">
              <el-icon><Location /></el-icon>
              <template #title>周边非遗地图</template>
            </el-menu-item>
            <el-menu-item index="/source">
              <el-icon><Picture /></el-icon>
              <template #title>非遗溯源</template>
            </el-menu-item>
          </div>

          <div class="menu-group">
            <div class="menu-group-label" v-if="!collapsed">创 作</div>
            <el-menu-item index="/revive">
              <el-icon><MagicStick /></el-icon>
              <template #title>非遗数字焕新</template>
            </el-menu-item>
          </div>

          <div class="menu-group">
            <div class="menu-group-label" v-if="!collapsed">知 识</div>
            <el-menu-item index="/chat">
              <el-icon><ChatDotRound /></el-icon>
              <template #title>星火向导问答</template>
            </el-menu-item>
            <el-menu-item index="/graph">
              <el-icon><Share /></el-icon>
              <template #title>知识图谱透视</template>
            </el-menu-item>
            <el-menu-item index="/quiz">
              <el-icon><Tickets /></el-icon>
              <template #title>AI闯关答题</template>
            </el-menu-item>
            <el-menu-item index="/report">
              <el-icon><Document /></el-icon>
              <template #title>研学报告</template>
            </el-menu-item>
          </div>

          <div class="menu-group">
            <div class="menu-group-label" v-if="!collapsed">社 区</div>
            <el-menu-item index="/community">
              <el-icon><MapLocation /></el-icon>
              <template #title>打卡广场</template>
            </el-menu-item>
            <el-menu-item index="/feedback">
              <el-icon><Promotion /></el-icon>
              <template #title>意见反馈</template>
            </el-menu-item>
          </div>
        </template>

        <!-- ── 管理员功能（仅管理员可见）── -->
        <template v-if="auth.isAdmin">
          <div class="menu-group">
            <div class="menu-group-label admin-group" v-if="!collapsed">管 理</div>
            <el-menu-item index="/admin/users" class="admin-menu-item">
              <el-icon><UserFilled /></el-icon>
              <template #title>用户管理</template>
            </el-menu-item>
            <el-menu-item index="/admin/checkins" class="admin-menu-item">
              <el-icon><CameraFilled /></el-icon>
              <template #title>打卡审核</template>
            </el-menu-item>
            <el-menu-item index="/admin/feedbacks" class="admin-menu-item">
              <el-icon><ChatDotRound /></el-icon>
              <template #title>反馈处理</template>
            </el-menu-item>
            <el-menu-item index="/admin/heatmap" class="admin-menu-item">
              <el-icon><DataAnalysis /></el-icon>
              <template #title>热力图分析</template>
            </el-menu-item>
          </div>
        </template>
      </el-menu>

      <!-- 底部折叠按钮 + 用户信息 -->
      <div class="sidebar-footer">
        <div class="user-info" v-if="!collapsed">
          <el-avatar :size="28" class="user-avatar">
            {{ auth.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <span class="user-name">{{ auth.username }}</span>
          <el-tag v-if="auth.isAdmin" size="small" type="warning" style="margin-left:2px;padding:0 4px;font-size:10px">管理</el-tag>
          <el-tooltip content="退出登录" placement="top">
            <el-icon class="logout-btn" @click="doLogout"><SwitchButton /></el-icon>
          </el-tooltip>
        </div>
        <el-tooltip v-else content="退出登录" placement="right">
          <el-icon class="logout-btn-solo" @click="doLogout"><SwitchButton /></el-icon>
        </el-tooltip>
        <div class="collapse-btn" @click="collapsed = !collapsed">
          <el-icon><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
        </div>
      </div>
    </aside>

    <!-- ── 主内容区 ─────────────────────────────────────────── -->
    <main class="main-content">
      <!-- 顶部面包屑栏 -->
      <header class="topbar">
        <div class="topbar-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">工作站</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-right">
          <el-tag size="small" type="success">
            <el-icon style="margin-right:4px"><Connection /></el-icon>
            系统运行中
          </el-tag>
          <span class="topbar-time">{{ timeStr }}</span>
        </div>
      </header>

      <!-- 页面内容 -->
      <div class="page-body" style="position:relative">
        <!-- Particle background for non-map pages -->
        <canvas
          v-if="showParticles"
          ref="layoutParticleCanvas"
          class="layout-particle-canvas"
        ></canvas>
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/features/auth/auth'
import { ElMessageBox } from 'element-plus'
import {
  Location, Picture, MagicStick, ChatDotRound, Share,
  MapLocation, Promotion, Setting, Connection, SwitchButton,
  CameraFilled, UserFilled, Tickets, DataAnalysis, Document
} from '@element-plus/icons-vue'

const route  = useRoute()
const router = useRouter()
const auth   = useAuthStore()

const collapsed = ref(false)

const titleMap = {
  '/map':       '周边非遗地图',
  '/source':    '非遗溯源',
  '/revive':    '非遗数字焕新',
  '/chat':      '星火向导问答',
  '/graph':     '知识图谱透视',
  '/quiz':      'AI闯关答题',
  '/report':    '非遗研学报告',
  '/community': '打卡广场',
  '/feedback':  '意见反馈',
  '/admin/checkins':  '打卡审核',
  '/admin/feedbacks': '反馈处理',
  '/admin/users':     '用户管理',
  '/admin/heatmap':   '热力图分析',
}

const activeRoute      = computed(() => route.path)
const currentPageTitle = computed(() => titleMap[route.path] || '工作站')

// 实时时间
const timeStr = ref('')
let timer = null
function updateTime() {
  timeStr.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}
onMounted(() => { updateTime(); timer = setInterval(updateTime, 1000); if (showParticles.value) startLayoutParticles() })
onUnmounted(() => { clearInterval(timer); if (cleanupLayoutParticles) cleanupLayoutParticles() })

// ── Particle background (non-map pages) ──
const NO_PARTICLE_ROUTES = new Set(['/map', '/graph', '/community'])
const showParticles = computed(() => !NO_PARTICLE_ROUTES.has(route.path))
const layoutParticleCanvas = ref(null)
let layoutAnimId = null
let cleanupLayoutParticles = null

function startLayoutParticles() {
  nextTick(() => {
    const canvas = layoutParticleCanvas.value
    if (!canvas) return
    if (cleanupLayoutParticles) { cleanupLayoutParticles(); cleanupLayoutParticles = null }
    const ctx = canvas.getContext('2d')
    let W = canvas.width  = canvas.offsetWidth
    let H = canvas.height = canvas.offsetHeight

    const COLORS = ['rgba(61,158,140,', 'rgba(201,168,76,', 'rgba(192,57,43,']
    const count = Math.max(30, Math.floor((W * H) / 18000))
    const pts = Array.from({ length: count }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      r: Math.random() * 1.2 + 0.3,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      alpha: Math.random() * 0.4 + 0.1,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
    }))
    const LINK = 80
    const onResize = () => {
      W = canvas.width  = canvas.offsetWidth
      H = canvas.height = canvas.offsetHeight
    }
    window.addEventListener('resize', onResize)
    function draw() {
      ctx.clearRect(0, 0, W, H)
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y
          const d = Math.sqrt(dx*dx + dy*dy)
          if (d < LINK) {
            ctx.beginPath()
            ctx.strokeStyle = `rgba(61,158,140,${0.1 * (1 - d / LINK)})`
            ctx.lineWidth = 0.5
            ctx.moveTo(pts[i].x, pts[i].y)
            ctx.lineTo(pts[j].x, pts[j].y)
            ctx.stroke()
          }
        }
      }
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy
        if (p.x < 0) p.x = W; if (p.x > W) p.x = 0
        if (p.y < 0) p.y = H; if (p.y > H) p.y = 0
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = p.color + p.alpha + ')'
        ctx.fill()
      }
      layoutAnimId = requestAnimationFrame(draw)
    }
    draw()
    cleanupLayoutParticles = () => {
      cancelAnimationFrame(layoutAnimId)
      window.removeEventListener('resize', onResize)
    }
  })
}

watch(showParticles, (val) => {
  if (!val && cleanupLayoutParticles) { cleanupLayoutParticles(); cleanupLayoutParticles = null }
  else if (val) startLayoutParticles()
}, { immediate: false })

watch(layoutParticleCanvas, (canvas) => {
  if (canvas) startLayoutParticles()
})

async function doLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
      confirmButtonText: '确定退出',
      cancelButtonText:  '取消',
      type:              'warning',
      center:            true,
      customClass:       'logout-dialog',
      message:           '退出后需要重新登录才能访问系统。',
    })
    await auth.logout()
    router.push('/login')
  } catch {
    // 用户点了取消，不做任何事
  }
}
</script>

<style scoped>
.layout-root {
  display: flex;
  width: 100vw; height: 100vh;
  overflow: hidden;
  background: var(--color-bg-base);
  /* 与右侧面板留出边距，侧边不贴死视口边缘 */
  padding: 10px 0 10px 10px;
  gap: 10px;
  box-sizing: border-box;
}

/* ── 侧边栏（圆角/边框与地图侧栏面板一致）──────────────── */
.sidebar {
  --sidebar-pad-x: 14px;
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-panel);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: width 0.25s ease;
  overflow: hidden;
}
.sidebar.collapsed { width: 64px; }

/* Logo：与菜单项左缘对齐 */
.sidebar-logo {
  min-height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px var(--sidebar-pad-x);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.logo-icon {
  width: 32px; height: 32px; border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--color-accent-teal), #2a7066);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-serif); font-size: 15px; color: #fff;
  flex-shrink: 0;
}
.logo-text { display: flex; flex-direction: column; gap: 2px; overflow: hidden; }
.logo-title {
  font-family: var(--font-serif); font-size: 15px; font-weight: 600;
  color: var(--color-accent-gold); letter-spacing: 0.5px; white-space: nowrap;
  line-height: 1.2;
}
.logo-sub {
  font-size: 10px; color: var(--color-text-muted);
  letter-spacing: 1px; white-space: nowrap; line-height: 1.2;
}

/* 菜单滚动区 */
.sidebar-menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 0 6px;
  border-right: none !important;
}

/* 分组：组内紧凑，组间拉开 */
.menu-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 6px;
}
.menu-group + .menu-group {
  margin-top: 14px;
}

.menu-group-label {
  font-size: 10px;
  letter-spacing: 0.8px;
  color: var(--color-text-muted);
  /* 与菜单文字对齐：左内边距 ≈ 图标区 + 间距 */
  padding: 2px 10px 6px 12px;
  line-height: 1.2;
  user-select: none;
}
.admin-group { color: var(--color-accent-gold); opacity: 0.85; }

/* 菜单行：呼吸感 + 可点区域 */
.sidebar-menu :deep(.el-menu-item) {
  height: auto !important;
  min-height: 40px;
  line-height: 1.35 !important;
  margin: 0 !important;
  padding: 9px 12px !important;
  border-radius: var(--radius-sm) !important;
  font-size: 13px !important;
  display: flex !important;
  align-items: center !important;
  gap: 10px !important;
  border-left: none !important;
}
.sidebar-menu :deep(.el-menu-item .el-icon) {
  font-size: 15px !important;
  width: 15px !important;
  height: 15px !important;
  margin: 0 !important;
  flex-shrink: 0;
}
.sidebar-menu :deep(.el-menu-item .el-menu-tooltip__trigger) {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 0 !important;
}
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(61,158,140,0.18) 0%, rgba(61,158,140,0.06) 100%) !important;
  color: var(--color-accent-teal) !important;
  box-shadow: inset 2px 0 0 var(--color-accent-teal);
}

/* 管理员菜单项高亮 */
:deep(.admin-menu-item) { color: var(--color-accent-gold) !important; }
:deep(.admin-menu-item .el-icon) { color: var(--color-accent-gold) !important; }

/* 底部 */
.sidebar-footer {
  border-top: 1px solid var(--color-border);
  padding: 10px var(--sidebar-pad-x) 12px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.user-info {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 8px; border-radius: var(--radius-sm);
}
.user-avatar {
  background: linear-gradient(135deg, var(--color-accent-gold), #a88030) !important;
  color: #fff !important;
  font-family: var(--font-serif);
  font-size: 13px;
  flex-shrink: 0;
}
.user-name {
  font-size: 13px; color: var(--color-text-secondary);
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.logout-btn { color: var(--color-text-muted); cursor: pointer; font-size: 15px; }
.logout-btn:hover { color: #c0392b; }
.logout-btn-solo {
  display: flex; align-items: center; justify-content: center;
  color: var(--color-text-muted); cursor: pointer; font-size: 16px;
  padding: 8px; border-radius: var(--radius-sm);
}
.logout-btn-solo:hover { color: #c0392b; background: var(--color-bg-hover); }

.collapse-btn {
  display: flex; align-items: center; justify-content: center;
  padding: 9px; border-radius: var(--radius-sm);
  color: var(--color-text-muted); cursor: pointer;
  transition: color 0.2s, background-color 0.2s;
  font-size: 15px;
}
.collapse-btn:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }

/* ── 主内容 ──────────────────────────────────────────────── */
.layout-particle-canvas {
  position: absolute;
  inset: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 0;
}

.main-content {
  flex: 1; display: flex; flex-direction: column;
  overflow: hidden; min-width: 0;
  /* 右侧主区同样圆角，与侧边视觉统一 */
  margin-right: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-base);
}

.topbar {
  height: 52px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px;
  background: var(--color-bg-panel);
  border-bottom: 1px solid var(--color-border);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}
.topbar-left :deep(.el-breadcrumb__inner) { color: var(--color-text-secondary); font-size: 13px; }
.topbar-left :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) { color: var(--color-text-primary); }
.topbar-left :deep(.el-breadcrumb__separator) { color: var(--color-text-muted); }

.topbar-right { display: flex; align-items: center; gap: 16px; }
.topbar-time { font-family: var(--font-mono); font-size: 13px; color: var(--color-text-muted); }

.page-body { flex: 1; overflow: hidden; }

/* 页面切换动画 */
.page-fade-enter-active,
.page-fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.page-fade-enter-from { opacity: 0; transform: translateY(6px); }
.page-fade-leave-to   { opacity: 0; transform: translateY(-6px); }

/* Logo 文字淡入淡出 */
.fade-text-enter-active,
.fade-text-leave-active { transition: opacity 0.2s; }
.fade-text-enter-from,
.fade-text-leave-to { opacity: 0; }
</style>

<!-- 退出弹窗全局样式（不能 scoped，因为 ElMessageBox 挂载在 body） -->
<style>
.logout-dialog {
  border-radius: 18px !important;
  padding: 10px 8px 4px !important;
  min-width: 380px !important;
  box-shadow: 0 24px 60px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.06) !important;
  background: var(--color-bg-panel, #1e1e2e) !important;
  border: 1px solid var(--color-border, #2d2d42) !important;
}
.logout-dialog .el-message-box__header {
  padding: 20px 24px 12px !important;
  border-bottom: 1px solid var(--color-border, #2d2d42) !important;
}
.logout-dialog .el-message-box__title {
  font-size: 17px !important;
  font-weight: 600 !important;
  color: var(--color-text-primary, #fff) !important;
  letter-spacing: 0.5px !important;
}
.logout-dialog .el-message-box__content {
  padding: 20px 24px !important;
}
.logout-dialog .el-message-box__message p {
  font-size: 14px !important;
  color: var(--color-text-secondary, #b0b4c8) !important;
  line-height: 1.6 !important;
}
.logout-dialog .el-message-box__status.el-icon {
  font-size: 22px !important;
  color: #e6a23c !important;
}
.logout-dialog .el-message-box__btns {
  padding: 12px 24px 22px !important;
  gap: 10px !important;
  display: flex;
  justify-content: center;
}
.logout-dialog .el-message-box__btns .el-button {
  border-radius: 10px !important;
  height: 40px !important;
  min-width: 110px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
}
.logout-dialog .el-message-box__btns .el-button--primary {
  background: linear-gradient(135deg, #3D9E8C, #2a7a70) !important;
  border-color: transparent !important;
  box-shadow: 0 4px 14px rgba(61,158,140,0.4) !important;
}
.logout-dialog .el-message-box__btns .el-button--primary:hover {
  box-shadow: 0 6px 18px rgba(61,158,140,0.55) !important;
  transform: translateY(-1px);
}
.logout-dialog .el-message-box__btns .el-button:not(.el-button--primary) {
  background: transparent !important;
  border-color: var(--color-border, #2d2d42) !important;
  color: var(--color-text-secondary, #b0b4c8) !important;
}
.logout-dialog .el-overlay {
  backdrop-filter: blur(4px) !important;
}
</style>
