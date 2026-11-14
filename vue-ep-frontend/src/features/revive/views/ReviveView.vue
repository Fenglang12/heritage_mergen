<template>
  <div class="page-wrapper">
    <div class="page-header">
      <el-icon class="ph-icon"><MagicStick /></el-icon>
      <div>
        <h2 class="ph-title">非遗数字焕新</h2>
        <p class="ph-sub">上传参考图并填写描述，生成数字非遗创作图</p>
      </div>
    </div>

    <div class="revive-layout">
      <!-- 左：输入区 -->
      <div class="revive-left">
        <!-- 图片上传 -->
        <el-card shadow="never" class="config-card">
          <p class="card-label">参考图片（可选）</p>
          <el-upload
            drag accept="image/*" :auto-upload="false"
            :show-file-list="false" :on-change="onFileChange"
            class="revive-uploader"
          >
            <div v-if="!previewUrl" class="upload-ph">
              <el-icon><Plus /></el-icon>
              <span>上传非遗参考图</span>
            </div>
            <img v-else :src="previewUrl" class="preview-img" />
          </el-upload>
        </el-card>

        <!-- 风格选择 -->
        <el-card shadow="never" class="config-card">
          <p class="card-label">快捷风格</p>
          <div class="style-grid">
            <div
              v-for="s in styleTags" :key="s.label"
              class="style-tag"
              :class="{ active: prompt === s.prompt }"
              @click="prompt = s.prompt"
            >
              <span>{{ s.label }}</span>
            </div>
          </div>
        </el-card>

        <!-- 创意描述 -->
        <el-card shadow="never" class="config-card">
          <p class="card-label">创意灵感描述</p>
          <el-input
            v-model="prompt" type="textarea"
            :rows="4" placeholder="描述您的创意方向，例如：将图片重构为赛博朋克风格，保留核心文化特征..."
          />
          <VoiceInputBar label="语音输入创意" hint="松开自动填入上方描述框" @text="onVoicePrompt" />
        </el-card>

        <el-button
          type="primary" size="large" :loading="generating"
          :disabled="!prompt" @click="runRevive"
          style="width:100%; height:44px;"
        >
          <el-icon v-if="!generating"><MagicStick /></el-icon>
          {{ generating ? btnText : '开始数字焕新' }}
        </el-button>
      </div>

      <!-- 右：结果区 -->
      <div class="revive-right">
        <!-- 等待态 -->
        <div v-if="generating" class="result-waiting">
          <div class="waiting-animation" :class="{ 'stage-glm': btnPhase <= 1, 'stage-cogview': btnPhase >= 2 }">
            <div class="orbit-ring ring-glm"></div>
            <div class="orbit-ring ring-2 ring-cogview"></div>
            <div class="orbit-core">{{ btnPhase >= 2 ? '绘' : '析' }}</div>
          </div>
          <p class="waiting-text">{{ progressText || btnText }}</p>
          <ul v-if="progressLog.length" class="progress-log">
            <li v-for="(line, i) in progressLog" :key="i">{{ line }}</li>
          </ul>
          <p class="waiting-sub">{{ waitingSub }}</p>
        </div>

        <!-- 空态 -->
        <el-empty v-else-if="!resultUrl" description="焕新作品将在此处呈现" :image-size="80">
          <template #image><el-icon style="font-size:64px; color:var(--color-text-muted)"><Picture /></el-icon></template>
        </el-empty>

        <!-- 作品展示 -->
        <div v-else class="artwork-display">
          <div class="artwork-frame">
            <img :src="resultUrl" class="artwork-img" crossorigin="anonymous" @error="onArtworkImgError" />
            <div class="artwork-overlay">
              <p class="artwork-tag">时空匠影 · 数字焕新</p>
              <p class="artwork-prompt">{{ lastPromptShort }}</p>
            </div>
          </div>
          <div class="artwork-actions">
            <el-button type="primary" @click="downloadArt">
              <el-icon><Download /></el-icon>下载作品
            </el-button>
            <el-button @click="resultUrl = ''">
              <el-icon><RefreshRight /></el-icon>重新生成
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { generateArtStream } from '@/api'
import { readChatStream } from '@/features/chat/utils/chatStream'
import VoiceInputBar from '@/features/shared/components/VoiceInputBar.vue'

const previewUrl = ref('')
const imageB64   = ref(null)
const prompt     = ref('')

function onVoicePrompt(text) {
  prompt.value = text
}
const resultUrl  = ref('')
const lastPrompt = ref('')
const generating = ref(false)
const btnPhase   = ref(0)
const progressText = ref('')
const progressLog  = ref([])

const phasesWithRef = ['已收到参考图…', '按参考图与文字融合创作…', '图生图绘制中…', '即将完成…']
const phasesTextOnly = ['理解文字创意…', '构思画面构图…', '文生图绘制中…', '即将完成…']
const btnText = computed(() => {
  const phases = imageB64.value ? phasesWithRef : phasesTextOnly
  return phases[btnPhase.value % phases.length]
})
const waitingSub = computed(() =>
  imageB64.value
    ? '图生图模式：参考图 + 文字描述 → Qwen-Image 绘制，请稍候…'
    : '文生图模式：仅按文字描述 → Qwen-Image 绘制，请稍候…'
)
const lastPromptShort = computed(() => lastPrompt.value.slice(0, 40) + (lastPrompt.value.length > 40 ? '...' : ''))

let phaseTimer = null

const styleTags = [
  { label: '赛博朋克', prompt: '将此非遗元素重构为赛博朋克风格，保留其核心文化特征，融入霓虹灯效、全息投影与未来科技感机械零件，背景为雨夜的赛博都市，电影级光影，8K超高清。' },
  { label: '3D潮玩', prompt: '将此非遗元素重构为泡泡玛特(Popmart)风格的3D潮玩盲盒手办。角色Q版精致可爱，采用光滑的树脂材质，边缘圆润，明亮温暖的工作室打光，C4D建模质感。' },
  { label: '国潮插画', prompt: '将此非遗元素转化为高质量的国风潮流手绘插画，使用中国传统色彩（朱砂红、石青、石绿），线条流畅且具有张力，结合现代平面设计排版感。' },
  { label: '敦煌壁画', prompt: '将此非遗元素转化为敦煌壁画风格，使用古老的矿物颜料色彩（土黄、朱砂、石青），带有岁月斑驳的肌理感，融入飞天、祥云等传统意象，神秘庄严。' },
]

function onFileChange(file) {
  const reader = new FileReader()
  reader.onload = (e) => { previewUrl.value = e.target.result; imageB64.value = e.target.result }
  reader.readAsDataURL(file.raw)
}

async function runRevive() {
  if (!prompt.value) return
  generating.value = true
  resultUrl.value = ''
  lastPrompt.value = prompt.value
  btnPhase.value = 0
  progressText.value = ''
  progressLog.value = []
  phaseTimer = setInterval(() => { btnPhase.value++ }, 4000)

  try {
    const res = await generateArtStream(prompt.value, imageB64.value)
    if (!res.ok) throw new Error('请求失败')
    for await (const event of readChatStream(res)) {
      if (event.type === 'progress') {
        const line = event.text || ''
        progressText.value = line
        if (line && progressLog.value[progressLog.value.length - 1] !== line) {
          progressLog.value.push(line)
        }
        if (event.stage === 'glm_start') btnPhase.value = 0
        else if (event.stage === 'cogview_start') btnPhase.value = 2
        else if (event.stage === 'done') btnPhase.value = 3
      }
      if (event.type === 'done' && event.url) {
        resultUrl.value = event.url
      }
      if (event.type === 'error') {
        ElMessage.error(event.msg || '生成失败')
        throw new Error(event.msg || 'error')
      }
    }
    if (!resultUrl.value) ElMessage.warning('未收到作品，请重试')
  } catch {
    if (generating.value) ElMessage.error('请求失败，请重试')
  } finally {
    generating.value = false
    clearInterval(phaseTimer)
    progressText.value = ''
  }
}

function onArtworkImgError() {
  ElMessage.warning('图片加载失败，请重新生成或稍后重试')
}

/** 使用 Blob 下载，避免外链 <a href> 导致整页跳转 404 */
async function downloadArt() {
  const url = resultUrl.value
  if (!url) return

  try {
    let blob
    if (url.startsWith('data:')) {
      const res = await fetch(url)
      blob = await res.blob()
    } else {
      const res = await fetch(url, { mode: 'cors' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      blob = await res.blob()
    }

    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = `非遗焕新_${Date.now()}.jpg`
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(objectUrl)
    ElMessage.success('下载已开始')
  } catch {
    try {
      const imgEl = document.querySelector('.artwork-img')
      if (!imgEl?.naturalWidth) throw new Error('no img')
      const canvas = document.createElement('canvas')
      canvas.width = imgEl.naturalWidth
      canvas.height = imgEl.naturalHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(imgEl, 0, 0)
      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob((b) => (b ? resolve(b) : reject()), 'image/jpeg', 0.92)
      })
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = `非遗焕新_${Date.now()}.jpg`
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(objectUrl)
      ElMessage.success('下载已开始')
    } catch {
      ElMessage.error('下载失败，请右键图片另存为')
    }
  }
}
</script>

<style scoped>
@import '@/assets/page-common.css';

.revive-layout { display: flex; gap: 20px; flex: 1; overflow: hidden; }

.revive-left {
  width: 300px; flex-shrink: 0;
  display: flex; flex-direction: column; gap: 12px;
  overflow-y: auto;
}

.config-card { background: var(--color-bg-panel) !important; border-color: var(--color-border) !important; }
:deep(.el-card__body) { padding: 14px !important; }
.card-label { font-size: 11px; color: var(--color-text-muted); margin-bottom: 8px; letter-spacing: 0.2px; }

.revive-uploader :deep(.el-upload-dragger) {
  background: var(--color-bg-base) !important;
  border-color: var(--color-border) !important;
  height: 120px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-md) !important;
}
.upload-ph { display: flex; flex-direction: column; align-items: center; gap: 6px; color: var(--color-text-muted); font-size: 12px; }
.upload-ph .el-icon { font-size: 24px; }
.preview-img { width: 100%; height: 120px; object-fit: cover; border-radius: var(--radius-sm); }

.style-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.style-tag {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px; border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  font-size: 12px; color: var(--color-text-secondary);
  cursor: pointer; transition: color 0.2s, background-color 0.2s, border-color 0.2s;
}
.style-tag:hover { border-color: var(--color-accent-teal); color: var(--color-accent-teal); background: rgba(61,158,140,0.06); }
.style-tag.active { border-color: var(--color-accent-teal); background: rgba(61,158,140,0.12); color: var(--color-accent-teal); }
.style-emoji { font-size: 16px; }

.revive-right {
  flex: 1; display: flex; align-items: center; justify-content: center;
  background: var(--color-bg-panel); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); overflow: hidden;
}

/* 等待动画 */
.result-waiting { text-align: center; }
.waiting-animation { position: relative; width: 100px; height: 100px; margin: 0 auto 20px; }
.orbit-ring {
  position: absolute; inset: 0; border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: var(--color-accent-teal);
  animation: spin 1.5s linear infinite;
}
.ring-2 { inset: 12px; border-top-color: var(--color-accent-gold); animation-duration: 2.5s; animation-direction: reverse; }
.stage-glm .ring-glm { border-top-color: var(--color-accent-teal);  }
.stage-cogview .ring-cogview { border-top-color: var(--color-accent-gold);  }
.orbit-core { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 32px; }
@keyframes spin { to { transform: rotate(360deg); } }
.waiting-text { color: var(--color-accent-teal); font-size: 14px; margin-bottom: 6px; }
.progress-log {
  list-style: none; padding: 0; margin: 12px auto 0; max-width: 320px; text-align: left;
  font-size: 12px; color: var(--color-text-secondary); line-height: 1.8;
}
.progress-log li::before { content: '▸ '; color: var(--color-accent-gold); }
.waiting-sub { color: var(--color-text-muted); font-size: 12px; margin-top: 10px; }

/* 作品展示 */
.artwork-display { width: 100%; height: 100%; display: flex; flex-direction: column; }
.artwork-frame { flex: 1; position: relative; overflow: hidden; }
.artwork-img { width: 100%; height: 100%; object-fit: contain; display: block; }
.artwork-overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: linear-gradient(transparent, rgba(0,0,0,0.75));
  padding: 20px 20px 16px;
}
.artwork-tag { color: var(--color-accent-gold); font-family: var(--font-serif); font-size: 13px; margin-bottom: 4px; }
.artwork-prompt { color: rgba(255,255,255,0.6); font-size: 12px; }
.artwork-actions { padding: 14px 20px; display: flex; gap: 10px; border-top: 1px solid var(--color-border); background: var(--color-bg-panel); }
</style>
