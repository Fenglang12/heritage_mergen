<template>
  <div class="page-chat">

    <!-- 会话列表侧栏 -->
    <div class="session-rail">
      <div class="rail-header">
        <span class="rail-title">对话记录</span>
        <el-button size="small" circle class="dark-tool-btn" @click="createNewSession" :loading="creatingSession">
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessions" :key="s.id"
          class="session-item"
          :class="{ active: s.id === currentSessionId }"
          @click="switchSession(s.id)"
        >
          <el-icon class="si-icon"><ChatDotRound /></el-icon>
          <div class="si-info" @dblclick.stop="startEditTitle(s)">
            <el-input
              v-if="editingSessionId === s.id"
              v-model="editingTitle"
              size="small"
              class="si-title-input"
              maxlength="100"
              @click.stop
              @keyup.enter="saveSessionTitle(s.id)"
              @blur="saveSessionTitle(s.id)"
            />
            <p v-else class="si-title" :title="s.title">{{ s.title }}</p>
            <p class="si-time">{{ s.time }}</p>
          </div>
          <el-icon class="si-edit" title="重命名" @click.stop="startEditTitle(s)"><Edit /></el-icon>
          <el-popconfirm title="确定删除此会话？" @confirm="deleteSession(s.id)" width="180">
            <template #reference>
              <el-icon class="si-del" @click.stop><Delete /></el-icon>
            </template>
          </el-popconfirm>
        </div>
        <el-empty v-if="!sessions.length" description="暂无对话" :image-size="40" style="margin-top:30px;" />
      </div>
    </div>

    <!-- 聊天主区 -->
    <div class="chat-main">

      <!-- 本会话研学目标（会话记忆） -->
      <div v-if="sessionMemory?.goal" class="session-goal-bar">
        <span class="goal-dot" aria-hidden="true"></span>
        <span class="goal-text">{{ sessionMemory.goal }}</span>
        <span v-if="sessionMemory.stops?.length" class="goal-stops">
          · {{ sessionMemory.stops.slice(0, 3).join(' → ') }}
        </span>
      </div>

      <!-- 消息列表 -->
      <div class="messages-area" ref="messagesRef" @click="onMessagesClick">
        <!-- 欢迎语 -->
        <div v-if="!messages.length && !currentSessionId" class="welcome-screen">
          <div class="welcome-icon" aria-hidden="true">遗</div>
          <h3>非遗智能向导</h3>
          <p>可问非遗百科、地标与图谱，支持文字和语音。</p>
          <p style="margin-top:8px;">请先在左侧 <strong style="color:var(--color-accent-teal)">新建对话</strong>。</p>
        </div>

        <template v-for="(msg, idx) in messages" :key="idx">
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="message user-msg">
            <div class="msg-bubble user-bubble">
              <img v-if="msg.imageUrl" :src="msg.imageUrl" class="msg-user-img" alt="参考图" />
              <span>{{ msg.content }}</span>
            </div>
            <div class="msg-avatar user-avatar-icon">
              {{ authStore.username?.charAt(0)?.toUpperCase() }}
            </div>
          </div>

          <!-- AI 消息 -->
          <div v-else class="message ai-msg">
            <div class="msg-avatar ai-avatar-icon" aria-hidden="true">遗</div>
            <div class="msg-content">
              <div class="msg-bubble ai-bubble">
                <!-- AI 正文经 renderAgentMessageHtml：Markdown → HTML 后 v-html 注入 -->
                <div class="md-body" v-html="renderAgentMessageHtml(msg.content)"></div>
                <img v-if="msg.imageUrl" :src="msg.imageUrl" class="msg-art-img" alt="焕新作品" />
              </div>
              <div class="msg-actions" v-if="idx === messages.length - 1 && !streamingText">
                <el-button size="small" text @click="playVoice(msg.content, idx)">
                  <el-icon><Microphone /></el-icon>
                  {{ activeVoiceIdx === idx ? '停止' : '朗读' }}
                </el-button>
              </div>
            </div>
          </div>
        </template>

        <!-- Agent 工具执行步骤 -->
        <div v-if="agentSteps.length" class="agent-steps">
          <div v-for="(step, i) in agentSteps" :key="i" class="agent-step" :class="{ done: step.done }">
            <span class="step-icon">{{ step.done ? '完成' : '…' }}</span>
            <span>{{ step.label }}</span>
          </div>
        </div>

        <!-- 流式输出气泡 -->
        <div v-if="streamingText !== null" class="message ai-msg">
          <div class="msg-avatar ai-avatar-icon" aria-hidden="true">遗</div>
          <div class="msg-bubble ai-bubble streaming-bubble">
            <div class="md-body" v-html="renderAgentMessageHtml(streamingText)"></div>
            <img v-if="streamArtUrl" :src="streamArtUrl" class="msg-art-img" alt="焕新作品" />
            <span class="typing-cursor" v-if="!streamingText"></span>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-row">
          <el-input
            v-model="inputText"
            placeholder="输入您的问题，或长按录音键说话..."
            size="large" clearable
            @keyup.enter="sendText"
            class="chat-input"
          />
          <el-button
            type="primary" size="large" :loading="sending"
            :disabled="(!inputText.trim() && !pendingImageB64) || !currentSessionId"
            @click="sendText"
            style="flex-shrink:0;"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
        <div class="toolbar-row">
          <el-button
            size="small"
            :type="isRecording ? 'danger' : ''"
            @mousedown="startRecording" @mouseup="stopRecording"
            @touchstart.prevent="startRecording" @touchend.prevent="stopRecording"
            class="record-btn dark-tool-btn"
          >
            <el-icon><Microphone /></el-icon>
            {{ isRecording ? '松开结束录音' : '按住说话' }}
          </el-button>
          <input ref="imageInputRef" type="file" accept="image/*" class="hidden-file" @change="onImagePicked" />
          <el-button size="small" class="dark-tool-btn" @click="imageInputRef?.click()">
            <el-icon><Picture /></el-icon>
            {{ pendingImageB64 ? '已选图' : '图片' }}
          </el-button>
          <el-button v-if="pendingImageB64" size="small" text @click="clearPendingImage">清除图片</el-button>
          <el-tooltip content="清空当前会话消息" placement="top">
            <el-button size="small" text @click="clearCurrentSession">
              <el-icon><Delete /></el-icon>清空记忆
            </el-button>
          </el-tooltip>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Picture, Edit } from '@element-plus/icons-vue'
import { useAuthStore } from '@/features/auth/auth'
import {
  getSessions, createSession, updateSessionTitle,
  getSessionHistory, clearSession,
  streamChat, streamChatAudio, streamChatImage, fetchTtsPcm,
} from '@/api'
import { readChatStream, toolStepLabel } from '@/features/chat/utils/chatStream'
import { renderAgentMessageHtml } from '@/features/chat/utils/suggestLinks'
import { useMapStore } from '@/features/map/stores/mapStore'
import { getBrowserPreciseLocation } from '@/features/map/utils/browserGps'

const authStore = useAuthStore()
const router = useRouter()
const mapStore = useMapStore()

/** 对话附带浏览器 GPS（优先用地图页缓存，避免每次弹权限） */
async function resolveChatGeo() {
  const cached = mapStore.lastGps
  if (cached?.lng != null && cached?.lat != null && Date.now() - (cached.ts || 0) < 10 * 60 * 1000) {
    return {
      lng: cached.lng,
      lat: cached.lat,
      city: cached.city || undefined,
      citycode: cached.citycode || undefined,
    }
  }
  try {
    const { coords } = await getBrowserPreciseLocation({
      timeoutMs: 6000,
      maximumAge: 120000,
    })
    if (coords?.lng != null && coords?.lat != null) {
      mapStore.setLastGps(coords)
      return { lng: coords.lng, lat: coords.lat }
    }
  } catch {
    /* 无定位时 Agent 仍可按城市检索 */
  }
  return null
}

/** 最近一次 Agent 地图搜索（跳转 /map 时 query 兜底） */
const lastAgentMapHint = ref({ city: '', keyword: '' })

const sessions         = ref([])
const editingSessionId = ref(null)
const editingTitle     = ref('')
const currentSessionId = ref(null)
const messages         = ref([])
const sessionMemory    = ref(null)  // { goal, theme, city, stops }
const inputText        = ref('')
const sending          = ref(false)
const streamingText    = ref(null)
const agentSteps       = ref([])
const messagesRef      = ref(null)
const creatingSession  = ref(false)
const imageInputRef    = ref(null)
const pendingImageB64  = ref(null)
const streamArtUrl     = ref(null)

// 语音
const activeVoiceIdx = ref(-1)
let currentAudioSource = null  // AudioBufferSourceNode for TTS
let currentAudioCtx    = null  // AudioContext for TTS

// 录音
const isRecording = ref(false)
let audioContext = null, audioStream = null, processor = null, audioChunks = []

// ── Init ──────────────────────────────────────────────────
onMounted(() => loadSessions())

async function loadSessions() {
  try {
    const res = await getSessions()
    sessions.value = res.data.sessions || []
  } catch { /* silent */ }
}

async function createNewSession() {
  creatingSession.value = true
  try {
    const res = await createSession()
    sessionMemory.value = null
    await loadSessions()
    await switchSession(res.data.session_id)
  } catch { ElMessage.error('创建会话失败') }
  finally { creatingSession.value = false }
}

async function switchSession(sid) {
  currentSessionId.value = sid
  messages.value = []
  sessionMemory.value = null
  try {
    const res = await getSessionHistory(sid)
    messages.value = res.data.data || []
    sessionMemory.value = res.data.memory || null
    await scrollBottom()
  } catch { /* silent */ }
}

async function deleteSession(sid) {
  await clearSession(sid)
  if (currentSessionId.value === sid) {
    currentSessionId.value = null
    messages.value = []
  }
  if (editingSessionId.value === sid) editingSessionId.value = null
  await loadSessions()
}

function startEditTitle(s) {
  editingSessionId.value = s.id
  editingTitle.value = s.title || ''
}

async function saveSessionTitle(sid) {
  if (editingSessionId.value !== sid) return
  const title = editingTitle.value.trim()
  editingSessionId.value = null
  if (!title) {
    ElMessage.warning('标题不能为空')
    await loadSessions()
    return
  }
  const prev = sessions.value.find((x) => x.id === sid)
  if (prev && prev.title === title) return
  try {
    await updateSessionTitle(sid, title)
    await loadSessions()
  } catch {
    ElMessage.error('重命名失败')
    await loadSessions()
  }
}

async function clearCurrentSession() {
  if (!currentSessionId.value) return
  await clearSession(currentSessionId.value)
  messages.value = []
  await loadSessions()
  // 创建新会话代替
  await createNewSession()
}

// ── Chat ──────────────────────────────────────────────────
async function sendText() {
  const text = inputText.value.trim() || (pendingImageB64.value ? '请根据这张图片进行非遗焕新或解读' : '')
  if (!text || !currentSessionId.value) return
  inputText.value = ''
  await send(text)
}

function resetStreamState() {
  agentSteps.value = []
  streamingText.value = ''
  streamArtUrl.value = null
}

function clearPendingImage() {
  pendingImageB64.value = null
  if (imageInputRef.value) imageInputRef.value.value = ''
}

function onImagePicked(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片请小于 5MB')
    return
  }
  const reader = new FileReader()
  reader.onload = () => { pendingImageB64.value = reader.result }
  reader.readAsDataURL(file)
}

function syncAgentMarkersToMapStore(event) {
  const data = event?.data
  if (!data || typeof data !== 'object' || !Array.isArray(data.markers) || !data.markers.length) {
    return
  }
  const tool = event.tool
  if (tool === 'search_places' || tool === 'plan_study_tour') {
    const city = data.city || ''
    const keyword = data.keyword || data.theme || ''
    mapStore.pushMarkersFromAgent(data.markers, city, keyword)
    lastAgentMapHint.value = { city, keyword }
    return
  }
  if (tool === 'identify_image') {
    const city = data.city || ''
    mapStore.pushMarkersFromAgent(data.markers, city, '')
    lastAgentMapHint.value = { city, keyword: '' }
  }
}

function handleAgentEvent(event, ctx) {
  const { placeholderMsg } = ctx

  if (event.type === 'asr' && placeholderMsg) {
    placeholderMsg.content = event.text || '（语音内容）'
    messages.value = [...messages.value]
    return
  }
  if (event.type === 'error') {
    if (placeholderMsg) {
      placeholderMsg.content = '⚠️ ' + (event.text || '请求失败')
      messages.value = [...messages.value]
    }
    ctx.failed = true
    return
  }
  if (event.type === 'trajectory') {
    // 后端轨迹日志事件：不打断步骤条（答辩可说明有 trajectory 可观测）
    return
  }
  if (event.type === 'session_memory') {
    sessionMemory.value = event.memory || null
    return
  }
  if (event.type === 'thinking') {
    agentSteps.value = [{ label: event.text || '正在分析…', done: false }]
    return
  }
  if (event.type === 'tool_call') {
    const label = toolStepLabel(event) || event.label || event.tool
    agentSteps.value.push({ label, done: false })
    return
  }
  if (event.type === 'tool_result') {
    const steps = agentSteps.value
    if (steps.length) steps[steps.length - 1].done = true
    syncAgentMarkersToMapStore(event)
    return
  }
  if (event.type === 'revive_progress') {
    const label = event.text || toolStepLabel(event) || '焕新进行中…'
    const steps = agentSteps.value
    const last = steps[steps.length - 1]
    if (last && !last.done && last.revive) {
      last.label = label
    } else {
      agentSteps.value.push({ label, done: false, revive: true })
    }
    return
  }
  if (event.type === 'art_image') {
    ctx.artUrl = event.url
    streamArtUrl.value = event.url
    return
  }
  if (event.type === 'text') {
    ctx.accumulated += event.text || ''
    streamingText.value = ctx.accumulated
  }
}

async function consumeChatStream(res, ctx = {}) {
  if (!res.ok) throw new Error('请求失败')
  for await (const event of readChatStream(res)) {
    handleAgentEvent(event, ctx)
    await scrollBottom()
    if (ctx.failed) break
  }
}

async function send(text) {
  const img = pendingImageB64.value
  messages.value.push({
    role: 'user',
    content: text,
    imageUrl: img || undefined,
  })
  pendingImageB64.value = null
  if (imageInputRef.value) imageInputRef.value.value = ''
  await scrollBottom()
  sending.value = true
  resetStreamState()

  const ctx = { accumulated: '', failed: false, artUrl: null }
  try {
    const geo = await resolveChatGeo()
    const res = img
      ? await streamChatImage(img, currentSessionId.value, text, geo)
      : await streamChat(text, currentSessionId.value, geo)
    await consumeChatStream(res, ctx)
    if (!ctx.failed && ctx.accumulated) {
      messages.value.push({
        role: 'assistant',
        content: ctx.accumulated,
        imageUrl: ctx.artUrl || undefined,
      })
    } else if (!ctx.failed && !ctx.accumulated) {
      messages.value.push({ role: 'assistant', content: '暂无回复，请重试。' })
    }
  } catch {
    messages.value.push({ role: 'assistant', content: '连接中断，请重试。' })
  } finally {
    streamingText.value = null
    streamArtUrl.value = null
    agentSteps.value = []
    sending.value = false
    await scrollBottom()
    await loadSessions()
  }
}

async function sendAudio(audioB64) {
  const placeholderMsg = { role: 'user', content: '识别中…', _isAudio: true }
  messages.value.push(placeholderMsg)
  await scrollBottom()
  sending.value = true
  resetStreamState()

  const ctx = { accumulated: '', failed: false, placeholderMsg }
  try {
    const geo = await resolveChatGeo()
    const res = await streamChatAudio(audioB64, currentSessionId.value, geo)
    await consumeChatStream(res, ctx)
    if (!ctx.failed && ctx.accumulated) {
      messages.value.push({ role: 'assistant', content: ctx.accumulated })
    }
  } catch (e) {
    console.error('sendAudio error:', e)
    placeholderMsg.content = '⚠️ 语音请求失败，请重试'
    messages.value = [...messages.value]
  } finally {
    streamingText.value = null
    agentSteps.value = []
    sending.value = false
    await scrollBottom()
    await loadSessions()
  }
}

async function scrollBottom() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTo({ top: messagesRef.value.scrollHeight, behavior: 'smooth' })
  }
}

// ── TTS ───────────────────────────────────────────────────
function stripForTts(raw) {
  return (raw || '')
    // 1. 换行 → 停顿逗号
    .replace(/\n+/g, '，')
    // 2. Markdown 标题符号
    .replace(/#{1,6}\s*/g, '')
    // 3. 粗体 / 斜体：**text** / *text* / __text__ / _text_
    .replace(/\*{1,3}([^*]+)\*{1,3}/g, '$1')
    .replace(/_{1,2}([^_]+)_{1,2}/g, '$1')
    // 4. 行内代码 / 代码块
    .replace(/```[\s\S]*?```/g, '（代码段）')
    .replace(/`([^`]*)`/g, '$1')
    // 5. 链接 [text](url) → text
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    // 6. 图片 ![alt](url) → alt
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    // 7. 引用块 > 
    .replace(/^>\s*/gm, '')
    // 8. 水平线
    .replace(/^[-*_]{3,}$/gm, '')
    // 9. 列表符号 - / * / 数字.
    .replace(/^[\s]*[-*+]\s+/gm, '')
    .replace(/^[\s]*\d+\.\s+/gm, '')
    // 10. HTML 标签
    .replace(/<br\s*\/?>/gi, '，')
    .replace(/<[^>]+>/g, '')
    // 11. 多余标点/空白
    .replace(/[，]{2,}/g, '，')
    .replace(/\s+/g, ' ')
    .trim()
}

async function playVoice(text, idx) {
  // 停止当前播放
  if (currentAudioSource) {
    try { currentAudioSource.stop() } catch {}
    currentAudioSource = null
  }
  if (activeVoiceIdx.value === idx) {
    activeVoiceIdx.value = -1
    return
  }

  const cleanText = stripForTts(text)
  if (!cleanText) return
  activeVoiceIdx.value = idx

  try {
    // 获取 PCM 数据
    const pcmBuffer = await fetchTtsPcm(cleanText)

    // 用 AudioContext 解码 16k 16bit 单声道 PCM
    const sampleRate   = 16000
    const numSamples   = pcmBuffer.byteLength / 2          // 16bit = 2 bytes/sample
    const audioCtx     = new (window.AudioContext || window.webkitAudioContext)({ sampleRate })
    const audioBuffer  = audioCtx.createBuffer(1, numSamples, sampleRate)
    const channelData  = audioBuffer.getChannelData(0)
    const view         = new DataView(pcmBuffer)

    // 将 Int16 PCM 转为 Float32（AudioContext 需要 -1.0 ~ 1.0）
    for (let i = 0; i < numSamples; i++) {
      channelData[i] = view.getInt16(i * 2, true) / 32768.0
    }

    const source = audioCtx.createBufferSource()
    source.buffer = audioBuffer
    source.connect(audioCtx.destination)
    source.onended = () => {
      activeVoiceIdx.value = -1
      currentAudioSource = null
      audioCtx.close()
    }
    source.start(0)
    currentAudioSource = source
    currentAudioCtx    = audioCtx
  } catch (e) {
    console.warn('TTS 播放失败:', e)
    activeVoiceIdx.value = -1
  }
}

// ── ASR ───────────────────────────────────────────────────
async function startRecording() {
  if (isRecording.value) return
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const AC = window.AudioContext || window.webkitAudioContext
    audioContext = new AC({ sampleRate: 16000 })
    const src = audioContext.createMediaStreamSource(audioStream)
    processor  = audioContext.createScriptProcessor(4096, 1, 1)
    audioChunks = []
    processor.onaudioprocess = (e) => {
      if (isRecording.value) audioChunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
    }
    src.connect(processor); processor.connect(audioContext.destination)
    isRecording.value = true
  } catch { ElMessage.warning('请允许麦克风权限') }
}

function stopRecording() {
  if (!isRecording.value) return
  isRecording.value = false
  if (processor) processor.disconnect()
  if (audioStream) audioStream.getTracks().forEach(t => t.stop())
  const wav = encodeWAV(audioChunks, audioContext.sampleRate)
  const reader = new FileReader()
  reader.readAsDataURL(wav)
  reader.onloadend = () => {
    if (currentSessionId.value) sendAudio(reader.result)
    else ElMessage.warning('请先选择或新建对话')
  }
}

function encodeWAV(chunks, rate) {
  let len = 0; chunks.forEach(c => len += c.length)
  const flat = new Float32Array(len); let off = 0
  chunks.forEach(c => { flat.set(c, off); off += c.length })
  const buf = new ArrayBuffer(44 + flat.length * 2)
  const v = new DataView(buf)
  const ws = (o, s) => { for (let i=0;i<s.length;i++) v.setUint8(o+i, s.charCodeAt(i)) }
  ws(0,'RIFF'); v.setUint32(4,36+flat.length*2,true); ws(8,'WAVE')
  ws(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true)
  v.setUint32(24,rate,true); v.setUint32(28,rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true)
  ws(36,'data'); v.setUint32(40,flat.length*2,true)
  let p=44; flat.forEach(s=>{ s=Math.max(-1,Math.min(1,s)); v.setInt16(p,s<0?s*0x8000:s*0x7FFF,true); p+=2 })
  return new Blob([v], { type: 'audio/wav' })
}

function onMessagesClick(e) {
  const a = e.target.closest?.('.agent-suggest-link')
  if (!a) return
  e.preventDefault()
  const path = a.getAttribute('data-path')
  if (!path) return

  if (path === '/map') {
    if (!mapStore.hasPendingUpdate) {
      mapStore.rearmAgentPending()
    }
    const { city, keyword } = lastAgentMapHint.value
    const query = {}
    if (city) query.city = city
    if (keyword) query.keyword = keyword
    router.push({ path: '/map', query: Object.keys(query).length ? query : undefined })
    return
  }
  router.push(path)
}
</script>

<style scoped>
.page-chat {
  display: flex; height: 100%;
  background: var(--color-bg-base);
  overflow: hidden;
}

/* 会话栏 */
.session-rail {
  width: 220px; flex-shrink: 0;
  background: var(--color-bg-panel);
  border-right: 1px solid var(--color-border);
  display: flex; flex-direction: column;
}
.rail-header {
  padding: 14px 14px 10px;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.rail-title { font-size: 13px; color: var(--color-text-secondary); font-weight: 600; }

.session-list { flex: 1; overflow-y: auto; padding: 6px; }
.session-item {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 10px; border-radius: var(--radius-sm);
  cursor: pointer; transition: color 0.15s, background-color 0.15s;
  position: relative;
}
.session-item:hover { background: var(--color-bg-hover); }
.session-item.active { background: rgba(61,158,140,0.1); }
.session-item:hover .si-del,
.session-item:hover .si-edit { opacity: 1; }
.si-icon { color: var(--color-text-muted); font-size: 14px; flex-shrink: 0; }
.si-info { flex: 1; min-width: 0; }
.si-title { font-size: 12px; color: var(--color-text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.si-time { font-size: 10px; color: var(--color-text-muted); margin-top: 1px; }
.si-title-input { width: 100%; }
.si-title-input :deep(.el-input__inner) {
  font-size: 12px; height: 24px; padding: 0 6px;
}
.si-edit { color: var(--color-text-muted); font-size: 13px; opacity: 0; transition: opacity 0.15s; flex-shrink: 0; }
.si-edit:hover { color: var(--color-accent-teal); }
.si-del { color: var(--color-text-muted); font-size: 13px; opacity: 0; transition: opacity 0.15s; flex-shrink: 0; }
.si-del:hover { color: #c0392b; }
.session-item.active .si-icon { color: var(--color-accent-teal); }
.session-item.active .si-title { color: var(--color-text-primary); }

/* 聊天主区 */
.chat-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.session-goal-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--color-border);
  background: rgba(61, 158, 140, 0.08);
  font-size: 12px;
  color: var(--color-text-secondary);
}
.goal-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--color-accent-teal);
  flex-shrink: 0;
}
.goal-text { color: var(--color-accent-teal); font-weight: 600; }
.goal-stops {
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.messages-area {
  flex: 1; overflow-y: auto; padding: 20px;
  display: flex; flex-direction: column; gap: 16px;
}

.welcome-screen {
  margin: auto; text-align: center; max-width: 360px;
}
.welcome-icon { font-family: var(--font-serif); font-size: 28px; margin-bottom: 16px; color: var(--color-accent-gold); }
.welcome-screen h3 { font-family: var(--font-serif); font-size: 18px; color: var(--color-text-primary); margin-bottom: 10px; }
.welcome-screen p { font-size: 13px; color: var(--color-text-muted); line-height: 1.7; }

.message { display: flex; align-items: flex-end; gap: 10px; max-width: 80%; }
.user-msg { margin-left: auto; flex-direction: row-reverse; }
.ai-msg { margin-right: auto; }

.msg-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; flex-shrink: 0;
}
.ai-avatar-icon { background: rgba(61,158,140,0.15); font-family: var(--font-serif); font-size: 15px; color: var(--color-accent-teal); }
.user-avatar-icon {
  background: linear-gradient(135deg, var(--color-accent-gold), #a88030);
  color: #fff; font-family: var(--font-serif); font-size: 14px; font-weight: 600;
}

.msg-content { display: flex; flex-direction: column; gap: 4px; }

.msg-bubble {
  padding: 10px 14px; border-radius: 14px;
  font-size: 13px; line-height: 1.75;
  max-width: 100%;
}
.ai-bubble {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  border-bottom-left-radius: 4px;
}
.user-bubble {
  background: linear-gradient(135deg, var(--color-accent-teal), #2e8070);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.streaming-bubble { border-color: rgba(61,158,140,0.3); }

.agent-steps {
  align-self: flex-start;
  max-width: 85%;
  padding: 10px 14px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--color-text-muted);
}
.agent-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
}
.agent-step.done { color: var(--color-accent-teal); }
.step-icon { font-size: 11px; width: 14px; text-align: center; }

.msg-actions { padding-left: 4px; }

/* 输入区 */
.input-area {
  padding: 14px 16px;
  background: var(--color-bg-panel);
  border-top: 1px solid var(--color-border);
  flex-shrink: 0;
}
.input-row { display: flex; gap: 8px; margin-bottom: 10px; }
.chat-input { flex: 1; }

.toolbar-row { display: flex; align-items: center; gap: 10px; }
.record-btn { letter-spacing: 1px; }
.dark-tool-btn:not(.el-button--danger) {
  --el-button-bg-color: #22262f;
  --el-button-border-color: #3a4258;
  --el-button-text-color: #a8b0c4;
  background: #22262f !important;
  border-color: #3a4258 !important;
  color: #a8b0c4 !important;
}
.dark-tool-btn:not(.el-button--danger):hover {
  background: rgba(61, 158, 140, 0.14) !important;
  border-color: rgba(61, 158, 140, 0.5) !important;
  color: #3d9e8c !important;
}
.hidden-file { display: none; }
.msg-art-img, .msg-user-img {
  max-width: 100%;
  border-radius: var(--radius-sm);
  margin-top: 8px;
  display: block;
}
.msg-user-img { max-height: 160px; object-fit: cover; }
:deep(.agent-suggest-link) {
  color: var(--color-accent-teal);
  text-decoration: underline;
  cursor: pointer;
}

/* Markdown 渲染样式（.md-body 内为 marked 生成的 HTML） */
:deep(.md-body) {
  word-break: break-word;
}
:deep(.md-body > *:first-child) { margin-top: 0; }
:deep(.md-body > *:last-child) { margin-bottom: 0; }
:deep(.md-body p) {
  margin: 0 0 0.55em;
}
:deep(.md-body p:last-child) { margin-bottom: 0; }
:deep(.md-body strong) {
  color: var(--color-text-primary);
  font-weight: 600;
}
:deep(.md-body hr) {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 0.75em 0;
}
:deep(.md-body ul),
:deep(.md-body ol) {
  margin: 0.35em 0 0.55em;
  padding-left: 1.25em;
}
:deep(.md-body li) {
  margin: 0.2em 0;
}
:deep(.md-body code) {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 0.92em;
  padding: 0.1em 0.35em;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.28);
}
:deep(.md-body pre) {
  margin: 0.5em 0;
  padding: 10px 12px;
  overflow-x: auto;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--color-border);
}
:deep(.md-body pre code) {
  padding: 0;
  background: transparent;
}
:deep(.md-body a) {
  color: var(--color-accent-teal);
}
</style>
