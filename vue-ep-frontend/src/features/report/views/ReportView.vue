<template>
  <div class="page-wrapper report-page">
    <div class="page-header">
      <el-icon class="ph-icon"><Document /></el-icon>
      <div>
        <h2 class="ph-title">非遗研学报告</h2>
        <p class="ph-sub">汇总对话、闯关与打卡数据，生成个性化学习总结</p>
      </div>
      <div style="margin-left:auto">
        <el-button type="primary" :loading="generating" @click="generateReport">
          {{ report ? '重新生成' : '生成报告' }}
        </el-button>
      </div>
    </div>

    <div v-if="generating && !report" class="report-loading">
      <div class="loading-spinner"></div>
      <p>AI 正在撰写您的研学报告…</p>
      <p v-if="streamHint" class="stream-hint">{{ streamHint }}</p>
    </div>

    <div v-else-if="!report && !generating" class="report-empty">
      <div class="empty-icon" aria-hidden="true">报</div>
      <p>暂无报告，点击右上角生成</p>
      <p class="empty-sub">需先有对话、答题或打卡记录</p>
    </div>

    <template v-else-if="report">
      <div class="report-meta">
        生成时间：{{ report.generated_at || '—' }}
        <span v-if="report.stats">
          · 对话 {{ report.stats.sessions }} 次 · 闯关 {{ report.stats.quiz_count }} 次 · 打卡 {{ report.stats.checkin_count }} 处
        </span>
      </div>

      <div class="report-grid">
        <div class="report-card">
          <h3>学习概览</h3>
          <p>{{ report.overview }}</p>
        </div>
        <div class="report-card">
          <h3>知识掌握</h3>
          <p>{{ report.knowledge }}</p>
        </div>
        <div class="report-card">
          <h3>探索足迹</h3>
          <p>{{ report.footprint }}</p>
        </div>
        <div class="report-card">
          <h3>学习建议</h3>
          <p>{{ report.recommendation }}</p>
        </div>
      </div>

      <div v-if="report.artworks?.length" class="report-card art-gallery-card">
        <h3>你的非遗数字创作集</h3>
        <p class="gallery-sub">{{ report.creations_summary }}</p>
        <div class="art-gallery">
          <div v-for="a in report.artworks" :key="a.id" class="art-thumb">
            <img :src="a.image" :alt="a.prompt" />
            <p class="art-prompt">{{ a.prompt }}</p>
            <span class="art-date">{{ a.created_at }}</span>
          </div>
        </div>
      </div>

      <div v-if="keywords.length" class="word-cloud">
        <span
          v-for="(w, i) in keywords"
          :key="w"
          class="cloud-word"
          :style="cloudStyle(i)"
        >{{ w }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import { getLatestReport, generateReportStream } from '@/api'
import { readChatStream } from '@/features/chat/utils/chatStream'

const report = ref(null)
const generating = ref(false)
const streamHint = ref('')

const keywords = computed(() => report.value?.keywords || [])

function cloudStyle(i) {
  const sizes = [22, 18, 16, 14, 20, 15]
  const colors = ['#3d9e8c', '#c9a84c', '#8b7fe8', '#e0c068', '#4aafd4']
  return {
    fontSize: `${sizes[i % sizes.length]}px`,
    color: colors[i % colors.length],
    transform: `rotate(${(i % 3 - 1) * 6}deg)`,
  }
}

async function loadLatest() {
  try {
    const res = await getLatestReport()
    if (res.data.status === 'success' && res.data.report) {
      report.value = res.data.report
    }
  } catch { /* silent */ }
}

async function generateReport() {
  generating.value = true
  streamHint.value = ''
  report.value = null
  try {
    const res = await generateReportStream()
    if (!res.ok) throw new Error('请求失败')
    const draft = {}
    for await (const event of readChatStream(res)) {
      if (event.type === 'error') {
        ElMessage.warning(event.text || '生成失败')
        return
      }
      if (event.type === 'section') {
        draft[event.key] = event.content
        streamHint.value = `正在生成：${event.title}…`
      }
      if (event.type === 'keywords') {
        draft.keywords = event.words
      }
      if (event.type === 'artworks') {
        draft.artworks = event.items
      }
      if (event.type === 'save_warning') {
        ElMessage.warning(event.text || '报告未能写入缓存')
      }
      if (event.type === 'done') {
        report.value = event.report || draft
      }
    }
    if (!report.value) {
      ElMessage.warning('报告内容为空')
    }
  } catch (e) {
    ElMessage.error(e.message || '生成报告失败')
  } finally {
    generating.value = false
    streamHint.value = ''
  }
}

onMounted(loadLatest)
</script>

<style scoped>
@import '@/assets/page-common.css';

.report-page { display: flex; flex-direction: column; gap: 16px; height: 100%; overflow-y: auto; }

.report-loading, .report-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: var(--color-text-muted); gap: 12px;
}
.loading-spinner {
  width: 40px; height: 40px; border: 3px solid var(--color-border);
  border-top-color: var(--color-accent-teal); border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.stream-hint { font-size: 12px; color: var(--color-accent-teal); }
.empty-icon { font-size: 48px; }
.empty-sub { font-size: 12px; }

.report-meta {
  font-size: 12px; color: var(--color-text-muted);
  padding: 8px 12px; background: var(--color-bg-panel);
  border-radius: var(--radius-sm); border: 1px solid var(--color-border);
}

.report-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px;
}
@media (max-width: 900px) { .report-grid { grid-template-columns: 1fr; } }

.report-card {
  padding: 16px; background: var(--color-bg-card);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
}
.report-card h3 {
  font-family: var(--font-serif); font-size: 15px; color: var(--color-accent-gold);
  margin-bottom: 10px;
}
.report-card p { font-size: 13px; line-height: 1.75; color: var(--color-text-secondary); }

.art-gallery-card { margin-top: 4px; }
.gallery-sub { font-size: 12px; color: var(--color-text-muted); margin-bottom: 14px; }
.art-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.art-thumb {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-bg-base);
}
.art-thumb img { width: 100%; height: 120px; object-fit: cover; display: block; }
.art-prompt {
  font-size: 11px; padding: 6px 8px; color: var(--color-text-secondary);
  line-height: 1.4; max-height: 3em; overflow: hidden;
}
.art-date { display: block; font-size: 10px; color: var(--color-text-muted); padding: 0 8px 8px; }

.word-cloud {
  display: flex; flex-wrap: wrap; gap: 16px 24px; justify-content: center;
  padding: 24px; background: var(--color-bg-panel);
  border: 1px solid var(--color-border); border-radius: var(--radius-lg);
  min-height: 100px; align-items: center;
}
.cloud-word { font-family: var(--font-serif); font-weight: 600; }
</style>
