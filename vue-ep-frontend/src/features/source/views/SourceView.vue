<template>
  <div class="page-wrapper">
    <div class="page-header">
      <el-icon class="ph-icon"><Picture /></el-icon>
      <div>
        <h2 class="ph-title">非遗识别溯源</h2>
        <p class="ph-sub">上传图片或视频，AI 识别非遗技艺并在地图上标记发源地</p>
      </div>
    </div>

    <div class="source-layout">
      <!-- 左：上传 & 操作 -->
      <div class="source-left">
        <el-card shadow="never" class="upload-card">

          <!-- 模式切换 Tab -->
          <div class="mode-tabs">
            <div
              class="mode-tab"
              :class="{ active: mode === 'image' }"
              @click="switchMode('image')"
            >
              <el-icon><Picture /></el-icon>
              图片识别
            </div>
            <div
              class="mode-tab"
              :class="{ active: mode === 'video' }"
              @click="switchMode('video')"
            >
              <el-icon><VideoPlay /></el-icon>
              视频理解
            </div>
          </div>

          <!-- ── 图片上传区 ── -->
          <template v-if="mode === 'image'">
            <p class="card-label">上传图片</p>
            <el-upload
              drag accept="image/*"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="onImageChange"
              class="uploader"
            >
              <div v-if="!imagePreviewUrl" class="upload-placeholder">
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <p>拖拽图片至此处，或 <em>点击上传</em></p>
                <p class="upload-hint">支持 JPG、PNG、WEBP</p>
              </div>
              <img v-else :src="imagePreviewUrl" class="preview-img" />
            </el-upload>

            <VoiceInputBar
              label="语音补充描述"
              hint="可选，帮助 AI 更准确识别"
              @text="voiceHint = $event"
            />
            <p v-if="voiceHint" class="voice-hint-text">{{ voiceHint }}</p>

            <el-button
              type="primary" size="large" :loading="loading"
              :disabled="!imageB64" @click="runImageSource"
              style="width:100%; margin-top:14px; letter-spacing:2px;"
            >
              <el-icon v-if="!loading"><Search /></el-icon>
              {{ loading ? '正在识别分析...' : '识图溯源 · 打点地图' }}
            </el-button>
          </template>

          <!-- ── 视频上传区 ── -->
          <template v-else>
            <p class="card-label">上传视频</p>
            <el-upload
              drag accept="video/*"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="onVideoChange"
              class="uploader"
            >
              <div v-if="!videoFile" class="upload-placeholder">
                <el-icon class="upload-icon"><VideoPlay /></el-icon>
                <p>拖拽视频至此处，或 <em>点击上传</em></p>
                <p class="upload-hint">支持 MP4、MOV、AVI，建议 50MB 以内</p>
              </div>
              <div v-else class="video-selected">
                <video
                  v-if="videoPreviewUrl"
                  :src="videoPreviewUrl"
                  class="preview-video"
                  controls
                  preload="metadata"
                />
                <div class="video-info">
                  <el-icon style="color:var(--color-accent-teal)"><VideoPlay /></el-icon>
                  <span>{{ videoFile.name }}</span>
                  <el-tag size="small" type="info">{{ videoSizeLabel }}</el-tag>
                </div>
              </div>
            </el-upload>

            <!-- 进度条（读取中） -->
            <div v-if="encoding" class="encoding-bar">
              <span class="encoding-label">正在读取视频...</span>
              <el-progress :percentage="encodingProgress" :stroke-width="4" striped striped-flow />
            </div>

            <el-button
              type="primary" size="large" :loading="loading"
              :disabled="!videoB64 || encoding" @click="runVideoSource"
              style="width:100%; margin-top:14px; letter-spacing:2px;"
            >
              <el-icon v-if="!loading"><Search /></el-icon>
              {{ loading ? '正在分析视频内容...' : '视频溯源 · 打点地图' }}
            </el-button>
            <p v-if="videoFile" class="video-tip">
              <el-icon><InfoFilled /></el-icon>
              视频理解耗时较长（约 30–90 秒），请耐心等待
            </p>
          </template>

        </el-card>
      </div>

      <!-- 右：结果区（图片 / 视频共用） -->
      <div class="source-right">
        <!-- 等待分析 -->
        <el-card v-if="loading" shadow="never" class="loading-result-card">
          <HeritageLoadingPanel :variant="mode === 'video' ? 'video-source' : 'image-source'" />
        </el-card>

        <!-- 空态 -->
        <el-empty
          v-else-if="!aiText"
          :description="mode === 'image' ? '上传图片后，AI 分析结果将在此处显示' : '上传视频后，AI 分析结果将在此处显示'"
          :image-size="80"
        >
          <template #image>
            <el-icon style="font-size:60px; color:var(--color-text-muted)">
              <VideoPlay v-if="mode === 'video'" />
              <Picture v-else />
            </el-icon>
          </template>
        </el-empty>

        <!-- 分析结果 -->
        <template v-else>
          <el-card shadow="never" class="result-card">
            <template #header>
              <div class="result-header">
                <span class="rh-avatar" aria-hidden="true">遗</span>
                <span class="rh-title">
                  非遗智能向导 · {{ mode === 'video' ? '视频分析报告' : '识别报告' }}
                </span>
                <el-tag size="small" style="margin-left:auto;">{{ identifiedCity }}</el-tag>
              </div>
            </template>
            <p class="result-text">{{ aiText }}</p>
            <div class="result-actions">
              <el-button size="small" @click="playVoice" :type="isPlaying ? 'danger' : ''">
                <el-icon><Microphone /></el-icon>
                {{ isPlaying ? '停止播报' : '语音播报' }}
              </el-button>
              <el-button
                v-if="markers.length"
                size="small" type="primary"
                @click="goToMap"
                style="margin-left:8px;"
              >
                <el-icon><Location /></el-icon>
                在地图中查看（{{ markers.length }}处）
              </el-button>
            </div>
          </el-card>

          <!-- 地标卡片 -->
          <div v-if="markers.length" class="markers-grid">
            <p class="markers-title">
              <el-icon><MapLocation /></el-icon>
              相关地标（{{ markers.length }} 处）——点击可在地图定位
            </p>
            <div class="marker-cards">
              <div
                v-for="m in markers" :key="m.id"
                class="marker-chip"
                @click="focusSingleMarker(m)"
              >
                <el-icon><Location /></el-icon>
                {{ m.base_name }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { analyzeSource, analyzeSourceVideo, fetchTtsPcm } from '@/api'
import { useMapStore } from '@/features/map/stores/mapStore'
import VoiceInputBar from '@/features/shared/components/VoiceInputBar.vue'
import HeritageLoadingPanel from '@/features/shared/components/HeritageLoadingPanel.vue'

const voiceHint = ref('')

const router   = useRouter()
const mapStore = useMapStore()

// ── 模式切换 ──────────────────────────
const mode = ref('image')   // 'image' | 'video'

function switchMode(m) {
  if (mode.value === m) return
  mode.value = m
  aiText.value         = ''
  markers.value        = []
  identifiedCity.value = ''
  voiceHint.value      = ''
}

// ── 图片状态 ──────────────────────────
const imageB64        = ref('')
const imagePreviewUrl = ref('')

function onImageChange(file) {
  // 换图后旧语音补充不再适用，避免误当作提示词带入下一次识别
  voiceHint.value = ''
  const reader = new FileReader()
  reader.onload = (e) => {
    imagePreviewUrl.value = e.target.result
    imageB64.value        = e.target.result
  }
  reader.readAsDataURL(file.raw)
}

// ── 视频状态 ──────────────────────────
const videoFile        = ref(null)
const videoPreviewUrl  = ref('')
const videoB64         = ref('')
const encoding         = ref(false)
const encodingProgress = ref(0)

const videoSizeLabel = computed(() => {
  if (!videoFile.value) return ''
  return (videoFile.value.size / 1024 / 1024).toFixed(1) + ' MB'
})

function onVideoChange(file) {
  const raw = file.raw
  if (!raw) return
  if (raw.size > 50 * 1024 * 1024) {
    ElMessage.warning('视频文件超过 50MB，请压缩后再上传')
    return
  }
  videoFile.value       = raw
  videoPreviewUrl.value = URL.createObjectURL(raw)
  videoB64.value        = ''
  encoding.value        = true
  encodingProgress.value = 0

  const reader = new FileReader()
  reader.onprogress = (e) => {
    if (e.lengthComputable) {
      encodingProgress.value = Math.round((e.loaded / e.total) * 100)
    }
  }
  reader.onload = (e) => {
    videoB64.value         = e.target.result   // data:video/mp4;base64,xxx
    encoding.value         = false
    encodingProgress.value = 100
  }
  reader.onerror = () => {
    encoding.value = false
    ElMessage.error('视频读取失败，请重试')
  }
  reader.readAsDataURL(raw)
}

// ── 公共结果状态 ──────────────────────
const aiText         = ref('')
const markers        = ref([])
const identifiedCity = ref('')
const loading        = ref(false)
const isPlaying      = ref(false)
let audioSource      = null

// ── 识别方法 ──────────────────────────
async function runImageSource() {
  loading.value = true
  aiText.value  = ''
  markers.value = []
  try {
    const res = await analyzeSource(imageB64.value, null, voiceHint.value)
    applyResult(res.data)
  } catch {
    ElMessage.error('图片识别失败，请重试')
  } finally {
    loading.value = false
  }
}

async function runVideoSource() {
  loading.value = true
  aiText.value  = ''
  markers.value = []
  try {
    const res = await analyzeSourceVideo(videoB64.value, null)
    applyResult(res.data)
  } catch (e) {
    const msg = e?.response?.data?.msg || '视频分析失败，请重试'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function applyResult(data) {
  aiText.value         = data.ai_text || ''
  markers.value        = data.markers || []
  identifiedCity.value = data.city    || ''
  if (markers.value.length) {
    mapStore.pushMarkersFromSource(markers.value, identifiedCity.value)
    ElMessage.success({
      message: `已识别到 ${identifiedCity.value}，可点击"在地图中查看"跳转至地图页面`,
      duration: 4000
    })
  }
}

// ── 地图跳转 ──────────────────────────
function goToMap() {
  mapStore.pushMarkersFromSource(markers.value, identifiedCity.value)
  router.push('/map')
}

function focusSingleMarker(m) {
  mapStore.pushMarkersFromSource([m], identifiedCity.value)
  router.push('/map')
}

// ── 语音播报 ──────────────────────────
async function playVoice() {
  if (!aiText.value) return
  if (audioSource) {
    try { audioSource.stop() } catch {}
    audioSource = null; isPlaying.value = false; return
  }
  isPlaying.value = true
  try {
    const pcmBuffer  = await fetchTtsPcm(aiText.value)
    const sampleRate = 16000
    const numSamples = pcmBuffer.byteLength / 2
    const ctx        = new (window.AudioContext || window.webkitAudioContext)({ sampleRate })
    const audioBuf   = ctx.createBuffer(1, numSamples, sampleRate)
    const channel    = audioBuf.getChannelData(0)
    const view       = new DataView(pcmBuffer)
    for (let i = 0; i < numSamples; i++) {
      channel[i] = view.getInt16(i * 2, true) / 32768.0
    }
    const source = ctx.createBufferSource()
    source.buffer = audioBuf
    source.connect(ctx.destination)
    source.onended = () => { isPlaying.value = false; audioSource = null; ctx.close() }
    source.start(0)
    audioSource = source
  } catch {
    isPlaying.value = false
    ElMessage.error('语音播放失败')
  }
}
</script>

<style scoped>
@import '@/assets/page-common.css';

.source-layout {
  display: flex; gap: 20px; flex: 1; overflow: hidden; min-height: 0;
}
.source-left { width: 320px; flex-shrink: 0; }
.upload-card { height: 100%; }
:deep(.el-card__body) { padding: 16px !important; }
.card-label { font-size: 12px; color: var(--color-text-muted); margin-bottom: 10px; letter-spacing: 1px; }

/* ── 模式 Tab ── */
.mode-tabs {
  display: flex; gap: 6px; margin-bottom: 14px;
  background: var(--color-bg-base); border-radius: var(--radius-md); padding: 4px;
}
.mode-tab {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 5px;
  padding: 7px 0; border-radius: calc(var(--radius-md) - 2px);
  font-size: 13px; color: var(--color-text-muted);
  cursor: pointer; transition: all 0.18s; user-select: none;
}
.mode-tab.active {
  background: var(--color-bg-card); color: var(--color-accent-teal);
  box-shadow: 0 1px 4px rgba(0,0,0,0.12); font-weight: 500;
}
.mode-tab:not(.active):hover { color: var(--color-text-secondary); }

/* ── 上传区 ── */
.uploader :deep(.el-upload-dragger) {
  background: var(--color-bg-base) !important;
  border-color: var(--color-border) !important;
  border-radius: var(--radius-md) !important;
  height: 200px; display: flex; align-items: center; justify-content: center;
}
.uploader :deep(.el-upload-dragger:hover) { border-color: var(--color-accent-teal) !important; }
.upload-placeholder { text-align: center; }
.upload-icon { font-size: 40px; color: var(--color-text-muted); margin-bottom: 10px; }
.upload-placeholder p { color: var(--color-text-secondary); font-size: 13px; }
.upload-placeholder em { color: var(--color-accent-teal); font-style: normal; }
.upload-hint { color: var(--color-text-muted); font-size: 11px; margin-top: 4px; }
.preview-img { width: 100%; height: 200px; object-fit: contain; border-radius: var(--radius-sm); }

/* ── 视频预览 ── */
.video-selected { width: 100%; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.preview-video { width: 100%; max-height: 150px; border-radius: var(--radius-sm); background: #000; object-fit: contain; }
.video-info {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  font-size: 12px; color: var(--color-text-secondary); padding: 0 4px;
}
.video-info span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── 编码进度 ── */
.encoding-bar { margin-top: 10px; }
.encoding-label { font-size: 11px; color: var(--color-text-muted); display: block; margin-bottom: 4px; }
.voice-hint-text { font-size: 12px; color: var(--color-accent-teal); margin-top: 8px; line-height: 1.5; }

/* ── 视频提示 ── */
.video-tip {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: var(--color-text-muted); margin-top: 8px; line-height: 1.5;
}

/* ── 结果区 ── */
.source-right { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
.loading-result-card {
  background: var(--color-bg-card) !important;
  border-color: var(--color-border) !important;
  flex: 1;
}
.loading-result-card :deep(.el-card__body) {
  padding: 16px !important;
}

.result-card { background: var(--color-bg-card) !important; border-color: var(--color-border) !important; }
:deep(.el-card__header) { padding: 12px 16px !important; border-bottom-color: var(--color-border) !important; }
.result-header { display: flex; align-items: center; gap: 8px; }
.rh-avatar { font-size: 16px; }
.rh-title { font-size: 13px; color: var(--color-text-secondary); }
.result-text { font-size: 13px; color: var(--color-text-secondary); line-height: 1.8; white-space: pre-wrap; }
.result-actions { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--color-border); display: flex; flex-wrap: wrap; gap: 8px; }

.markers-title { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--color-text-muted); margin-bottom: 10px; }
.marker-cards { display: flex; flex-wrap: wrap; gap: 8px; }
.marker-chip {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 20px;
  background: rgba(61,158,140,0.08); border: 1px solid rgba(61,158,140,0.2);
  font-size: 12px; color: var(--color-accent-teal);
  cursor: pointer; transition: all 0.15s;
}
.marker-chip:hover {
  background: rgba(61,158,140,0.2);
  border-color: var(--color-accent-teal);
  transform: translateY(-1px);
}
</style>
