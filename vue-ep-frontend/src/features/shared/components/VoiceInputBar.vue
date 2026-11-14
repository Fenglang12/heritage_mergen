<template>
  <div class="voice-bar">
    <el-button
      size="small"
      :type="isRecording ? 'danger' : ''"
      class="voice-btn"
      @mousedown="startRecording"
      @mouseup="stopRecording"
      @mouseleave="isRecording && stopRecording()"
      @touchstart.prevent="startRecording"
      @touchend.prevent="stopRecording"
    >
      <el-icon><Microphone /></el-icon>
      {{ isRecording ? '松开结束' : label }}
    </el-button>
    <span v-if="hint" class="voice-hint">{{ hint }}</span>
  </div>
</template>

<script setup>
import { Microphone } from '@element-plus/icons-vue'
import { useVoiceInput } from '@/features/shared/composables/useVoiceInput'

const props = defineProps({
  label: { type: String, default: '按住说话' },
  hint: { type: String, default: '' },
})
const emit = defineEmits(['text'])

const { isRecording, startRecording, stopRecording } = useVoiceInput((text) => {
  emit('text', text)
})
</script>

<style scoped>
.voice-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.voice-hint {
  font-size: 11px;
  color: var(--color-text-muted);
}
.voice-btn:not(.el-button--danger) {
  --el-button-bg-color: #22262f;
  --el-button-border-color: #3a4258;
  --el-button-text-color: #a8b0c4;
  background: #22262f !important;
  border-color: #3a4258 !important;
  color: #a8b0c4 !important;
}
.voice-btn:not(.el-button--danger):hover {
  background: rgba(61, 158, 140, 0.14) !important;
  border-color: rgba(61, 158, 140, 0.5) !important;
  color: #3d9e8c !important;
}
</style>
