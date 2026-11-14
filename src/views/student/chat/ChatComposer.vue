<script setup>
import { ElInput } from 'element-plus'

defineProps({
  modelValue: { type: String, default: '' },
  isAnonymous: { type: Boolean, default: false },
  currentSessionId: { type: [String, Number], default: null },
  isTyping: { type: Boolean, default: false },
  deepThinkEnabled: { type: Boolean, default: false },
  lastReplyChars: { type: Number, default: 0 },
  lastReplyRatio: { type: Number, default: 1 },
})

const emit = defineEmits(['update:modelValue', 'send', 'toggle-deep'])
</script>

<template>
  <footer class="input-bar">
    <ElInput
      aria-label="输入消息"
      :model-value="modelValue"
      type="textarea"
      :rows="2"
      placeholder="在这里输入你想说的话..."
      resize="none"
      :disabled="!isAnonymous && !currentSessionId"
      @update:model-value="emit('update:modelValue', $event)"
      @keydown.enter.prevent="emit('send')"
    />
    <button
      type="button"
      aria-label="发送消息"
      class="send-btn"
      @click="emit('send')"
      :disabled="!modelValue.trim() || (!isAnonymous && !currentSessionId) || isTyping"
    >
      发送
    </button>
    <button
      type="button"
      class="deep-think-toggle"
      :class="{ active: deepThinkEnabled }"
      @click="emit('toggle-deep')"
      :disabled="isTyping"
    >
      {{ deepThinkEnabled ? '深度思考: 开' : '深度思考: 关' }}
    </button>
  </footer>
  <div v-if="lastReplyChars > 0" class="reply-stats">
    本回答共{{ lastReplyChars }}字，约为您平时请求的{{ lastReplyRatio.toFixed(1) }}倍
  </div>
</template>

<style scoped>
.input-bar {
  border-top: 1px solid var(--border);
  background: var(--surface);
  padding: 12px 16px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.deep-think-toggle {
  width: 120px;
  height: 60px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-subtle);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.deep-think-toggle.active {
  background: var(--accent-sage-soft);
  border-color: var(--success-text);
  color: var(--success-text);
}

.reply-stats {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.input-bar :deep(.el-textarea__inner) {
  min-height: 60px !important;
  border-radius: var(--radius);
  box-shadow: none;
  border: 1px solid var(--border);
  font-size: 14px;
  line-height: 1.6;
}

.send-btn {
  width: 80px;
  height: 60px;
  border: none;
  border-radius: var(--radius);
  background: var(--primary);
  color: var(--surface);
  font-size: 14px;
  cursor: pointer;
}

.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .input-bar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .input-bar :deep(.el-textarea) {
    flex: 1 1 100%;
    min-width: 0;
  }

  .input-bar .send-btn,
  .input-bar .deep-think-toggle {
    min-height: 44px;
  }
}
</style>
