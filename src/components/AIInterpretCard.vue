<template>
  <el-card class="ai-interpret-card">
    <template #header>
      <div class="card-header">
        <span>AI 解读</span>
        <div class="actions">
          <el-button size="small" class="action-btn" @click="copyText">一键复制</el-button>
          <el-button size="small" class="action-btn" @click="speakText">{{ speaking ? "停止朗读" : "语音朗读" }}</el-button>
        </div>
      </div>
    </template>
    <p class="interpret-text">{{ displayText }}</p>
  </el-card>
</template>

<script setup>
import { computed, ref, onBeforeUnmount } from "vue"
import { ElMessage } from "element-plus"

const props = defineProps({
  text: { type: String, default: "" },
  language: { type: String, default: "zh-CN" },
})

const speaking = ref(false)

const displayText = computed(() => props.text || "AI 解读生成中，请稍后再试")

const copyText = async () => {
  try {
    await navigator.clipboard.writeText(displayText.value)
    ElMessage.success("已复制到剪贴板")
  } catch (error) {
    ElMessage.error("复制失败，请手动复制")
  }
}

const speakText = () => {
  if (!("speechSynthesis" in window)) {
    ElMessage.warning("当前浏览器不支持语音朗读")
    return
  }
  if (speaking.value) {
    window.speechSynthesis.cancel()
    speaking.value = false
    return
  }
  const utterance = new SpeechSynthesisUtterance(displayText.value)
  utterance.lang = props.language || "zh-CN"
  utterance.rate = 1
  utterance.onend = () => {
    speaking.value = false
  }
  utterance.onerror = () => {
    speaking.value = false
    ElMessage.error("朗读失败")
  }
  speaking.value = true
  window.speechSynthesis.speak(utterance)
}

onBeforeUnmount(() => {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel()
  }
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

.interpret-text {
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
}
</style>
