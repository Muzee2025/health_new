<template>
  <el-card class="ai-interpret-card">
    <template #header>
      <div class="card-header">
        <span>AI辅助说明</span>
        <div class="actions">
          <el-button size="small" class="action-btn" :disabled="!hasContent" @click="copyText"
            >复制说明</el-button
          >
          <el-button size="small" class="action-btn" :disabled="!hasContent" @click="speakText">{{
            speaking ? '停止朗读' : '语音朗读'
          }}</el-button>
        </div>
      </div>
    </template>
    <p v-if="status === 'loading'" class="state-text" role="status">正在整理说明…</p>
    <p v-else-if="status === 'error'" class="state-text error-text" role="alert">
      {{ errorMessage || '说明暂时无法获取，请稍后重试。' }}
    </p>
    <p v-else-if="!hasContent" class="state-text">{{ emptyMessage }}</p>
    <template v-else>
      <p v-if="content.summary" class="interpret-text">{{ content.summary }}</p>
      <section v-if="content.observations?.length">
        <h4>观察内容</h4>
        <ul>
          <li v-for="(item, i) in content.observations" :key="`o-${i}`">{{ item }}</li>
        </ul>
      </section>
      <section v-if="content.next_steps?.length">
        <h4>可以考虑</h4>
        <ul>
          <li v-for="(item, i) in content.next_steps" :key="`n-${i}`">{{ item }}</li>
        </ul>
      </section>
      <section v-if="content.limitations?.length">
        <h4>说明与局限</h4>
        <ul>
          <li v-for="(item, i) in content.limitations" :key="`l-${i}`">{{ item }}</li>
        </ul>
      </section>
      <p v-if="status !== 'idle'" class="source-note">
        {{ statusLabel }}<template v-if="modelId"> · {{ modelId }}</template>
      </p>
    </template>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage, ElCard, ElButton } from 'element-plus'

const props = defineProps({
  text: { type: [String, Object], default: '' },
  status: { type: String, default: 'idle' },
  source: { type: String, default: '' },
  modelId: { type: String, default: '' },
  language: { type: String, default: 'zh-CN' },
  errorMessage: { type: String, default: '' },
  emptyMessage: { type: String, default: '提交内容后，这里会显示可用的说明。' },
})
const speaking = ref(false)
const content = computed(() => {
  if (typeof props.text === 'string')
    return { summary: props.text.trim(), observations: [], next_steps: [], limitations: [] }
  const value = props.text?.content || props.text || {}
  return {
    summary: typeof value.summary === 'string' ? value.summary.trim() : '',
    observations: Array.isArray(value.observations)
      ? value.observations.filter((item) => typeof item === 'string' && item.trim())
      : [],
    next_steps: Array.isArray(value.next_steps)
      ? value.next_steps.filter((item) => typeof item === 'string' && item.trim())
      : [],
    limitations: Array.isArray(value.limitations)
      ? value.limitations.filter((item) => typeof item === 'string' && item.trim())
      : [],
  }
})
const hasContent = computed(() =>
  Boolean(
    content.value.summary ||
    content.value.observations.length ||
    content.value.next_steps.length ||
    content.value.limitations.length,
  ),
)
const statusLabel = computed(() => {
  const status =
    { completed: '已生成', fallback: '本地说明', insufficient: '资料不足' }[props.status] || '说明'
  const source = { local_rules: '本地规则', provider: '模型服务' }[props.source]
  return [status, source].filter(Boolean).join(' · ')
})
const displayText = computed(() =>
  [
    content.value.summary,
    ...content.value.observations,
    ...content.value.next_steps,
    ...content.value.limitations,
  ]
    .filter(Boolean)
    .join('\n'),
)

const copyText = async () => {
  if (!hasContent.value) return
  try {
    await navigator.clipboard.writeText(displayText.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择说明内容')
  }
}
const speakText = () => {
  if (!('speechSynthesis' in window)) {
    ElMessage.warning('当前浏览器不支持语音朗读')
    return
  }
  if (speaking.value) {
    window.speechSynthesis.cancel()
    speaking.value = false
    return
  }
  const utterance = new SpeechSynthesisUtterance(displayText.value)
  utterance.lang = props.language || 'zh-CN'
  utterance.onend = () => {
    speaking.value = false
  }
  utterance.onerror = () => {
    speaking.value = false
    ElMessage.error('朗读失败')
  }
  speaking.value = true
  window.speechSynthesis.speak(utterance)
}
onBeforeUnmount(() => {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
})
</script>

<style scoped>
.ai-interpret-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px 0 color-mix(in srgb, var(--gray-900) 8%, transparent);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
.action-btn {
  transition: transform 200ms ease;
}
.action-btn:hover {
  transform: scale(1.02);
}
.interpret-text,
.state-text {
  line-height: 1.65;
  margin: 0;
  white-space: pre-wrap;
}
.error-text {
  color: var(--danger-text);
}
.ai-interpret-card h4 {
  margin: 18px 0 6px;
  font-size: 14px;
}
.ai-interpret-card ul {
  margin: 0;
  padding-left: 22px;
}
.ai-interpret-card li {
  line-height: 1.65;
  margin: 4px 0;
}
.source-note {
  margin: 16px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
