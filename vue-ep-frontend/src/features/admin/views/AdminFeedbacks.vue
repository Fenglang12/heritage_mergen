<template>
  <div class="admin-panel">
    <div class="panel-header">
      <div class="panel-title"><el-icon><ChatDotRound /></el-icon> 反馈处理</div>
    </div>

    <!-- Large card tab buttons -->
    <div class="status-cards">
      <div
        v-for="tab in statusTabs"
        :key="String(tab.value)"
        class="status-card"
        :class="{ active: statusFilter === tab.value }"
        @click="switchStatus(tab.value)"
      >
        <el-icon class="status-card-icon"><component :is="tab.icon" /></el-icon>
        <div class="status-card-label">{{ tab.label }}</div>
        <div class="status-card-badge" v-if="tab.value === 0 && pendingCount > 0">
          {{ pendingCount }}
        </div>
      </div>
    </div>

    <div class="fb-list" v-loading="loading">
      <div v-if="list.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无反馈" :image-size="80" />
      </div>
      <div v-for="fb in list" :key="fb.id" class="fb-card">
        <div class="fba-top">
          <el-tag :type="typeColor(fb.type)" size="small" effect="light">{{ typeLabel(fb.type) }}</el-tag>
          <el-tag :type="statusColor(fb.status)" size="small" effect="light" style="margin-left:6px">{{ statusLabel(fb.status) }}</el-tag>
          <span class="fba-user">来自：{{ fb.username }}</span>
          <span class="fba-time">{{ fb.created_at }}</span>
        </div>
        <div class="fba-title">{{ fb.title }}</div>
        <div class="fba-content">{{ fb.content }}</div>
        <div v-if="fb.admin_reply" class="fba-reply">
          <el-icon><Service /></el-icon> {{ fb.admin_reply }}
          <span style="margin-left:8px;font-size:11px;color:var(--color-text-muted)">{{ fb.replied_at }}</span>
        </div>
        <div class="fba-actions" v-if="fb.status === 0">
          <el-input v-model="fb._reply" placeholder="输入回复内容（可选）" size="small" class="fba-input" />
          <div class="fba-btn-group">
            <el-button type="success" size="small" @click="doReply(fb, 1)">
              <el-icon style="margin-right:4px"><CircleCheck /></el-icon>标为已处理
            </el-button>
            <el-button type="info" size="small" plain @click="doReply(fb, 2)">
              <el-icon style="margin-right:4px"><Remove /></el-icon>忽略
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="pagination-bar" v-if="totalPages > 1">
      <el-pagination small background layout="prev, pager, next"
        :total="total" :page-size="15" v-model:current-page="page" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Service, CircleCheck, Remove, List, Finished, SwitchButton } from '@element-plus/icons-vue'
import { adminListFeedbacks, adminReplyFeedback, adminGetStats } from '@/api'

const statusTabs = [
  { value: null, label: '全部',   icon: List },
  { value: 0,    label: '待处理', icon: SwitchButton },
  { value: 1,    label: '已处理', icon: Finished },
  { value: 2,    label: '已忽略', icon: Remove },
]

const list         = ref([])
const loading      = ref(false)
const page         = ref(1)
const total        = ref(0)
const totalPages   = ref(0)
const statusFilter = ref(0)
const pendingCount = ref(0)

function switchStatus(val) {
  statusFilter.value = val
  load(1)
}

async function load(p = 1) {
  loading.value = true; page.value = p
  try {
    const res = await adminListFeedbacks(p, statusFilter.value)
    list.value       = res.data.data.map(f => ({ ...f, _reply: '' }))
    total.value      = res.data.total
    totalPages.value = res.data.pages
  } finally { loading.value = false }
}

async function loadStats() {
  try { const r = await adminGetStats(); pendingCount.value = r.data.pending_feedbacks ?? 0 } catch {}
}

async function doReply(fb, status) {
  try {
    await adminReplyFeedback(fb.id, fb._reply || '', status)
    ElMessage.success(status === 1 ? '已标为已处理' : '已忽略')
    load(page.value); loadStats()
  } catch {}
}

const typeLabel   = (t) => ({ general:'综合', bug:'问题', suggestion:'建议', other:'其他' }[t] || t)
const typeColor   = (t) => ({ general:'info', bug:'danger', suggestion:'success', other:'' }[t] || '')
const statusLabel = (s) => ({ 0:'待处理', 1:'已处理', 2:'已忽略' }[s] || '')
const statusColor = (s) => ({ 0:'warning', 1:'success', 2:'info' }[s] || '')

onMounted(() => { load(); loadStats() })
</script>

<style scoped>
.admin-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; background: var(--color-bg-base); }
.panel-header {
  display: flex; align-items: center;
  padding: 14px 24px; border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-panel); flex-shrink: 0;
}
.panel-title { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 700; font-family: var(--font-serif); color: var(--color-text-primary); }

/* ── Large card status buttons (4 cols for feedback) ── */
.status-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 16px 24px;
  background: var(--color-bg-panel);
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.status-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  cursor: pointer;
  transition: all 0.25s ease;
  user-select: none;
}

.status-card:hover {
  border-color: var(--color-accent-teal);
  background: var(--color-bg-hover);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

.status-card.active {
  border-color: var(--color-accent-teal);
  background: linear-gradient(135deg, rgba(61,158,140,0.18) 0%, rgba(61,158,140,0.06) 100%);
  box-shadow: 0 4px 16px rgba(61,158,140,0.2), inset 0 0 0 1px rgba(61,158,140,0.3);
}

.status-card-icon {
  font-size: 22px;
  color: var(--color-text-muted);
  transition: color 0.25s;
}
.status-card.active .status-card-icon { color: var(--color-accent-teal); }
.status-card:hover:not(.active) .status-card-icon { color: var(--color-text-secondary); }

.status-card-label {
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-serif);
  color: var(--color-text-secondary);
  transition: color 0.25s;
}
.status-card.active .status-card-label { color: var(--color-accent-teal); }

.status-card-badge {
  position: absolute;
  top: 7px; right: 9px;
  min-width: 18px; height: 18px;
  padding: 0 5px;
  background: var(--color-accent-red);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
}

.fb-list { flex: 1; overflow-y: auto; padding: 16px 24px; display: flex; flex-direction: column; gap: 12px; }

.empty-state {
  display: flex; align-items: center; justify-content: center;
  flex: 1; min-height: 320px;
}
:deep(.empty-state .el-empty__description p) { color: var(--color-text-secondary) !important; font-size: 14px; }

.fb-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex; flex-direction: column; gap: 8px;
  transition: border-color 0.2s;
}
.fb-card:hover { border-color: var(--color-border-soft); }

.fba-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fba-user { font-size: 12px; color: var(--color-accent-teal); }
.fba-time { margin-left: auto; font-size: 11px; color: #6e7491; white-space: nowrap; }
.fba-title { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.fba-content { font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; }
.fba-reply {
  display: flex; align-items: flex-start; gap: 6px;
  padding: 8px 12px;
  background: rgba(61,158,140,0.08);
  border-left: 2px solid var(--color-accent-teal);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 12px; color: var(--color-accent-teal); line-height: 1.5;
}
.fba-actions {
  display: flex; align-items: center; gap: 10px;
  padding-top: 6px;
  border-top: 1px solid var(--color-border-soft);
  margin-top: 2px; flex-wrap: wrap;
}
.fba-input { flex: 1; min-width: 160px; }
.fba-btn-group { display: flex; gap: 8px; flex-shrink: 0; }
:deep(.fba-btn-group .el-button) { border-radius: var(--radius-sm); font-size: 12px; padding: 6px 14px; }

.pagination-bar { display: flex; justify-content: center; padding: 12px; border-top: 1px solid var(--color-border); flex-shrink: 0; }
</style>
