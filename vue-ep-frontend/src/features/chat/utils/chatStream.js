/**
 * 解析 /api/chat 的 SSE 流（支持 JSON data: 行与旧版 [ASR]/[ERR] 前缀）。
 */

export async function* readChatStream(response) {
  if (!response?.body) {
    throw new Error('响应体为空')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const raw of lines) {
      const line = raw.trim()
      if (!line) continue

      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6))
        } catch {
          /* 忽略畸形行 */
        }
        continue
      }

      if (line.startsWith('[ASR]')) {
        yield { type: 'asr', text: line.slice(5).trim() }
        continue
      }
      if (line.startsWith('[ERR]')) {
        yield { type: 'error', text: line.slice(5).trim() }
        continue
      }

      yield { type: 'text', text: line }
    }
  }

  const tail = buffer.trim()
  if (tail.startsWith('data: ')) {
    try {
      yield JSON.parse(tail.slice(6))
    } catch { /* noop */ }
  }
}

/** 工具调用步骤的展示文案 */
export function toolStepLabel(event) {
  if (event.type === 'tool_call') {
    return event.label || event.tool || '执行工具'
  }
  if (event.type === 'tool_result') {
    return `已完成：${event.label || event.tool || '工具'}`
  }
  if (event.type === 'thinking') {
    return event.text || '思考中…'
  }
  if (event.type === 'revive_progress') {
    return event.text || '焕新进行中…'
  }
  return ''
}
