<template>
  <div class="admin-panel">
    <div class="panel-header">
      <div class="panel-title"><el-icon><CameraFilled /></el-icon> 打卡审核</div>
    </div>

    <!-- Large card tab buttons -->
    <div class="status-cards">
      <div
        v-for="tab in statusTabs"
        :key="tab.value"
        class="status-card"
        :class="{ active: checkinStatus === tab.value }"
        @click="switchStatus(tab.value)"
      >
        <el-icon class="status-card-icon"><component :is="tab.icon" /></el-icon>
        <div class="status-card-label">{{ tab.label }}</div>
        <div class="status-card-badge" v-if="tab.value === 0 && pendingCount > 0">
          {{ pendingCount }}
        </div>
      </div>
    </div>

    <div class="review-list" v-loading="loading">
      <div v-if="list.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无记录" :image-size="80" />
      </div>
      <div v-for="item in list" :key="item.id" class="review-card">
        <div class="review-photo" v-if="item.photo_data">
          <el-image :src="item.photo_data" fit="cover" :preview-src-list="[item.photo_data]" preview-teleported />
        </div>
        <div class="review-photo no-img" v-else><el-icon :size="30"><Picture /></el-icon></div>
        <div class="review-body">
          <div class="review-site"><el-icon><Location /></el-icon> {{ item.site_name }}</div>
          <div class="review-meta">{{ item.username }} · {{ item.created_at }}</div>
          <div class="review-desc" v-if="item.description">{{ item.description }}</div>
          <div class="review-reject" v-if="item.reject_reason">拒绝原因：{{ item.reject_reason }}</div>
          <div class="review-actions" v-if="item.status === 0">
            <el-button type="success" size="small" @click="doApprove(item)"><el-icon><Check /></el-icon> 通过</el-button>
            <el-button type="danger"  size="small" @click="openReject(item)"><el-icon><Close /></el-icon> 拒绝</el-button>
          </div>
          <div class="review-actions" v-else>
            <el-tag :type="item.status === 1 ? 'success' : 'danger'" size="small">{{ item.status === 1 ? '已通过' : '已拒绝' }}</el-tag>
            <el-button type="danger" text size="small" @click="doDelete(item.id)" style="margin-left:auto">删除</el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="pagination-bar" v-if="totalPages > 1">
      <el-pagination small background layout="prev, pager, next"
        :total="total" :page-size="15" v-model:current-page="page" @current-change="load" />
    </div>

    <el-dialog
      v-model="rejectVisible"
      width="440px"
      class="heritage-dialog heritage-dialog--form heritage-dialog--warn"
      :show-close="false"
      align-center
      destroy-on-close
    >
      <template #header>
        <div class="admin-dialog-hero admin-dialog-hero--warn">
          <div class="admin-dialog-hero-main">
            <span class="admin-dialog-hero-icon" aria-hidden="true">审</span>
            <div>
              <div class="admin-dialog-hero-title">填写拒绝原因</div>
              <p v-if="pendingItem" class="admin-dialog-hero-sub">
                打卡「<em>{{ pendingItem.site_name }}</em>」将不予通过
              </p>
            </div>
          </div>
          <button type="button" class="admin-dialog-close" aria-label="关闭" @click="rejectVisible = false">×</button>
        </div>
      </template>

      <div class="admin-dialog-body">
        <label class="admin-dialog-label">拒绝说明</label>
        <el-input
          v-model="rejectReason"
          type="textarea"
          :rows="4"
          maxlength="200"
          show-word-limit
          resize="none"
          class="admin-dialog-field"
          placeholder="请说明未通过原因，便于用户修改后重新提交……"
        />
        <p class="admin-dialog-hint">说明将展示在用户的打卡记录中。</p>
      </div>

      <template #footer>
        <div class="admin-dialog-footer">
          <el-button class="admin-dialog-btn-ghost" @click="rejectVisible = false">取消</el-button>
          <el-button type="danger" :loading="acting" @click="doReject">确认拒绝</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CameraFilled, Picture, Location, Check, Close, Clock, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { adminListCheckins, adminReviewCheckin, adminDeleteCheckin, adminGetStats } from '@/api'

const statusTabs = [
  { value: 0, label: '待审核', icon: Clock },
  { value: 1, label: '已通过', icon: CircleCheck },
  { value: 2, label: '已拒绝', icon: CircleClose },
]

const list          = ref([])
const loading       = ref(false)
const page          = ref(1)
const total         = ref(0)
const totalPages    = ref(0)
const checkinStatus = ref(0)
const pendingCount  = ref(0)
const acting        = ref(false)
const rejectVisible = ref(false)
const rejectReason  = ref('')
const pendingItem   = ref(null)

function switchStatus(val) {
  checkinStatus.value = val
  load(1)
}

async function load(p = 1) {
  loading.value = true; page.value = p
  try {
    const res = await adminListCheckins(p, checkinStatus.value)
    list.value       = res.data.data
    total.value      = res.data.total
    totalPages.value = res.data.pages
  } finally { loading.value = false }
}

async function loadStats() {
  try { const r = await adminGetStats(); pendingCount.value = r.data.pending_checkins ?? 0 } catch {}
}

async function doApprove(item) {
  acting.value = true
  try {
    await adminReviewCheckin(item.id, 'approve', '')
    ElMessage.success('打卡已通过审核')
    load(page.value); loadStats()
  } finally { acting.value = false }
}

function openReject(item) { pendingItem.value = item; rejectReason.value = ''; rejectVisible.value = true }

async function doReject() {
  if (!pendingItem.value) return
  if (!rejectReason.value.trim()) { ElMessage.error('请填写拒绝原因'); return }
  acting.value = true
  try {
    await adminReviewCheckin(pendingItem.value.id, 'reject', rejectReason.value)
    ElMessage.success('已拒绝该打卡')
    rejectVisible.value = false
    load(page.value); loadStats()
  } finally { acting.value = false }
}

async function doDelete(cid) {
  await ElMessageBox.confirm('确定要删除该打卡记录？此操作不可撤销。', '警告', { type: 'warning' })
  try { await adminDeleteCheckin(cid); ElMessage.success('已删除'); load(page.value); loadStats() } catch {}
}

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

/* ── Large card status buttons ── */
.status-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
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
  padding: 18px 12px;
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
  font-size: 26px;
  color: var(--color-text-muted);
  transition: color 0.25s;
}
.status-card.active .status-card-icon { color: var(--color-accent-teal); }
.status-card:hover:not(.active) .status-card-icon { color: var(--color-text-secondary); }

.status-card-label {
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-serif);
  color: var(--color-text-secondary);
  transition: color 0.25s;
}
.status-card.active .status-card-label { color: var(--color-accent-teal); }

.status-card-badge {
  position: absolute;
  top: 8px; right: 10px;
  min-width: 18px; height: 18px;
  padding: 0 5px;
  background: var(--color-accent-red);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
}

.review-list {
  flex: 1; overflow-y: auto; padding: 16px 24px;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; align-content: start;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex; align-items: center; justify-content: center;
  min-height: 320px; width: 100%;
}
:deep(.empty-state .el-empty__description p) { color: var(--color-text-secondary) !important; font-size: 14px; }
:deep(.empty-state .el-empty__image svg path) { fill: var(--color-text-muted) !important; }

.review-card { background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; display: flex; flex-direction: column; }
.review-photo { height: 140px; overflow: hidden; background: var(--color-bg-hover); }
.review-photo :deep(.el-image) { width: 100%; height: 100%; }
.review-photo :deep(.el-image__inner) { object-fit: cover; }
.review-photo.no-img { display: flex; align-items: center; justify-content: center; color: var(--color-text-muted); }
.review-body { padding: 10px 12px; display: flex; flex-direction: column; gap: 5px; }
.review-site { display: flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 600; color: var(--color-accent-gold); }
.review-meta { font-size: 11px; color: #6e7491; }
.review-desc { font-size: 12px; color: var(--color-text-secondary); line-height: 1.4; }
.review-reject { font-size: 12px; color: var(--color-accent-red); }
.review-actions { display: flex; gap: 8px; align-items: center; margin-top: 4px; }
.pagination-bar { display: flex; justify-content: center; padding: 10px; border-top: 1px solid var(--color-border); flex-shrink: 0; }
</style>
