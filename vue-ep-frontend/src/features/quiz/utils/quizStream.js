/**
 * 解析 /api/quiz/generate/stream 的 SSE 题目流。
 */

export async function* readQuizStream(response) {
  if (!response?.body) throw new Error('响应体为空')

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
      if (!line.startsWith('data: ')) continue
      try {
        yield JSON.parse(line.slice(6))
      } catch { /* skip */ }
    }
  }
}
