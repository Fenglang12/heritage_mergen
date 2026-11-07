<template>
  <div class="admin-panel">
    <div class="panel-header">
      <div class="panel-title"><el-icon><UserFilled /></el-icon> 用户管理</div>
      <el-input v-model="keyword" placeholder="搜索用户名…" size="small" clearable style="width:200px" @change="load(1)">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <div class="user-table-wrap" v-loading="loading">
      <el-table :data="list"
        :header-cell-style="{ background: 'var(--color-bg-hover)', color: 'var(--color-text-primary)', fontSize: '12px', fontWeight: '600', letterSpacing: '0.04em', padding: '14px 16px' }"
        :row-style="{ background: 'var(--color-bg-card)' }"
        size="default">
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="username" label="用户名" min-width="140">
          <template #default="{ row }">
            <span class="username-cell">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 1 ? 'warning' : 'info'" size="small" effect="light">{{ row.role === 1 ? '管理员' : '用户' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_banned ? 'danger' : 'success'" size="small" effect="light">{{ row.is_banned ? '已封号' : '正常' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="banned_reason" label="封号原因" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="dim-cell">{{ row.banned_reason || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="150">
          <template #default="{ row }">
            <span class="dim-cell">{{ row.created_at }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <template v-if="row.role !== 1">
              <el-button v-if="!row.is_banned" type="danger"  size="small" plain @click="openBan(row)">封号</el-button>
              <el-button v-else                type="success" size="small" plain @click="doUnban(row)">解封</el-button>
            </template>
            <el-tag v-else size="small" type="warning" effect="plain">受保护</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-bar" v-if="totalPages > 1">
      <el-pagination small background layout="prev, pager, next"
        :total="total" :page-size="20" v-model:current-page="page" @current-change="load" />
    </div>

    <el-dialog
      v-model="banVisible"
      width="440px"
      class="heritage-dialog heritage-dialog--form heritage-dialog--danger"
      :show-close="false"
      align-center
      destroy-on-close
    >
      <template #header>
        <div class="admin-dialog-hero admin-dialog-hero--danger">
          <div class="admin-dialog-hero-main">
            <span class="admin-dialog-hero-icon" aria-hidden="true">禁</span>
            <div>
              <div class="admin-dialog-hero-title">填写封号原因</div>
              <p v-if="pendingUser" class="admin-dialog-hero-sub">
                即将限制用户 <em>{{ pendingUser.username }}</em> 的登录与使用
              </p>
            </div>
          </div>
          <button type="button" class="admin-dialog-close" aria-label="关闭" @click="banVisible = false">×</button>
        </div>
      </template>

      <div class="admin-dialog-body">
        <label class="admin-dialog-label">封号说明</label>
        <el-input
          v-model="banReason"
          type="textarea"
          :rows="4"
          maxlength="200"
          show-word-limit
          resize="none"
          class="admin-dialog-field"
          placeholder="例如：发布违规内容、恶意刷屏等……"
        />
        <p class="admin-dialog-hint">提交后将写入用户档案，对方在被解封前可查看此说明。</p>
      </div>

      <template #footer>
        <div class="admin-dialog-footer">
          <el-button class="admin-dialog-btn-ghost" @click="banVisible = false">取消</el-button>
          <el-button type="danger" :loading="acting" @click="doBan">确认封号</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UserFilled, Search } from '@element-plus/icons-vue'
import { adminListUsers, adminBanUser, adminUnbanUser } from '@/api'

const list       = ref([])
const loading    = ref(false)
const page       = ref(1)
const total      = ref(0)
const totalPages = ref(0)
const keyword    = ref('')
const banVisible = ref(false)
const banReason  = ref('')
const acting     = ref(false)
const pendingUser = ref(null)

async function load(p = 1) {
  loading.value = true; page.value = p
  try {
    const res = await adminListUsers(p, keyword.value)
    list.value       = res.data.data
    total.value      = res.data.total
    totalPages.value = res.data.pages
  } finally { loading.value = false }
}

function openBan(user) { pendingUser.value = user; banReason.value = ''; banVisible.value = true }

async function doBan() {
  if (!pendingUser.value) return
  acting.value = true
  try {
    await adminBanUser(pendingUser.value.id, banReason.value || '违反社区规范')
    ElMessage.success(`用户 ${pendingUser.value.username} 已封号`)
    banVisible.value = false; load(page.value)
  } finally { acting.value = false }
}

async function doUnban(user) {
  await ElMessageBox.confirm(`确定解封用户 ${user.username}？`, '提示', { type: 'info' })
  try { await adminUnbanUser(user.id); ElMessage.success('用户已解封'); load(page.value) } catch {}
}

onMounted(load)
</script>

<style scoped>
.admin-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; background: var(--color-bg-base); }
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-panel); flex-shrink: 0;
}
.panel-title { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 700; font-family: var(--font-serif); color: var(--color-text-primary); }
.user-table-wrap { flex: 1; overflow-y: auto; padding: 20px 24px; }

:deep(.el-table) { background: transparent !important; }
:deep(.el-table tr) { background: var(--color-bg-card) !important; }
:deep(.el-table__row:hover td) { background: var(--color-bg-hover) !important; }
:deep(.el-table td) { border-bottom-color: var(--color-border) !important; padding: 13px 16px !important; }
:deep(.el-table th) { border-bottom-color: var(--color-border) !important; }
:deep(.el-table__empty-block) { background: var(--color-bg-card); }

/* Improved text contrast for secondary/dim content */
.username-cell { font-weight: 500; color: var(--color-text-primary); font-size: 13px; }
.dim-cell { color: #6e7491; font-size: 12px; font-variant-numeric: tabular-nums; }

.pagination-bar { display: flex; justify-content: center; padding: 12px; border-top: 1px solid var(--color-border); flex-shrink: 0; }
</style>
