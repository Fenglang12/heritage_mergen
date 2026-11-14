/**
 * api/index.js — 统一管理所有后端接口（含社区 & 管理员新接口）
 */
import axios from 'axios'
import router from '@/core/router'
// # 已注释：地图定位不再依赖公网 IP
// import { ensureClientPublicIp, clearClientPublicIpCache } from '@/features/map/utils/clientIp'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 30000
})

// # 已注释：不再给 default_local / get_location 附加 X-Client-Public-IP
// const IP_LOCATION_PATHS = ['/default_local', '/get_location']
// api.interceptors.request.use(async (config) => { ... ensureClientPublicIp ... })

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('username')
      localStorage.removeItem('role')
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

// ── 认证 ────────────────────────────────────────────────────
export const login    = (username, password) => api.post('/login',    { username, password })
export const register = (username, password) => api.post('/register', { username, password })
export const logout   = ()                   => api.get('/logout')

// ── 地图 ────────────────────────────────────────────────────
/**
 * 仅浏览器精确位置：必须带 lng/lat。
 * IP 头 / 无坐标请求已停用。
 */
export async function getDefaultLocal(forceIp = false, coords = null) {
  // # 已注释：不再查询/传递公网 IP
  // if (forceIp) clearClientPublicIpCache()
  // await ensureClientPublicIp(forceIp)
  if (coords?.lng == null || coords?.lat == null) {
    const err = new Error('缺少浏览器精确坐标，已关闭 IP 定位')
    err.code = 'GPS_REQUIRED'
    return Promise.reject(err)
  }
  const params = { lng: coords.lng, lat: coords.lat }
  console.info('[API] default_local 仅 GPS', params)
  return api.get('/default_local', { params })
}
export async function getIpLocation(forceIp = false, coords = null) {
  // # 已注释：IP 定位
  // if (forceIp) clearClientPublicIpCache()
  // await ensureClientPublicIp(forceIp)
  if (coords?.lng == null || coords?.lat == null) {
    const err = new Error('缺少浏览器精确坐标')
    err.code = 'GPS_REQUIRED'
    return Promise.reject(err)
  }
  return api.get('/get_location', { params: { lng: coords.lng, lat: coords.lat } })
}

/** Agent / 对话带参跳转：按城市+关键词搜索地图标点 */
export const searchMapMarkers = (city, keyword) =>
  api.get('/map/search', { params: { city: city || undefined, keyword } })

// ── 识图 ────────────────────────────────────────────────────
export const analyzeSource = (image, session_id, voice_hint = '') =>
  api.post('/analyze_source', { image, session_id, voice_hint })
export const analyzeSourceVideo = (video, session_id) => api.post('/analyze_source_video', { video, session_id }, { timeout: 120000 })

// ── 焕新 ────────────────────────────────────────────────────
export const generateArt  = (prompt, image, session_id) => api.post('/generate_art', { prompt, image, session_id })

/** 非遗焕新 SSE */
export const generateArtStream = (prompt, image) =>
  fetch('/api/generate_art/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ prompt, image }),
  })
export const queryArtTask = (taskId) => api.get(`/query_art/${taskId}`)

// ── 会话 ────────────────────────────────────────────────────
export const getSessions        = ()    => api.get('/sessions')
export const createSession      = ()    => api.post('/session/create')
export const updateSessionTitle = (sid, title) => api.patch(`/session/${sid}`, { title })
export const getSessionHistory  = (sid) => api.get(`/history/${sid}`)
export const clearSession       = (sid) => api.post('/clear', { session_id: sid })

// ── 图谱 ────────────────────────────────────────────────────
export const getGraphData = () => api.get('/graph_data')

// ── TTS ─────────────────────────────────────────────────────
// TTS POST：返回原始 PCM 数据（aue=raw, 16k 16bit 单声道）
export const fetchTtsPcm = async (text) => {
  const res = await fetch('/api/stream_voice', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ text })
  })
  if (!res.ok) throw new Error('TTS 请求失败')
  const arrayBuffer = await res.arrayBuffer()
  return arrayBuffer
}

// ── 流式对话（Agent SSE）──────────────────────────────────────
function postChatStream(body) {
  return fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body)
  })
}

/** @param {object} [geo] 可选浏览器 GPS：{ lng, lat, city, citycode } */
export const streamChat = (message, session_id, geo = null) =>
  postChatStream({ message, session_id, ...(geo || {}) })

export const streamChatAudio = (audio_b64, session_id, geo = null) =>
  postChatStream({ audio: audio_b64, session_id, ...(geo || {}) })

export const streamChatImage = (image, session_id, message = '', geo = null) =>
  postChatStream({ image, message, session_id, ...(geo || {}) })

/** 独立语音转文字（识图/焕新/答题页复用） */
export const transcribeAudio = (audio_b64) =>
  api.post('/asr', { audio: audio_b64 }, { timeout: 60000 })

export const queryGraph = (question) =>
  api.post('/graph/query', { question })

// ── 用户反馈 ─────────────────────────────────────────────────
export const submitFeedback = (data) => api.post('/feedback/submit', data)
export const getMyFeedbacks = (page = 1) => api.get('/feedback/my', { params: { page } })

// ── 社区打卡 ─────────────────────────────────────────────────
export const submitCheckin   = (data)              => api.post('/checkin/submit', data)
export const listCheckins    = (page = 1, site = '') => api.get('/checkin/list', { params: { page, site } })
export const getCheckinPins  = ()                  => api.get('/checkin/map_pins')
export const getMyCheckins   = (page = 1)          => api.get('/checkin/my', { params: { page } })

// ── 打卡评论 ─────────────────────────────────────────────────
export const getComments   = (cid)     => api.get(`/checkin/${cid}/comments`)
export const addComment    = (cid, content) => api.post(`/checkin/${cid}/comment`, { content })
export const deleteComment = (commentId)    => api.delete(`/comment/${commentId}/delete`)

// ── 管理员接口 ───────────────────────────────────────────────
export const adminGetStats     = ()              => api.get('/admin/stats')
export const adminListUsers    = (page, keyword) => api.get('/admin/users', { params: { page, keyword } })
export const adminBanUser      = (uid, reason)   => api.post(`/admin/user/${uid}/ban`,   { reason })
export const adminUnbanUser    = (uid)            => api.post(`/admin/user/${uid}/unban`)
export const adminListFeedbacks = (page, status) => api.get('/admin/feedbacks', { params: { page, status } })
export const adminReplyFeedback = (fid, reply, status) => api.post(`/admin/feedback/${fid}/reply`, { reply, status })
export const adminListCheckins  = (page, status) => api.get('/admin/checkins', { params: { page, status } })
export const adminReviewCheckin = (cid, action, reason) => api.post(`/admin/checkin/${cid}/review`, { action, reason })
export const adminDeleteCheckin = (cid)          => api.delete(`/admin/checkin/${cid}/delete`)

// ── 闯关答题 ─────────────────────────────────────────────────
export const generateQuiz = () => api.get('/quiz/generate', { timeout: 90000 })

export const streamGenerateQuiz = () =>
  fetch('/api/quiz/generate/stream', { method: 'GET', credentials: 'include' })

export const submitQuiz     = (data) => api.post('/quiz/submit', data)
export const getLeaderboard = () => api.get('/quiz/leaderboard')

// ── 研学报告 ─────────────────────────────────────────────────
export const getLatestReport = () => api.get('/report/latest')

export const generateReportStream = () =>
  fetch('/api/report/generate/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  })

// ── 管理员热力图 ──────────────────────────────────────────────
export const adminHeatmapHeritage = () => api.get('/admin/heatmap/heritage')
export const adminHeatmapCheckin  = () => api.get('/admin/heatmap/checkin')

export default api
