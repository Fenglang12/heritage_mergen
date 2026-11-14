import { marked } from 'marked'

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

marked.setOptions({
  gfm: true,
  breaks: true, // 单换行也转 <br>，贴近聊天习惯
})

/** 站内白名单链接 → 可点击的 agent-suggest-link（由 ChatView 拦截跳转） */
function decorateAgentLinks(html) {
  return html.replace(
    /<a\s+([^>]*?)href="(\/[^"]+)"([^>]*)>([\s\S]*?)<\/a>/gi,
    (match, pre, href, post, label) => {
      const base = href.split('?')[0].replace(/\/+$/, '') || href
      if (!VALID_PATHS.has(base)) return match
      return `<a href="${href}" class="agent-suggest-link" data-path="${base}">${label}</a>`
    },
  )
}

/**
 * 将 Agent 文本转为可展示 HTML：
 * 1) 规范化站内 Markdown 链接
 * 2) marked 解析 **加粗** / --- 分割线 / - 列表 / [文](路径) 等
 * 3) 白名单路径加 data-path，供气泡点击路由跳转
 */
export function renderAgentMessageHtml(text) {
  const normalized = normalizeAgentSuggestLinks(text || '')
  // 仍保留对原始 md 链接的一次校正，再交给 marked
  const withFixedMd = normalized.replace(VALID_PATH_LINK_RE, '[$1]($2)')
  const html = marked.parse(withFixedMd, { async: false })
  return decorateAgentLinks(typeof html === 'string' ? html : String(html || ''))
}
