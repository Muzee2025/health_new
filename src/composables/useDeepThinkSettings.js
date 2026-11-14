import { ref } from 'vue'

const DEEP_THINK_STORAGE_KEY = 'advanced_ai_deep_think_enabled'
const DEEP_THINK_WELCOME_KEY = 'advanced_ai_deep_think_welcome_shown'
const NORMAL_REPLY_AVG_KEY = 'advanced_ai_normal_reply_avg_chars'
const NORMAL_REPLY_COUNT_KEY = 'advanced_ai_normal_reply_count'

export function useDeepThinkSettings({
  chatSession,
  ElMessage,
  ElMessageBox,
  storage = {
    getItem: (key) => globalThis.localStorage.getItem(key),
    setItem: (key, value) => globalThis.localStorage.setItem(key, value),
  },
}) {
  const deepThinkEnabled = ref(false)
  const normalReplyAvgChars = ref(0)
  const normalReplyCount = ref(0)

  const loadSettings = () => {
    try {
      deepThinkEnabled.value = storage.getItem(DEEP_THINK_STORAGE_KEY) === '1'
      normalReplyAvgChars.value = Number(storage.getItem(NORMAL_REPLY_AVG_KEY) || '0')
      normalReplyCount.value = Number(storage.getItem(NORMAL_REPLY_COUNT_KEY) || '0')
      return true
    } catch {
      if (!chatSession.isActive()) return false
      deepThinkEnabled.value = false
      normalReplyAvgChars.value = 0
      normalReplyCount.value = 0
      return true
    }
  }

  const toggleDeepThink = () => {
    const next = !deepThinkEnabled.value
    try {
      storage.setItem(DEEP_THINK_STORAGE_KEY, next ? '1' : '0')
      deepThinkEnabled.value = next
      if (next && storage.getItem(DEEP_THINK_WELCOME_KEY) !== '1') {
        ElMessageBox.alert('已开启深度思考，回复将更长、更系统。', '深度思考模式', {
          confirmButtonText: '我知道了',
        })
        storage.setItem(DEEP_THINK_WELCOME_KEY, '1')
      }
      ElMessage.success(next ? '已开启深度思考模式' : '已关闭深度思考模式')
    } catch {
      if (!chatSession.isActive()) return
      ElMessage.error('无法保存深度思考设置，请检查浏览器存储权限')
    }
  }

  const persistNormalReplyStats = () => {
    try {
      storage.setItem(NORMAL_REPLY_AVG_KEY, String(normalReplyAvgChars.value))
      storage.setItem(NORMAL_REPLY_COUNT_KEY, String(normalReplyCount.value))
      return true
    } catch {
      // Storage is optional; a live chat continues if browser storage is unavailable.
      return chatSession.isActive()
    }
  }

  return {
    deepThinkEnabled,
    normalReplyAvgChars,
    normalReplyCount,
    loadSettings,
    toggleDeepThink,
    persistNormalReplyStats,
  }
}
