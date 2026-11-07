import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { transcribeAudio } from '@/api'

/** 按住说话 → WAV Base64 → /api/asr */
export function useVoiceInput(onText) {
  const isRecording = ref(false)
  let audioContext = null
  let audioStream = null
  let processor = null
  let audioChunks = []

  function encodeWAV(chunks, rate) {
    let len = 0
    chunks.forEach(c => { len += c.length })
    const flat = new Float32Array(len)
    let off = 0
    chunks.forEach(c => { flat.set(c, off); off += c.length })
    const buf = new ArrayBuffer(44 + flat.length * 2)
    const v = new DataView(buf)
    const ws = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)) }
    ws(0, 'RIFF')
    v.setUint32(4, 36 + flat.length * 2, true)
    ws(8, 'WAVE')
    ws(12, 'fmt ')
    v.setUint32(16, 16, true)
    v.setUint16(20, 1, true)
    v.setUint16(22, 1, true)
    v.setUint32(24, rate, true)
    v.setUint32(28, rate * 2, true)
    v.setUint16(32, 2, true)
    v.setUint16(34, 16, true)
    ws(36, 'data')
    v.setUint32(40, flat.length * 2, true)
    let p = 44
    flat.forEach(s => {
      s = Math.max(-1, Math.min(1, s))
      v.setInt16(p, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
      p += 2
    })
    return new Blob([v], { type: 'audio/wav' })
  }

  async function startRecording() {
    if (isRecording.value) return
    try {
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const AC = window.AudioContext || window.webkitAudioContext
      audioContext = new AC({ sampleRate: 16000 })
      const src = audioContext.createMediaStreamSource(audioStream)
      processor = audioContext.createScriptProcessor(4096, 1, 1)
      audioChunks = []
      processor.onaudioprocess = (e) => {
        if (isRecording.value) audioChunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      }
      src.connect(processor)
      processor.connect(audioContext.destination)
      isRecording.value = true
    } catch {
      ElMessage.warning('请允许麦克风权限')
    }
  }

  async function stopRecording() {
    if (!isRecording.value) return
    isRecording.value = false
    if (processor) processor.disconnect()
    if (audioStream) audioStream.getTracks().forEach(t => t.stop())

    const sampleCount = audioChunks.reduce((n, c) => n + c.length, 0)
    if (sampleCount < 1600) {
      ElMessage.warning('录音太短，请按住多说一两秒')
      if (audioContext) {
        try { await audioContext.close() } catch { /* ignore */ }
      }
      audioContext = null
      return
    }

    const rate = audioContext?.sampleRate || 16000
    const wav = encodeWAV(audioChunks, rate)
    if (audioContext) {
      try { await audioContext.close() } catch { /* ignore */ }
    }
    audioContext = null

    const reader = new FileReader()
    reader.readAsDataURL(wav)
    reader.onloadend = async () => {
      try {
        const res = await transcribeAudio(reader.result)
        const text = res.data?.text
        if (res.data?.status === 'success' && text && onText) {
          onText(text)
        } else {
          ElMessage.warning(res.data?.msg || '未识别到语音内容')
        }
      } catch (err) {
        const msg = err.response?.data?.msg || err.message || '语音识别失败'
        ElMessage.error(msg)
      }
    }
  }

  return { isRecording, startRecording, stopRecording }
}
