# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = 'div'

layout = ROOT / 'vue-ep-frontend/src/views/LayoutView.vue'
t = layout.read_text(encoding='utf-8')
if 'index="/report"' not in t:
    needle = (
        '          <el-menu-item index="/quiz">\n'
        '            <el-icon><Tickets /></el-icon>\n'
        '            <template #title>AI闯关答题</template>\n'
        '          </el-menu-item>\n\n'
        f'          <{D} class="menu-group-label"'
    )
    repl = (
        '          <el-menu-item index="/quiz">\n'
        '            <el-icon><Tickets /></el-icon>\n'
        '            <template #title>AI闯关答题</template>\n'
        '          </el-menu-item>\n'
        '          <el-menu-item index="/report">\n'
        '            <el-icon><Document /></el-icon>\n'
        '            <template #title>研学报告</template>\n'
        '          </el-menu-item>\n\n'
        f'          <{D} class="menu-group-label"'
    )
    t = t.replace(needle, repl)
layout.write_text(t, encoding='utf-8')

quiz = ROOT / 'vue-ep-frontend/src/views/QuizView.vue'
qt = quiz.read_text(encoding='utf-8')

if 'loadingQuestions' not in qt:
    old_block = (
        f'        <{D} class="loading-sub">讯飞星火大模型根据非遗知识图谱动态生成题目</{D}>\n'
        f'      </{D}>'
    )
    new_block = (
        f'        <{D} class="loading-sub">讯飞星火大模型根据非遗知识图谱动态生成题目</{D}>\n'
        f'        <{D} v-if="loadingQuestions.length" class="loading-preview">\n'
        f'          <{D} v-for="(q, i) in loadingQuestions" :key="i" class="preview-card">\n'
        '            <span class="preview-badge">Q{{ i + 1 }}</span>\n'
        '            {{ q.question }}\n'
        f'          </{D}>\n'
        f'        </{D}>\n'
        f'      </{D}>'
    )
    qt = qt.replace(old_block, new_block)

if 'streamGenerateQuiz' not in qt:
    qt = qt.replace(
        "import { generateQuiz, submitQuiz, getLeaderboard } from '../api'",
        "import { streamGenerateQuiz, submitQuiz, getLeaderboard } from '../api'\n"
        "import { readQuizStream } from '../utils/quizStream'",
    )

if 'const loadingQuestions' not in qt:
    qt = qt.replace(
        "const errorMsg    = ref('')",
        "const errorMsg    = ref('')\nconst loadingQuestions = ref([])",
    )

old_start = """async function startQuiz() {
  phase.value = 'loading'
  resetState()
  try {
    const res = await generateQuiz()
    if (res.data.status !== 'success') throw new Error(res.data.msg)
    questions.value = res.data.questions
    answers.value   = new Array(questions.value.length).fill(null)
    phase.value     = 'playing'
    startGlobalTimer()
  } catch (e) {
    // 改成这样：
    const msg = e.code === 'ECONNABORTED' || e.message?.includes('timeout')
      ? 'AI出题响应较慢，请点击重新生成（通常第二次会更快）'
      : (e.message || '出题失败，请重试')
    phase.value = 'error'
    // 如果你的 error 页面有 errorMsg 变量的话也设一下：
    // errorMsg.value = msg
    ElMessage.warning(msg)
  }
}"""

new_start = """async function startQuiz() {
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
}"""

if old_start in qt:
    qt = qt.replace(old_start, new_start)

if '.loading-preview' not in qt:
    qt = qt.replace(
        '.loading-sub {',
        '.loading-preview { margin-top: 20px; width: 100%; max-width: 520px; display: flex; flex-direction: column; gap: 8px; }\n'
        '.preview-card { padding: 10px 12px; background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: 8px; font-size: 12px; color: var(--color-text-secondary); text-align: left; animation: fadeIn 0.3s ease; }\n'
        '.preview-badge { color: var(--color-accent-teal); font-weight: 700; margin-right: 6px; }\n'
        '@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }\n'
        '.loading-sub {',
    )

quiz.write_text(qt, encoding='utf-8')
print('layout has report:', 'index="/report"' in layout.read_text(encoding='utf-8'))
print('quiz has stream:', 'streamGenerateQuiz' in quiz.read_text(encoding='utf-8'))
