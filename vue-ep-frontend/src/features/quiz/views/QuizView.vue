<template>
  <div class="quiz-root">

    <!-- ══ 加载中 ══════════════════════════════════════════════ -->
    <div v-if="phase === 'loading'" class="quiz-loading">
      <div class="loading-inner">
        <div class="loading-spinner"></div>
        <div class="loading-title">AI 正在出题中…</div>
        <div class="loading-sub">讯飞星火大模型根据非遗知识图谱动态生成题目</div>
        <div v-if="loadingQuestions.length" class="loading-preview">
          <div v-for="(q, i) in loadingQuestions" :key="i" class="preview-card">
            <span class="preview-badge">Q{{ i + 1 }}</span>
            {{ q.question }}
          </div>
        </div>
      </div>
    </div>

    <!-- ══ 错误 ════════════════════════════════════════════════ -->
    <div v-else-if="phase === 'error'" class="quiz-error">
      <el-icon :size="48" color="var(--color-accent-red)"><WarningFilled /></el-icon>
      <div class="error-msg">{{ errorMsg }}</div>
      <el-button type="primary" @click="startQuiz">重新生成题目</el-button>
    </div>

    <!-- ══ 答题主界面 ════════════════════════════════════════ -->
    <div v-else-if="phase === 'playing'" class="quiz-playing">

      <!-- 顶部进度条 -->
      <div class="quiz-header">
        <div class="quiz-progress-bar">
          <div class="quiz-progress-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
        <div class="quiz-meta">
          <span class="q-counter">第 {{ currentIdx + 1 }} / {{ questions.length }} 题</span>
          <span class="q-score">得分：<b>{{ liveScore }}</b></span>
          <span class="q-timer" :class="{ 'timer-warn': timeLeft <= 10 }">
            <el-icon><Timer /></el-icon> {{ timeLeft }}s
          </span>
          <transition name="combo-pop">
            <span v-if="comboCount >= 2" class="combo-badge">{{ comboCount }} 连击</span>
          </transition>
        </div>
      </div>

      <!-- 题目卡 -->
      <transition name="slide-fade" mode="out-in">
        <div class="question-card" :key="currentIdx">
          <div class="q-label">Q{{ currentIdx + 1 }}</div>
          <div class="q-text">{{ currentQ.question }}</div>
          <el-button size="small" text class="read-q-btn" @click="readQuestionAloud">
            <el-icon><Microphone /></el-icon> 朗读题目
          </el-button>

          <div class="options-grid">
            <div
              v-for="(opt, oi) in currentQ.options"
              :key="oi"
              class="option-btn"
              :class="optionClass(opt)"
              @click="selectAnswer(opt)"
            >
              <span class="opt-letter">{{ opt.charAt(0) }}</span>
              <span class="opt-text">{{ opt.slice(3) }}</span>
            </div>
          </div>

          <!-- 答题反馈 -->
          <transition name="fade">
            <div v-if="answered" class="answer-feedback" :class="isCorrect ? 'correct' : 'wrong'">
              <el-icon v-if="isCorrect"><CircleCheckFilled /></el-icon>
              <el-icon v-else><CircleCloseFilled /></el-icon>
              <span>{{ isCorrect ? '回答正确！' : `正确答案是 ${currentQ.answer}` }}</span>
              <span class="explanation">{{ currentQ.explanation }}</span>
            </div>
          </transition>

          <div v-if="answered" class="next-btn-wrap">
            <el-button
              type="primary"
              size="large"
              @click="nextQuestion"
              class="next-btn"
            >
              {{ currentIdx < questions.length - 1 ? '下一题 →' : '查看结果 →' }}
            </el-button>
          </div>
        </div>
      </transition>

    </div>

    <!-- ══ 结果页 ════════════════════════════════════════════ -->
    <div v-else-if="phase === 'result'" class="quiz-result">
      <div class="result-card">

        <div class="result-title">
          <span v-if="resultEmoji" class="result-emoji">{{ resultEmoji }}</span>
          闯关完成！
        </div>

        <div class="result-score-ring">
          <svg viewBox="0 0 120 120" class="ring-svg">
            <circle cx="60" cy="60" r="52" class="ring-bg" />
            <circle
              cx="60" cy="60" r="52"
              class="ring-fill"
              :stroke-dasharray="`${scoreArc} 327`"
            />
          </svg>
          <div class="ring-label">
            <div class="ring-score">{{ finalScore }}</div>
            <div class="ring-unit">分</div>
          </div>
        </div>

        <div class="result-stats">
          <div class="stat-item">
            <div class="stat-val green">{{ correctCount }}</div>
            <div class="stat-key">答对</div>
          </div>
          <div class="stat-item">
            <div class="stat-val red">{{ questions.length - correctCount }}</div>
            <div class="stat-key">答错</div>
          </div>
          <div class="stat-item">
            <div class="stat-val gold">{{ timeUsed }}s</div>
            <div class="stat-key">用时</div>
          </div>
          <div class="stat-item">
            <div class="stat-val">No.{{ myRank ?? '—' }}</div>
            <div class="stat-key">排名</div>
          </div>
        </div>

        <div class="result-actions">
          <el-button type="primary" @click="startQuiz">再来一局</el-button>
          <el-button @click="phase = 'leaderboard'; loadLeaderboard()">查看排行榜</el-button>
        </div>
      </div>

      <!-- 答题详情复盘 -->
      <div class="review-list">
        <div class="review-title">答题详情</div>
        <div v-for="(q, i) in questions" :key="i" class="review-item">
          <div class="review-q">
            <span class="review-badge" :class="answers[i] === q.answer ? 'right' : 'wrong'">
              {{ answers[i] === q.answer ? '✓' : '✗' }}
            </span>
            Q{{ i + 1 }}. {{ q.question }}
          </div>
          <div class="review-ans">
            你的答案：<b :class="answers[i] === q.answer ? 'green' : 'red'">{{ answers[i] || '未作答' }}</b>
            &nbsp;|&nbsp;
            正确答案：<b class="green">{{ q.answer }}</b>
          </div>
          <div class="review-exp">{{ q.explanation }}</div>
        </div>
      </div>
    </div>

    <!-- ══ 排行榜 ════════════════════════════════════════════ -->
    <div v-else-if="phase === 'leaderboard'" class="quiz-leaderboard">
      <div class="lb-header">
        <div class="lb-title"><el-icon><Trophy /></el-icon> 非遗闯关排行榜</div>
        <el-button size="small" @click="phase = 'intro'">← 返回</el-button>
      </div>

      <div class="lb-my-rank" v-if="myRank">
        我的排名：<b class="gold">No.{{ myRank }}</b>
        &emsp;最高得分：<b class="gold">{{ myBest?.score ?? '—' }}</b>
      </div>

      <el-table :data="board" class="lb-table" stripe>
        <el-table-column label="排名" width="70">
          <template #default="{ row }">
            <span class="rank-badge" :class="`rank-${row.rank}`">{{ row.rank }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" />
        <el-table-column prop="best_score" label="最高分" width="90">
          <template #default="{ row }">
            <b class="gold">{{ row.best_score }}</b>
          </template>
        </el-table-column>
        <el-table-column prop="best_correct" label="最多答对" width="100" />
        <el-table-column prop="best_time" label="最短用时" width="100">
          <template #default="{ row }">{{ row.best_time }}s</template>
        </el-table-column>
        <el-table-column prop="play_count" label="游戏次数" width="100" />
      </el-table>

      <div class="lb-actions">
        <el-button type="primary" @click="startQuiz">开始闯关</el-button>
      </div>
    </div>

    <!-- ══ 介绍页（初始状态） ═══════════════════════════════ -->
    <div v-else class="quiz-intro">
      <div class="intro-card">
        <div class="intro-icon" aria-hidden="true">遗</div>
        <div class="intro-title">AI 非遗闯关答题</div>
        <div class="intro-desc">
          讯飞星火大模型根据非遗知识图谱动态出题，<br>
          考察你对中华非物质文化遗产的了解程度。
        </div>
        <div class="intro-rules">
          <div class="rule-item"><el-icon><Star /></el-icon> 共 5 道选择题，每题 20 分</div>
          <div class="rule-item"><el-icon><Timer /></el-icon> 每题限时 30 秒，越快加分越多</div>
          <div class="rule-item"><el-icon><Trophy /></el-icon> 完成后可进入全球排行榜</div>
        </div>
        <div class="intro-actions">
          <el-button type="primary" size="large" @click="startQuiz" class="start-btn">
            开始闯关
          </el-button>
          <el-button size="large" @click="phase = 'leaderboard'; loadLeaderboard()">
            查看排行榜
          </el-button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Timer, Trophy, Star, WarningFilled,
  CircleCheckFilled, CircleCloseFilled
} from '@element-plus/icons-vue'
import { streamGenerateQuiz, submitQuiz, getLeaderboard, fetchTtsPcm } from '@/api'
import { readQuizStream } from '@/features/quiz/utils/quizStream'

// ─── 状态 ─────────────────────────────────────────────────────
const phase       = ref('intro')   // intro | loading | playing | result | leaderboard | error
const questions   = ref([])
const currentIdx  = ref(0)
const answers     = ref([])        // 每题用户选项
const answered    = ref(false)
const isCorrect   = ref(false)
const timeLeft    = ref(30)
const totalTime   = ref(300)       // 全局总计时
const timeUsed    = ref(0)
const liveScore   = ref(0)
const comboCount  = ref(0)
const errorMsg    = ref('')
const loadingQuestions = ref([])

// 结果相关
const finalScore  = ref(0)
const correctCount = ref(0)
const myRank      = ref(null)
const myBest      = ref(null)
const board       = ref([])

let questionTimer = null
let globalTimer   = null

// ─── 计算属性 ──────────────────────────────────────────────────
const currentQ    = computed(() => questions.value[currentIdx.value] || {})
const progressPct = computed(() =>
  questions.value.length ? ((currentIdx.value) / questions.value.length) * 100 : 0
)
const scoreArc    = computed(() => (finalScore.value / 100) * 327)
const resultEmoji = computed(() => {
  if (finalScore.value >= 90) return ""
  if (finalScore.value >= 70) return ''
  if (finalScore.value >= 50) return ""
  return ""
})

// ─── 答题核心 ─────────────────────────────────────────────────

// 找到这段
async function startQuiz() {
  phase.value = 'loading'
  resetState()
  loadingQuestions.value = []
  try {
    const res = await streamGenerateQuiz()
    if (!res.ok) throw new Error('出题请求失败')
    const list = []
    for await (const event of readQuizStream(res)) {
      if (event.type === 'error') throw new Error(event.msg || '出题失败')
      if (event.type === 'question') {
        list.push(event.data)
        loadingQuestions.value = [...list]
      }
      if (event.type === 'done') break
    }
    if (!list.length) throw new Error('未收到题目')
    questions.value = list
    answers.value = new Array(list.length).fill(null)
    phase.value = 'playing'
    loadingQuestions.value = []
    startGlobalTimer()
    startQuestionTimer()
  } catch (e) {
    const msg = e.message?.includes('timeout')
      ? 'AI出题响应较慢，请点击重新生成'
      : (e.message || '出题失败，请重试')
    phase.value = 'error'
    errorMsg.value = msg
    ElMessage.warning(msg)
  }
}

function resetState() {
  clearInterval(questionTimer)
  clearInterval(globalTimer)
  currentIdx.value = 0
  answers.value    = []
  answered.value   = false
  isCorrect.value  = false
  timeLeft.value   = 30
  liveScore.value  = 0
  comboCount.value = 0
  timeUsed.value   = 0
}

async function readQuestionAloud() {
  const q = currentQ.value?.question
  if (!q) return
  try {
    const pcm = await fetchTtsPcm(q.slice(0, 200))
    const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 })
    const view = new DataView(pcm)
    const n = pcm.byteLength / 2
    const buf = ctx.createBuffer(1, n, 16000)
    const ch = buf.getChannelData(0)
    for (let i = 0; i < n; i++) ch[i] = view.getInt16(i * 2, true) / 32768
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    src.start(0)
  } catch { /* silent */ }
}

function startQuestionTimer() {
  clearInterval(questionTimer)
  timeLeft.value = 30
  questionTimer = setInterval(() => {
    timeLeft.value--
    if (timeLeft.value <= 0) {
      clearInterval(questionTimer)
      if (!answered.value) {
        // 超时自动提交空答案
        answered.value = true
        isCorrect.value = false
      }
    }
  }, 1000)
}

function startGlobalTimer() {
  clearInterval(globalTimer)
  const start = Date.now()
  globalTimer = setInterval(() => {
    timeUsed.value = Math.floor((Date.now() - start) / 1000)
  }, 1000)
}

function selectAnswer(opt) {
  if (answered.value) return
  const letter = opt.charAt(0).toUpperCase()
  answers.value[currentIdx.value] = letter
  answered.value = true
  isCorrect.value = letter === (currentQ.value.answer || '').toUpperCase()
  if (isCorrect.value) {
    liveScore.value += 20
    comboCount.value += 1
  } else {
    comboCount.value = 0
  }
  clearInterval(questionTimer)
}

function optionClass(opt) {
  if (!answered.value) return ''
  const letter   = opt.charAt(0).toUpperCase()
  const correct  = (currentQ.value.answer || '').toUpperCase()
  const selected = answers.value[currentIdx.value]
  if (letter === correct)             return 'opt-correct'
  if (letter === selected)            return 'opt-wrong'
  return 'opt-dim'
}

function nextQuestion() {
  answered.value = false
  isCorrect.value = false
  if (currentIdx.value < questions.value.length - 1) {
    currentIdx.value++
    startQuestionTimer()
  } else {
    finishQuiz()
  }
}

async function finishQuiz() {
  clearInterval(questionTimer)
  clearInterval(globalTimer)

  const answerMap = {}
  questions.value.forEach((q, i) => {
    answerMap[String(q.id)] = answers.value[i] || ''
  })

  try {
    const res = await submitQuiz({
      answers:   answerMap,
      questions: questions.value,
      time_used: timeUsed.value,
    })
    if (res.data.status === 'success') {
      finalScore.value  = res.data.score
      correctCount.value = res.data.correct
      myRank.value      = res.data.rank
    }
  } catch (e) {
    ElMessage.warning('成绩提交失败，本局成绩不计入排行榜')
    // 本地计算
    finalScore.value   = liveScore.value
    correctCount.value = answers.value.filter((a, i) =>
      a === (questions.value[i]?.answer || '').toUpperCase()
    ).length
  }

  phase.value = 'result'
}

async function loadLeaderboard() {
  try {
    const res = await getLeaderboard()
    board.value  = res.data.board
    myRank.value = res.data.my_rank
    myBest.value = res.data.my_best
  } catch (e) {
    ElMessage.error('排行榜加载失败')
  }
}

onUnmounted(() => {
  clearInterval(questionTimer)
  clearInterval(globalTimer)
})
</script>

<style scoped>
/* ── 根容器 ─────────────────────────────────────────────────── */
.quiz-root {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  background: var(--color-bg-base);
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* ── 加载动画 ────────────────────────────────────────────────── */
.quiz-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.loading-inner { text-align: center; }
.loading-spinner {
  width: 56px; height: 56px;
  border: 4px solid var(--color-border);
  border-top-color: var(--color-accent-teal);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
  margin: 0 auto 20px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-title { font-size: 18px; color: var(--color-text-primary); margin-bottom: 8px; }
.loading-sub   { font-size: 13px; color: var(--color-text-secondary); }

/* ── 错误 ───────────────────────────────────────────────────── */
.quiz-error {
  display: flex; flex-direction: column; align-items: center;
  gap: 16px; margin-top: 80px;
}
.error-msg { color: var(--color-text-secondary); font-size: 15px; }

/* ── 答题主界面 ─────────────────────────────────────────────── */
.quiz-playing { width: 100%; max-width: 680px; }

.quiz-header { margin-bottom: 20px; }
.quiz-progress-bar {
  height: 6px;
  background: var(--color-border);
  border-radius: 3px;
  margin-bottom: 12px;
  overflow: hidden;
}
.quiz-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent-teal), var(--color-accent-gold));
  border-radius: 3px;
  transition: width 0.4s ease;
}
.quiz-meta {
  display: flex; gap: 16px; align-items: center;
  font-size: 13px; color: var(--color-text-secondary);
}
.q-counter { margin-right: auto; }
.q-score b { color: var(--color-accent-gold); }
.combo-badge {
  color: var(--color-accent-gold);
  font-weight: 600;
  font-size: 13px;
  animation: combo-pulse 0.6s ease;
}
@keyframes combo-pulse {
  0% { transform: scale(0.8); opacity: 0.5; }
  50% { transform: scale(1.15); }
  100% { transform: scale(1); opacity: 1; }
}
.combo-pop-enter-active { animation: combo-pulse 0.4s ease; }
.read-q-btn { margin: -4px 0 10px 4px; }
.q-timer {
  display: flex; align-items: center; gap: 4px;
  font-variant-numeric: tabular-nums;
  color: var(--color-accent-teal);
  font-weight: 600;
}
.timer-warn { color: var(--color-accent-red) !important; animation: blink 0.8s linear infinite; }
@keyframes blink { 50% { opacity: 0.4; } }

/* ── 题目卡 ─────────────────────────────────────────────────── */
.question-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 28px 32px;
}
.q-label {
  font-size: 11px; font-weight: 600; letter-spacing: 0.2px;
  color: var(--color-accent-teal); margin-bottom: 12px;
}
.q-text {
  font-size: 18px; font-family: var(--font-serif);
  color: var(--color-text-primary);
  line-height: 1.65; margin-bottom: 24px;
}

/* 选项 */
.options-grid { display: flex; flex-direction: column; gap: 10px; }
.option-btn {
  display: flex; align-items: center; gap: 14px;
  padding: 13px 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: color 0.2s, background-color 0.2s, border-color 0.2s;
  background: var(--color-bg-hover);
}
.option-btn:hover:not(.opt-correct):not(.opt-wrong):not(.opt-dim) {
  border-color: var(--color-accent-teal);
  background: rgba(61, 158, 140, 0.08);
}
.opt-letter {
  width: 28px; height: 28px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--color-border);
  font-size: 12px; font-weight: 600;
  color: var(--color-text-secondary);
}
.opt-text { font-size: 15px; color: var(--color-text-primary); }

.opt-correct { border-color: #27ae60 !important; background: rgba(39,174,96,0.1) !important; }
.opt-correct .opt-letter { background: #27ae60 !important; color: #fff !important; }
.opt-wrong   { border-color: var(--color-accent-red) !important; background: rgba(192,57,43,0.1) !important; }
.opt-wrong   .opt-letter { background: var(--color-accent-red) !important; color: #fff !important; }
.opt-dim     { opacity: 0.45; cursor: default; }

/* 反馈区 */
.answer-feedback {
  display: flex; align-items: flex-start; gap: 8px;
  margin-top: 18px; padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: 14px; line-height: 1.6;
}
.answer-feedback.correct { background: rgba(39,174,96,0.12); color: #2ecc71; }
.answer-feedback.wrong   { background: rgba(192,57,43,0.12); color: #e74c3c; }
.explanation { margin-left: 4px; color: var(--color-text-secondary); font-size: 13px; }

/* 下一题按钮 */
.next-btn-wrap { margin-top: 20px; display: flex; justify-content: flex-end; }
.next-btn { min-width: 140px; }

/* ── 动画 ───────────────────────────────────────────────────── */
.slide-fade-enter-active, .slide-fade-leave-active { transition: opacity 0.3s ease, transform 0.3s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateX(30px); }
.slide-fade-leave-to   { opacity: 0; transform: translateX(-30px); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ── 结果页 ─────────────────────────────────────────────────── */
.quiz-result { width: 100%; max-width: 680px; }
.result-card {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); padding: 32px;
  display: flex; flex-direction: column; align-items: center; gap: 20px;
  margin-bottom: 24px;
}
.result-title {
  font-size: 22px; font-family: var(--font-serif);
  color: var(--color-text-primary); display: flex; align-items: center; gap: 8px;
}
.result-emoji { font-size: 28px; }

/* SVG 得分环 */
.result-score-ring { position: relative; width: 140px; height: 140px; }
.ring-svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring-bg   { fill: none; stroke: var(--color-border); stroke-width: 10; }
.ring-fill {
  fill: none; stroke: var(--color-accent-gold); stroke-width: 10;
  stroke-linecap: round;
  transition: stroke-dasharray 1s ease;
}
.ring-label {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.ring-score { font-size: 36px; font-weight: 600; color: var(--color-accent-gold); }
.ring-unit  { font-size: 13px; color: var(--color-text-secondary); }

/* 统计 */
.result-stats { display: flex; gap: 32px; }
.stat-item { text-align: center; }
.stat-val { font-size: 28px; font-weight: 600; color: var(--color-text-primary); }
.stat-key { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.green { color: #2ecc71 !important; }
.red   { color: var(--color-accent-red) !important; }
.gold  { color: var(--color-accent-gold) !important; }

.result-actions { display: flex; gap: 12px; }

/* 复盘列表 */
.review-list {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); padding: 20px 24px;
}
.review-title { font-size: 15px; font-weight: 600; color: var(--color-text-primary); margin-bottom: 16px; }
.review-item { padding: 12px 0; border-bottom: 1px solid var(--color-border-soft); }
.review-item:last-child { border-bottom: none; }
.review-q { display: flex; align-items: flex-start; gap: 8px; font-size: 14px; color: var(--color-text-primary); margin-bottom: 6px; }
.review-badge {
  width: 20px; height: 20px; flex-shrink: 0;
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600;
}
.review-badge.right { background: rgba(39,174,96,0.2); color: #2ecc71; }
.review-badge.wrong { background: rgba(192,57,43,0.2); color: var(--color-accent-red); }
.review-ans { font-size: 13px; color: var(--color-text-secondary); margin-bottom: 4px; margin-left: 28px; }
.review-exp { font-size: 12px; color: var(--color-text-muted); margin-left: 28px; }

/* ── 排行榜 ─────────────────────────────────────────────────── */
.quiz-leaderboard { width: 100%; max-width: 700px; }
.lb-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.lb-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 18px; font-family: var(--font-serif); color: var(--color-text-primary);
}
.lb-my-rank {
  padding: 10px 16px; background: var(--color-bg-card);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 14px; color: var(--color-text-secondary);
  margin-bottom: 16px;
}
.lb-table { width: 100%; }
.rank-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 50%;
  font-size: 12px; font-weight: 600;
  background: var(--color-border); color: var(--color-text-secondary);
}
.rank-1 { background: #c9a84c; color: #fff; }
.rank-2 { background: #8fa8c8; color: #fff; }
.rank-3 { background: #b87333; color: #fff; }
.lb-actions { margin-top: 20px; display: flex; justify-content: center; }

/* ── 介绍页 ─────────────────────────────────────────────────── */
.quiz-intro {
  flex: 1; display: flex; align-items: center; justify-content: center; width: 100%;
}
.intro-card {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); padding: 48px 56px;
  text-align: center; max-width: 500px; width: 100%;
}
.intro-icon { font-size: 56px; margin-bottom: 12px; }
.intro-title {
  font-size: 26px; font-family: var(--font-serif);
  color: var(--color-text-primary); margin-bottom: 12px;
}
.intro-desc { font-size: 14px; color: var(--color-text-secondary); line-height: 1.8; margin-bottom: 24px; }
.intro-rules { display: flex; flex-direction: column; gap: 10px; margin-bottom: 32px; }
.rule-item {
  display: flex; align-items: center; gap: 8px; justify-content: center;
  font-size: 14px; color: var(--color-text-secondary);
}
.intro-actions { display: flex; flex-direction: column; gap: 12px; align-items: center; }
.start-btn { min-width: 180px; font-size: 16px; }

/* Element Plus 深色覆盖 */
:deep(.el-table) { background: transparent !important; }
:deep(.el-table tr) { background: var(--color-bg-card) !important; }
:deep(.el-table__row:hover td) { background: var(--color-bg-hover) !important; }
:deep(.el-table td) { border-bottom-color: var(--color-border) !important; }
:deep(.el-table th) {
  background: var(--color-bg-panel) !important;
  border-bottom-color: var(--color-border) !important;
}
</style>
