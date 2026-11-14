<template>
  <div class="chat-page business-page">
    <aside class="session-panel">
      <div class="session-toolbar">
        <el-button type="primary" plain class="new-conv-btn" @click="createNewChat(currentMode)"
          ><LibraryIcon name="add" /> 新对话</el-button
        >
      </div>
      <div class="session-search">
        <el-input v-model="searchQuery" placeholder="搜索聊天记录..." />
      </div>
      <div class="session-list" v-loading="loadingSessions">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          :class="['session-item', currentSessionId === session.id ? 'active' : '']"
          role="button"
          tabindex="0"
          :aria-current="currentSessionId === session.id ? 'true' : undefined"
          @click="loadSession(session.id)"
          @keydown.enter.stop.prevent="loadSession(session.id)"
          @keydown.space.stop.prevent="loadSession(session.id)"
        >
          <div class="session-top">
            <span
              class="session-mode-dot"
              :class="session.mode === 'daily' ? 'dot-daily' : 'dot-counsel'"
            />
            <span class="session-name">{{ session.title }}</span>
            <span v-if="session.archived" class="session-archived">已归档</span>
            <span class="session-time">{{ formatSessionTime(session.updated_at) }}</span>
            <el-dropdown @command="(cmd) => handleSessionCommand(cmd, session)">
              <span class="session-more" @click.stop>•••</span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div class="session-preview">
            {{ session.mode === 'daily' ? '日常聊天会话' : '心理咨询会话' }}
          </div>
        </div>
      </div>
    </aside>

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
        <div class="messages-area" ref="chatScrollRef">
          <div v-if="crisisBannerVisible" class="crisis-banner">
            <el-icon><LibraryIcon name="alert" /></el-icon>
            <strong>高危预警</strong>
            <span
              >检测到需要关注的求助信息。系统无法确认人工服务是否已接收，请优先联系实际人工支持。</span
            >
          </div>

          <template v-for="(msg, index) in chatHistory" :key="index">
            <div :class="['message-row', msg.role === 'user' ? 'row-user' : 'row-ai']">
              <div class="avatar-wrap">
                <el-avatar
                  v-if="msg.role === 'user'"
                  :size="36"
                  :src="isAnonymous ? anonymousAvatar : userAvatar"
                />
                <el-avatar v-else :size="36" class="mail-avatar">
                  <el-icon><LibraryIcon name="chat" /></el-icon>
                </el-avatar>
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
                <span class="thinking-phase">{{
                  phaseLabelMap[thinkingPhase] || '准备中...'
                }}</span>
              </div>
              <div class="thinking-lines">
                <div
                  v-for="(line, idx) in thinkingLogs"
                  :key="`thinking-${idx}`"
                  class="thinking-line"
                >
                  {{ line }}
                </div>
              </div>
            </div>
          </template>

          <div v-if="isTyping && !isDeepStreaming" class="message-row row-ai">
            <div class="avatar-wrap">
              <el-avatar :size="36" class="mail-avatar">
                <el-icon><LibraryIcon name="chat" /></el-icon>
              </el-avatar>
            </div>
            <div class="message-body">
              <div class="bubble bubble-ai typing">
                <span v-if="instantFeedback">{{ instantFeedback }}</span>
                <template v-else><i></i><i></i><i></i></template>
              </div>
            </div>
          </div>
        </div>

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

import { ref, nextTick, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  ElButton,
  ElInput,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElSwitch,
  ElIcon,
  ElAvatar,
  vLoading,
} from 'element-plus'
import axios from 'axios'
import RiskFactorFiveDimension from '../../components/RiskFactorFiveDimension.vue'
import ChatComposer from './chat/ChatComposer.vue'
import { sleep, withApiRetry } from '@/services/advancedChatRetry'
import {
  createTimeoutController,
  parseSsePacket,
  safeParseJson,
} from '@/services/advancedChatStream'
import { createChatStorage } from '@/services/chatIndexedDb'
import { createPrivateChatSession, storedSessionToken } from '@/services/privateChatSession'
import { useChatSessions } from '@/composables/useChatSessions'

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
let wsReconnectTimer = null

const inputText = ref('')
const isTyping = ref(false)
const isAnonymous = ref(false)
const instantFeedback = ref('')
const langStatus = ref(null)
const deepThinkEnabled = ref(false)
const DEEP_THINK_STORAGE_KEY = 'advanced_ai_deep_think_enabled'
const DEEP_THINK_WELCOME_KEY = 'advanced_ai_deep_think_welcome_shown'
const NORMAL_REPLY_AVG_KEY = 'advanced_ai_normal_reply_avg_chars'
const NORMAL_REPLY_COUNT_KEY = 'advanced_ai_normal_reply_count'
const normalReplyAvgChars = ref(0)
const normalReplyCount = ref(0)
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
const searchQuery = ref('')
const currentSessionId = ref(null)
const currentMode = ref('daily')

const chatHistory = ref([])
const chatScrollRef = ref(null)
const crisisBannerVisible = ref(false)
let crisisBannerTimer = null

const filteredSessions = computed(() => {
  const base = sessions.value.filter((s) => !s.archived)
  if (!searchQuery.value) return base
  return base.filter((s) => s.title.includes(searchQuery.value))
})

const ws = ref(null)

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

const initWebSocket = () => {
  const token = getStoredToken()
  if (!token || !chatSession.isActive()) return
  const wsUrl = new URL(axios.getUri({ url: '/api/ws' }), window.location.href)
  wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  ws.value = new WebSocket(wsUrl.href, ['access_token', token])
  ws.value.onopen = () => {
    console.log('Student WS connected')
  }
  ws.value.onmessage = (event) => {
    if (!chatSession.isActive()) return
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'warning_processed') {
        ElMessage.success({
          message: msg.data.message || '老师已收到您的预警信息，正在处理中，请保持通讯畅通。',
          duration: 10000,
          showClose: true,
        })
      }
    } catch (e) {
      if (!chatSession.isActive()) return
    }
  }
  ws.value.onclose = (event) => {
    if (chatSession.isActive() && event.code !== 1008)
      wsReconnectTimer = setTimeout(initWebSocket, 5000)
  }
}

onMounted(async () => {
  try {
    deepThinkEnabled.value = localStorage.getItem(DEEP_THINK_STORAGE_KEY) === '1'
    normalReplyAvgChars.value = Number(localStorage.getItem(NORMAL_REPLY_AVG_KEY) || '0')
    normalReplyCount.value = Number(localStorage.getItem(NORMAL_REPLY_COUNT_KEY) || '0')
  } catch {
    if (!chatSession.isActive()) return
    deepThinkEnabled.value = false
    normalReplyAvgChars.value = 0
    normalReplyCount.value = 0
  }
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
  clearTimeout(wsReconnectTimer)
  if (crisisBannerTimer) clearTimeout(crisisBannerTimer)
  if (ws.value) ws.value.close()
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

const formatSessionTime = (time) => {
  if (!time) return '--:--'
  const d = new Date(time)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

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
      try {
        localStorage.setItem(NORMAL_REPLY_AVG_KEY, String(normalReplyAvgChars.value))
        localStorage.setItem(NORMAL_REPLY_COUNT_KEY, String(normalReplyCount.value))
      } catch {
        if (!chatSession.isActive()) return
        // 本地存储不可用时仅忽略，不影响主流程
      }
    }

    langStatus.value = { language: data.language, confidence: data.confidence }
    chatHistory.value[chatHistory.value.length - 1].heatmap = data.attention_heatmap || []
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

const toggleDeepThink = () => {
  const next = !deepThinkEnabled.value
  try {
    localStorage.setItem(DEEP_THINK_STORAGE_KEY, next ? '1' : '0')
    deepThinkEnabled.value = next
    if (next && localStorage.getItem(DEEP_THINK_WELCOME_KEY) !== '1') {
      ElMessageBox.alert('已开启深度思考，回复将更长、更系统。', '深度思考模式', {
        confirmButtonText: '我知道了',
      })
      localStorage.setItem(DEEP_THINK_WELCOME_KEY, '1')
    }
    ElMessage.success(next ? '已开启深度思考模式' : '已关闭深度思考模式')
  } catch {
    if (!chatSession.isActive()) return
    ElMessage.error('无法保存深度思考设置，请检查浏览器存储权限')
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

.session-panel {
  width: 280px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
}

.session-search {
  padding: 14px;
}

.session-toolbar {
  padding: 12px 14px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.new-conv-btn {
  width: 110px;
}

.session-search :deep(.el-input__wrapper) {
  border-radius: var(--radius);
  box-shadow: none;
  border: 1px solid var(--border);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 10px;
}

.session-item {
  padding: 16px 12px;
  border-radius: var(--radius);
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.session-item:hover {
  background: var(--surface-subtle);
}
.session-item:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 2px;
}

.session-item.active {
  background: var(--brand-50);
}

.session-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-archived {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-subtle);
  border-radius: 999px;
  padding: 1px 6px;
}

.session-more {
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  padding: 0 4px;
}

.session-mode-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-daily {
  background: var(--primary);
}

.dot-counsel {
  background: var(--success-text);
}

.session-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.session-preview {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
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

.analysis-panel {
  width: 340px;
  border-left: 1px solid var(--border);
  background: var(--surface-warm);
  padding: 16px;
  overflow-y: auto;
}

.panel-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 14px;
}

.panel-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.panel-title-row h4 {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary);
}

.panel-hint {
  font-size: 12px;
  color: var(--text-secondary);
}

.radar-box {
  height: 220px;
}

.risk-result {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
}

.risk-low {
  color: var(--success-text);
}

.risk-mid {
  color: var(--warning-text);
}

.risk-high {
  color: var(--danger);
}

.mt-16 {
  margin-top: 16px;
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

  .session-panel {
    width: 100%;
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
  .session-panel {
    max-height: 240px;
    min-height: 0;
  }
  .session-list {
    max-height: 130px;
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
  .message-row {
    max-width: 100%;
  }
  .bubble {
    overflow-wrap: anywhere;
  }
}
</style>
