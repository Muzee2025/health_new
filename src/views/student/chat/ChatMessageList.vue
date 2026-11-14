<script setup>
import { nextTick, ref } from 'vue'
import { ElAvatar, ElIcon } from 'element-plus'

defineProps({
  messages: { type: Array, default: () => [] },
  isAnonymous: { type: Boolean, default: false },
  userAvatar: { type: String, default: '' },
  anonymousAvatar: { type: String, default: '' },
  crisisBannerVisible: { type: Boolean, default: false },
  isDeepStreaming: { type: Boolean, default: false },
  thinkingLogs: { type: Array, default: () => [] },
  thinkingAnchorMessageId: { type: [String, Number], default: '' },
  thinkingPhase: { type: String, default: '' },
  phaseLabelMap: { type: Object, default: () => ({}) },
  isTyping: { type: Boolean, default: false },
  instantFeedback: { type: String, default: '' },
  isDangerText: { type: Function, default: () => () => false },
})

const scrollElement = ref(null)

const scrollToBottom = async () => {
  await nextTick()
  if (scrollElement.value) {
    scrollElement.value.scrollTop = scrollElement.value.scrollHeight
  }
}

defineExpose({ scrollToBottom, scrollElement })
</script>

<template>
  <div class="messages-area" ref="scrollElement">
    <div v-if="crisisBannerVisible" class="crisis-banner">
      <ElIcon><LibraryIcon name="alert" /></ElIcon>
      <strong>高危预警</strong>
      <span
        >检测到需要关注的求助信息。系统无法确认人工服务是否已接收，请优先联系实际人工支持。</span
      >
    </div>

    <template v-for="(msg, index) in messages" :key="index">
      <div :class="['message-row', msg.role === 'user' ? 'row-user' : 'row-ai']">
        <div class="avatar-wrap">
          <ElAvatar
            v-if="msg.role === 'user'"
            :size="36"
            :src="isAnonymous ? anonymousAvatar : userAvatar"
          />
          <ElAvatar v-else :size="36" class="mail-avatar">
            <ElIcon><LibraryIcon name="chat" /></ElIcon>
          </ElAvatar>
        </div>

        <div class="message-body">
          <div
            :class="[
              'bubble',
              msg.role === 'user' ? 'bubble-user' : 'bubble-ai',
              msg.role === 'user' && isDangerText(msg.content) ? 'bubble-danger' : '',
            ]"
          >
            <template v-if="msg.role === 'ai'">
              <span class="ai-message-text">{{ msg.content }}</span>
            </template>
            <template v-else>
              {{ msg.content }}
            </template>
          </div>
        </div>
      </div>

      <div
        v-if="
          (isDeepStreaming || thinkingLogs.length) &&
          thinkingAnchorMessageId &&
          msg.id === thinkingAnchorMessageId
        "
        class="thinking-panel"
      >
        <div class="thinking-title">
          <strong>深度思考草稿</strong>
          <span class="thinking-phase">{{ phaseLabelMap[thinkingPhase] || '准备中...' }}</span>
        </div>
        <div class="thinking-lines">
          <div v-for="(line, idx) in thinkingLogs" :key="'thinking-' + idx" class="thinking-line">
            {{ line }}
          </div>
        </div>
      </div>
    </template>

    <div v-if="isTyping && !isDeepStreaming" class="message-row row-ai">
      <div class="avatar-wrap">
        <ElAvatar :size="36" class="mail-avatar">
          <ElIcon><LibraryIcon name="chat" /></ElIcon>
        </ElAvatar>
      </div>
      <div class="message-body">
        <div class="bubble bubble-ai typing">
          <span v-if="instantFeedback">{{ instantFeedback }}</span>
          <template v-else><i></i><i></i><i></i></template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: var(--bg);
}

.crisis-banner {
  position: sticky;
  top: 0;
  z-index: 4;
  margin-bottom: 14px;
  border-radius: var(--radius);
  padding: 10px 12px;
  background: var(--danger-100);
  color: var(--danger-text);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  animation: bannerFlash 0.35s ease;
}

.message-row {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.row-user {
  flex-direction: row-reverse;
}

.avatar-wrap {
  flex-shrink: 0;
}

.mail-avatar {
  background: var(--warm);
  color: var(--primary);
}

.message-body {
  max-width: 70%;
}

.row-user .message-body {
  display: flex;
  justify-content: flex-end;
}

.bubble {
  border-radius: var(--radius);
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.bubble-ai {
  background: linear-gradient(135deg, var(--surface-subtle) 0%, var(--warm) 100%);
  color: var(--text-primary);
}

.ai-message-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.bubble-user {
  background: linear-gradient(135deg, var(--brand-600) 0%, var(--brand-600) 100%);
  color: var(--surface) !important;
  font-weight: 500;
  text-shadow: 0 1px 0 color-mix(in srgb, var(--gray-900) 8%, transparent);
}

.bubble-user span {
  color: var(--surface) !important;
}

.bubble-danger {
  border: 1px solid var(--danger);
  background: var(--danger-100);
  color: var(--danger-text);
}

.kw-mark {
  background: var(--warning-100);
  border-radius: 4px;
  padding: 0 2px;
}

.typing i {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-secondary);
  margin-right: 3px;
  animation: dot 1.2s infinite ease-in-out;
}

.typing i:nth-child(2) {
  animation-delay: 0.15s;
}

.typing i:nth-child(3) {
  animation-delay: 0.3s;
}

.thinking-panel {
  margin: 2px 0 14px;
  border: 1px dashed var(--border);
  background: color-mix(in srgb, var(--brand-500) 78%, transparent);
  border-radius: 10px;
  padding: 10px 12px;
}

.thinking-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--text-primary);
}

.thinking-phase {
  color: var(--text-secondary);
  font-size: 12px;
}

.thinking-lines {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.thinking-line {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

@keyframes dot {
  0%,
  80%,
  100% {
    transform: scale(0.6);
    opacity: 0.6;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes bannerFlash {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 600px) {
  .message-row {
    max-width: 100%;
  }

  .bubble {
    overflow-wrap: anywhere;
  }
}
</style>
