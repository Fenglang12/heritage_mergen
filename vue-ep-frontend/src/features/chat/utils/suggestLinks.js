/** Agent 回答末尾功能推荐链接：路径与默认文案（对话不引导至闯关 /quiz） */
export const AGENT_PATH_LABELS = {
  '/map': '打开非遗地图',
  '/revive': '非遗焕新',
  '/graph': '知识图谱',
  '/source': '识图溯源',
  '/report': '研学报告',
  '/community': '打卡广场',
}

const VALID_PATHS = new Set(Object.keys(AGENT_PATH_LABELS))

/** 构建仅匹配白名单站内路径的 Markdown 链接正则 */
function buildValidPathLinkRe() {
  const pathPattern = Object.keys(AGENT_PATH_LABELS)
    .map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|')
  return new RegExp(`\\[([^\\]]+)\\]\\((${pathPattern})\\)`, 'gi')
}

const VALID_PATH_LINK_RE = buildValidPathLinkRe()

function rewriteQuizLinks(text, fallbackPath = '/graph') {
  const label = AGENT_PATH_LABELS[fallbackPath] || '知识图谱'
  const replacement = `[${label}](${fallbackPath})`
  return text.replace(/\[([^\]]+)\]\(\/quiz[^)]*\)/gi, replacement)
}

/**
 * 修正模型误输出的 [/graph]、[/search_heritage?query=…]、[/quiz] 等为标准 Markdown。
 */
export function normalizeAgentSuggestLinks(text) {
  if (!text) return ''
  let out = rewriteQuizLinks(text)
  for (const [path, label] of Object.entries(AGENT_PATH_LABELS)) {
    const esc = path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    out = out.replace(new RegExp(`\\[${esc}\\](?!\\s*\\()`, 'gi'), `[${label}](${path})`)
  }
  out = out.replace(/\[([^\]]+)\]\((\/[^)]+)\)/gi, (match, linkLabel, path) => {
    const base = path.split('?')[0].replace(/\/+$/, '')
    if (base === '/quiz' || base.startsWith('/quiz')) {
      return `[${AGENT_PATH_LABELS['/graph']}](/graph)`
    }
    if (VALID_PATHS.has(base)) return match
    if (/search_heritage|query_graph|heritage/i.test(base)) {
      return `[${AGENT_PATH_LABELS['/graph']}](/graph)`
    }
    return `[${AGENT_PATH_LABELS['/graph']}](/graph)`
  })
  return rewriteQuizLinks(out)
}

/** 将 Agent 文本转为可展示 HTML（含可点击推荐链接，仅白名单路径） */
export function renderAgentMessageHtml(text) {
  let html = normalizeAgentSuggestLinks(text).replace(/\n/g, '<br>')
  html = html.replace(
    VALID_PATH_LINK_RE,
    '<a href="$2" class="agent-suggest-link" data-path="$2">$1</a>',
  )
  return html
}
