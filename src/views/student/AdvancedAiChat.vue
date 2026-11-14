<template>
  <div class="chat-page business-page">
    <ChatSessionSidebar
      :sessions="sessions"
      :current-session-id="currentSessionId"
      :loading-sessions="loadingSessions"
      :current-mode="currentMode"
      @create="createNewChat"
      @select="loadSession"
      @rename="handleSessionCommand('rename', $event)"
      @delete="handleSessionCommand('delete', $event)"
    />

    <section class="chat-main-wrap">
      <header class="chat-top-bar">
        <div class="mode-actions">
          <button
            class="mode-pill"
            type="button"
            :class="{ active: currentMode === 'daily' }"
            :aria-pressed="currentMode === 'daily'"
            @click="createNewChat('daily')"
          >
            新日常聊天
          </button>
          <button
            class="mode-pill"
            type="button"
            :class="{ active: currentMode === 'counseling' }"
            :aria-pressed="currentMode === 'counseling'"
            @click="createNewChat('counseling')"
          >
            新心理咨询
          </button>
          <router-link to="/student/questions" class="mode-pill support-link"
            >向老师留言</router-link
          >
          <span v-if="langStatus" class="voice-tag"
            >语言 {{ langStatus.language }} · {{ Math.round(langStatus.confidence * 100) }}%</span
          >
        </div>
        <div class="anon-switch">
          <span>实名</span>
          <el-switch v-model="isAnonymous" />
          <span>{{ isAnonymous ? '匿名（不保存）' : '匿名' }}</span>
        </div>
      </header>

      <div class="chat-content">
        <ChatMessageList
          ref="messageListRef"
          :messages="chatHistory"
          :is-anonymous="isAnonymous"
          :user-avatar="userAvatar"
          :anonymous-avatar="anonymousAvatar"
          :crisis-banner-visible="crisisBannerVisible"
          :is-deep-streaming="isDeepStreaming"
          :thinking-logs="thinkingLogs"
          :thinking-anchor-message-id="thinkingAnchorMessageId"
          :thinking-phase="thinkingPhase"
          :phase-label-map="phaseLabelMap"
          :is-typing="isTyping"
          :instant-feedback="instantFeedback"
          :is-danger-text="isDangerText"
        />
        <aside class="analysis-panel">
          <RiskFactorFiveDimension />
        </aside>
      </div>

      <ChatComposer
        v-model="inputText"
        :is-anonymous="isAnonymous"
        :current-session-id="currentSessionId"
        :is-typing="isTyping"
        :deep-think-enabled="deepThinkEnabled"
        :last-reply-chars="lastReplyChars"
        :last-reply-ratio="lastReplyRatio"
        @send="sendMessage"
        @toggle-deep="toggleDeepThink"
      />
    </section>
  </div>
</template>

<script setup>
import { getVisualAsset } from '../../design/asset-registry'
const userAvatar = getVisualAsset('studentAvatar').url
const anonymousAvatar = getVisualAsset('anonymousAvatar').url

import { ref, nextTick, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { ElMessage, ElMessageBox, ElSwitch } from 'element-plus'
import axios from 'axios'
import RiskFactorFiveDimension from '../../components/RiskFactorFiveDimension.vue'
import ChatComposer from './chat/ChatComposer.vue'
import ChatSessionSidebar from './chat/ChatSessionSidebar.vue'
import ChatMessageList from './chat/ChatMessageList.vue'
import { sleep, withApiRetry } from '@/services/advancedChatRetry'
import {
  createTimeoutController,
  parseSsePacket,
  safeParseJson,
} from '@/services/advancedChatStream'
import { createChatStorage } from '@/services/chatIndexedDb'
import { createPrivateChatSession, storedSessionToken } from '@/services/privateChatSession'
import { useChatWebSocket } from '@/composables/useChatWebSocket'
import { useChatSessions } from '@/composables/useChatSessions'
import { useDeepThinkSettings } from '@/composables/useDeepThinkSettings'

const sessionAbort = new AbortController()
const chatSession = createPrivateChatSession(
  storedSessionToken(),
  storedSessionToken,
  sessionAbort.signal,
)
const chatStorage = createChatStorage(chatSession)
const { putMessage, upsertConversation } = chatStorage
const sessionRequest = (method, url, data, config = {}) =>
  chatSession.run(() =>
    axios.request({ ...config, method, url, data, signal: sessionAbort.signal }),
  )
const sessionHttp = {
  get: (url, config) => sessionRequest('get', url, undefined, config),
  post: (url, data, config) => sessionRequest('post', url, data, config),
  patch: (url, data, config) => sessionRequest('patch', url, data, config),
  delete: (url, config) => sessionRequest('delete', url, undefined, config),
}
const inputText = ref('')
const isTyping = ref(false)
const isAnonymous = ref(false)
const instantFeedback = ref('')
const langStatus = ref(null)
const lastReplyChars = ref(0)
const lastReplyRatio = ref(1)
const isDeepStreaming = ref(false)
const thinkingPhase = ref('')
const thinkingLogs = ref([])
const thinkingAnchorMessageId = ref('')
const phaseLabelMap = {
  memory: '正在回溯记忆',
  trend: '正在纵向洞察',
  response: '正在生成回应',
}

const sessions = ref([])
const loadingSessions = ref(false)
const currentSessionId = ref(null)
const currentMode = ref('daily')

const chatHistory = ref([])
const messageListRef = ref(null)
const chatScrollRef = computed(() => messageListRef.value?.scrollElement ?? null)
const crisisBannerVisible = ref(false)
let crisisBannerTimer = null

const {
  syncSessionsFromServer,
  loadSessionsFromLocal,
  persistUiState,
  createNewChat,
  loadSession,
  renameSession,
  deleteSession,
} = useChatSessions({
  chatSession,
  sessionHttp,
  storage: chatStorage,
  state: {
    sessions,
    loadingSessions,
    currentSessionId,
    currentMode,
    chatHistory,
    inputText,
    isAnonymous,
    chatScrollRef,
    crisisBannerVisible,
  },
  withApiRetry,
  sleep,
  ElMessage,
  ElMessageBox,
})

const {
  deepThinkEnabled,
  normalReplyAvgChars,
  normalReplyCount,
  loadSettings: loadDeepThinkSettings,
  toggleDeepThink,
  persistNormalReplyStats,
} = useDeepThinkSettings({ chatSession, ElMessage, ElMessageBox })

onMounted(async () => {
  if (!loadDeepThinkSettings()) return
  await loadSessionsFromLocal()
  if (!chatSession.isActive()) return
  await syncSessionsFromServer()
  if (!chatSession.isActive()) return
  if (sessions.value.length > 0) await loadSession(sessions.value[0].id)
  else await createNewChat('daily')
  if (!chatSession.isActive()) return
  initWebSocket()
})

onBeforeUnmount(() => {
  sessionAbort.abort()
  if (crisisBannerTimer) clearTimeout(crisisBannerTimer)
  closeWebSocket()
})

watch(isAnonymous, async (val) => {
  if (val) {
    // 匿名模式：仅保留当前内存对话，不做任何持久化。
    chatHistory.value = []
    crisisBannerVisible.value = false
    inputText.value = ''
    await scrollToBottom()
    ElMessage.info('已进入匿名模式：聊天记录不会保存，刷新后自动清空。')
    return
  }
  ElMessage.success('已切回实名模式：聊天记录将正常保存。')
  // The anonymous draft must not survive the switch: it was typed under the
  // "not saved" promise, and the next loadSession would otherwise store it.
  inputText.value = ''
  if (sessions.value.length > 0) {
    await loadSession(sessions.value[0].id)
  } else {
    await createNewChat(currentMode.value || 'daily')
  }
})

const uuid = () =>
  globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`

const getStoredToken = () => {
  const raw = localStorage.getItem('token') || localStorage.getItem('access_token') || ''
  const token = String(raw).trim()
  if (!token) return ''
  return token.toLowerCase().startsWith('bearer ') ? token.slice(7).trim() : token
}

const { connect: initWebSocket, close: closeWebSocket } = useChatWebSocket({
  chatSession,
  getStoredToken,
  axios,
  ElMessage,
})

const resetThinkingPanel = () => {
  thinkingPhase.value = ''
  thinkingLogs.value = []
}

const appendThinkingLine = (text) => {
  const line = String(text || '').trim()
  if (!line) return
  thinkingLogs.value.push(line)
}

const streamDeepThinkReply = async (payload, aiLocal) => {
  const token = getStoredToken()
  chatSession.assertActive()
  const { controller, timer } = createTimeoutController(70000)
  const abortStream = () => controller.abort()
  sessionAbort.signal.addEventListener('abort', abortStream, { once: true })
  try {
    const res = await fetch(axios.getUri({ url: '/api/advanced-ai/chat/stream' }), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal: controller.signal,
      body: JSON.stringify(payload),
    })
    if (!res.ok || !res.body) {
      throw new Error(`流式接口调用失败(${res.status})`)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let finalPayload = null

    while (true) {
      const { done, value } = await reader.read()
      chatSession.assertActive()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const packets = buffer.split('\n\n')
      buffer = packets.pop() || ''
      for (const packet of packets) {
        if (!packet.trim()) continue
        const { event, data } = parseSsePacket(packet)
        if (event === 'phase') {
          thinkingPhase.value = data
        } else if (event === 'memory_chunk' || event === 'trend_chunk') {
          const parsed = safeParseJson(data, () => chatSession.isActive())
          appendThinkingLine(parsed?.text || data)
        } else if (event === 'message_chunk') {
          const parsed = safeParseJson(data, () => chatSession.isActive())
          aiLocal.content += parsed?.text || ''
        } else if (event === 'done') {
          finalPayload = safeParseJson(data, () => chatSession.isActive()) || null
        } else if (event === 'error') {
          const parsed = safeParseJson(data, () => chatSession.isActive())
          throw new Error(parsed?.text || '流式处理失败')
        }
      }
      await scrollToBottom()
    }
    if (!finalPayload || !finalPayload.reply) {
      throw new Error('流式响应未返回最终内容')
    }
    return finalPayload
  } finally {
    clearTimeout(timer)
    sessionAbort.signal.removeEventListener('abort', abortStream)
  }
}

const sendMessage = async () => {
  if (!chatSession.isActive()) return
  if (!inputText.value.trim() || isTyping.value || (!isAnonymous.value && !currentSessionId.value))
    return
  const userMsg = inputText.value.trim()
  inputText.value = ''
  // Pin the conversation this message belongs to. Everything below used to read
  // currentSessionId at the moment the reply arrived, so switching chats while
  // a reply was streaming stored it in the session the user had just opened.
  const requestSessionId = currentSessionId.value
  const requestAnonymous = Boolean(isAnonymous.value)
  const requestMode = currentMode.value
  const userLocal = {
    id: uuid(),
    role: 'user',
    content: userMsg,
    heatmap: [],
    created_at: new Date().toISOString(),
  }
  chatHistory.value.push(userLocal)
  if (!requestAnonymous) {
    await putMessage({
      id: userLocal.id,
      conversationId: requestSessionId,
      role: 'user',
      content: userMsg,
      model: 'user',
      timestamp: userLocal.created_at,
    })
  }
  await scrollToBottom()

  isTyping.value = true
  instantFeedback.value = '消息已接收并分析中...'
  setTimeout(() => {
    if (isTyping.value) instantFeedback.value = ''
  }, 2000)

  const buildPayload = (useDeepThink) => ({
    session_id: requestSessionId,
    message: userMsg,
    modality: 'text',
    anonymous: requestAnonymous,
    mode: requestMode,
    deep_think: Boolean(useDeepThink),
    history: chatHistory.value
      .filter((m) => m.role === 'user' || m.role === 'ai')
      .map((m) => ({ role: m.role, content: m.content })),
  })

  const deepRequested = deepThinkEnabled.value
  let data = null
  let deepActuallyUsed = deepRequested
  let streamAiLocal = null
  try {
    if (deepRequested) {
      isDeepStreaming.value = true
      resetThinkingPanel()
      thinkingAnchorMessageId.value = userLocal.id
      thinkingPhase.value = 'memory'
      appendThinkingLine('正在连接深层记忆网络...')
      streamAiLocal = {
        id: uuid(),
        role: 'ai',
        content: '',
        is_crisis: false,
        emotion_tags: null,
        created_at: new Date().toISOString(),
      }
      chatHistory.value.push(streamAiLocal)
      await scrollToBottom()
      data = await streamDeepThinkReply(buildPayload(true), streamAiLocal)
      streamAiLocal.content = data.reply || streamAiLocal.content
    } else {
      data = (await sessionHttp.post('/api/advanced-ai/chat', buildPayload(false))).data
    }
  } catch (error) {
    if (!chatSession.isActive()) return
    if (streamAiLocal) {
      const idx = chatHistory.value.findIndex((x) => x.id === streamAiLocal.id)
      if (idx >= 0) chatHistory.value.splice(idx, 1)
    }
    resetThinkingPanel()
    thinkingAnchorMessageId.value = ''
    if (deepRequested) {
      const detail = error?.response?.data?.detail || error?.message
      let msg = typeof detail === 'string' ? detail : '深度思考请求失败'
      if (
        String(error?.name || '').includes('Abort') ||
        String(detail || '').includes('timeout:70000')
      ) {
        msg = '深度思考超时，请稍后重试'
      }
      ElMessage.error(msg)
    } else {
      const detail = error?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : '服务器响应失败，请重试'
      ElMessage.error(msg)
    }
  }

  try {
    if (!data || !chatSession.isActive()) return
    const currentReply = data.reply || ''
    const currentChars = currentReply.replace(/\s+/g, '').length
    lastReplyChars.value = currentChars

    const baseAvg =
      normalReplyAvgChars.value > 0 ? normalReplyAvgChars.value : Math.max(currentChars, 1)
    lastReplyRatio.value = Math.max(currentChars / baseAvg, 1)

    if (!deepActuallyUsed) {
      const total = normalReplyAvgChars.value * normalReplyCount.value + currentChars
      normalReplyCount.value += 1
      normalReplyAvgChars.value = total / Math.max(normalReplyCount.value, 1)
      if (!persistNormalReplyStats()) return
    }

    langStatus.value = { language: data.language, confidence: data.confidence }
    const aiLocal = streamAiLocal || {
      id: uuid(),
      role: 'ai',
      content: data.reply,
      is_crisis: data.is_crisis,
      emotion_tags: data.emotion_tags || null,
      created_at: new Date().toISOString(),
    }
    if (!streamAiLocal) {
      chatHistory.value.push(aiLocal)
    } else {
      aiLocal.content = data.reply || aiLocal.content
      aiLocal.is_crisis = Boolean(data.is_crisis)
      aiLocal.emotion_tags = data.emotion_tags || null
    }
    if (!requestAnonymous) {
      await putMessage({
        id: aiLocal.id,
        conversationId: requestSessionId,
        role: 'ai',
        content: data.reply,
        model: 'emohaa',
        emotion_tags: data.emotion_tags || null,
        is_crisis: Boolean(data.is_crisis),
        timestamp: aiLocal.created_at,
      })
      await upsertConversation({
        id: requestSessionId,
        title:
          sessions.value.find((x) => x.id === requestSessionId)?.title ||
          userMsg.slice(0, 15) ||
          '新对话',
        mode: requestMode,
        createdAt:
          sessions.value.find((x) => x.id === requestSessionId)?.createdAt ||
          new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        archived: Boolean(sessions.value.find((x) => x.id === requestSessionId)?.archived),
      })
    }
    if (data.is_crisis) {
      triggerCrisisBanner()
      ElMessage.warning({
        message:
          data.warning_state === 'created'
            ? '需关注的提示已记录；尚不代表教师已查看或处理，请优先寻求实际人工支持。'
            : '检测到需关注的信息，尚未确认预警已保存，请优先联系实际人工支持。',
        duration: 7000,
      })
    }
    if (!requestAnonymous) {
      window.dispatchEvent(
        new CustomEvent('assistant-message-saved', {
          detail: { sessionId: requestSessionId, ts: Date.now() },
        }),
      )
      await loadSessionsFromLocal()
    }
  } finally {
    isDeepStreaming.value = false
    if (!data || !deepActuallyUsed) {
      resetThinkingPanel()
      thinkingAnchorMessageId.value = ''
    }
    isTyping.value = false
    instantFeedback.value = ''
    await scrollToBottom()
    if (!isAnonymous.value && chatSession.isActive()) {
      await persistUiState()
    }
  }
}

const handleSessionCommand = async (cmd, session) => {
  try {
    if (cmd === 'rename') await renameSession(session)
    if (cmd === 'delete') await deleteSession(session)
  } catch {
    if (!chatSession.isActive()) return
    // 用户取消
  }
}

const triggerCrisisBanner = () => {
  crisisBannerVisible.value = true
  if (crisisBannerTimer) clearTimeout(crisisBannerTimer)
  crisisBannerTimer = setTimeout(() => {
    crisisBannerVisible.value = false
  }, 10000)
}

const isDangerText = (text) => /跳楼|自杀|轻生|不想活|结束生命/.test(text || '')

const scrollToBottom = async () => {
  if (messageListRef.value?.scrollToBottom) {
    await messageListRef.value.scrollToBottom()
    return
  }
  await nextTick()
  if (chatScrollRef.value) {
    chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-page {
  --primary: var(--brand-600);
  --warm: var(--warning-100);
  --mint: var(--accent-sage-soft);
  --danger: var(--danger-text);
  --bg: var(--surface-warm);
  --card: var(--surface);
  --radius: 12px;
  --shadow: 0 2px 8px color-mix(in srgb, var(--gray-900) 6%, transparent);
}

.chat-page {
  display: flex;
  gap: 16px;
  height: calc(100vh - 120px);
  background: var(--bg);
}
.chat-page.business-page {
  width: 100%;
  max-width: none;
  margin: 0;
}

.chat-main-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  background: var(--card);
  overflow: hidden;
}

.chat-top-bar {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mode-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mode-pill {
  border: none;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  background: var(--surface-subtle);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-pill.active {
  background: var(--primary);
  color: var(--surface);
}
.support-link {
  display: inline-flex;
  align-items: center;
  color: var(--brand-700);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.voice-tag {
  border-radius: 999px;
  background: var(--surface-subtle);
  color: var(--text-secondary);
  padding: 5px 10px;
  font-size: 12px;
}

.anon-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.chat-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.analysis-panel {
  width: 340px;
  border-left: 1px solid var(--border);
  background: var(--surface-warm);
  padding: 16px;
  overflow-y: auto;
}

@media (max-width: 1200px) {
  .analysis-panel {
    width: 300px;
  }
}

@media (max-width: 980px) {
  .chat-page {
    flex-direction: column;
    height: auto;
  }

  .chat-content {
    flex-direction: column;
  }

  .analysis-panel {
    width: 100%;
    border-left: none;
    border-top: 1px solid var(--border);
  }
}
@media (max-width: 600px) {
  .chat-page {
    gap: 10px;
  }
  .chat-top-bar {
    align-items: stretch;
    flex-direction: column;
    gap: 10px;
  }
  .mode-actions {
    flex-wrap: wrap;
  }
  .anon-switch {
    justify-content: flex-start;
  }
}
</style>
