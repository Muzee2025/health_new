<template>
  <div class="chat-page">
    <aside class="session-panel">
      <div class="session-toolbar">
        <el-button type="primary" plain class="new-conv-btn" @click="createNewChat(currentMode)"><LibraryIcon name="add" /> 新对话</el-button>
      </div>
      <div class="session-search">
        <el-input v-model="searchQuery" placeholder="搜索聊天记录..." />
      </div>
      <div class="session-list" v-loading="loadingSessions">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          :class="['session-item', currentSessionId === session.id ? 'active' : '']"
          @click="loadSession(session.id)"
        >
          <div class="session-top">
            <span class="session-mode-dot" :class="session.mode === 'daily' ? 'dot-daily' : 'dot-counsel'" />
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
          <div class="session-preview">{{ session.mode === 'daily' ? '日常聊天会话' : '心理咨询会话' }}</div>
        </div>
      </div>
    </aside>

    <section class="chat-main-wrap">
      <header class="chat-top-bar">
        <div class="mode-actions">
          <button
            class="mode-pill"
            :class="{ active: currentMode === 'daily' }"
            @click="createNewChat('daily')"
          >
            新日常聊天
          </button>
          <button
            class="mode-pill"
            :class="{ active: currentMode === 'counseling' }"
            @click="createNewChat('counseling')"
          >
            新心理咨询
          </button>
          <router-link to="/student/questions" class="mode-pill support-link">向老师留言</router-link>
          <span v-if="langStatus" class="voice-tag">语言 {{ langStatus.language }} · {{ Math.round(langStatus.confidence * 100) }}%</span>
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
            <el-icon><LibraryIcon name="alert"  /></el-icon>
            <strong>高危预警</strong>
            <span>检测到高风险表达，系统已启动安全干预流程。</span>
          </div>

          <template v-for="(msg, index) in chatHistory" :key="index">
            <div :class="['message-row', msg.role === 'user' ? 'row-user' : 'row-ai']">
              <div class="avatar-wrap">
                <el-avatar v-if="msg.role === 'user'" :size="36" :src="isAnonymous ? anonymousAvatar : userAvatar" />
                <el-avatar v-else :size="36" class="mail-avatar">
                  <el-icon><LibraryIcon name="chat"  /></el-icon>
                </el-avatar>
              </div>

              <div class="message-body">
                <div
                  :class="[
                    'bubble',
                    msg.role === 'user' ? 'bubble-user' : 'bubble-ai',
                    msg.role === 'user' && isDangerText(msg.content) ? 'bubble-danger' : ''
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
              v-if="(isDeepStreaming || thinkingLogs.length) && thinkingAnchorMessageId && msg.id === thinkingAnchorMessageId"
              class="thinking-panel"
            >
              <div class="thinking-title">
                <strong>深度思考草稿</strong>
                <span class="thinking-phase">{{ phaseLabelMap[thinkingPhase] || '准备中...' }}</span>
              </div>
              <div class="thinking-lines">
                <div v-for="(line, idx) in thinkingLogs" :key="`thinking-${idx}`" class="thinking-line">{{ line }}</div>
              </div>
            </div>
          </template>

          <div v-if="isTyping && !isDeepStreaming" class="message-row row-ai">
            <div class="avatar-wrap">
              <el-avatar :size="36" class="mail-avatar">
                <el-icon><LibraryIcon name="chat"  /></el-icon>
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
          <div class="panel-card">
            <div class="panel-title-row">
              <h4>风险因子五维评估</h4>
              <el-button text @click="refreshRiskRadar">重试</el-button>
            </div>
            <div ref="radarRef" class="radar-box"></div>
            <p v-if="latestEmotion" class="risk-result" :class="riskClass">当前风险等级：{{ riskLevelText }}</p><p v-else class="risk-result">暂无会话分析数据</p>
          </div>
        </aside>
      </div>

      <footer class="input-bar">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="在这里输入你想说的话..."
          resize="none"
          :disabled="!isAnonymous && !currentSessionId"
          @keydown.enter.prevent="sendMessage"
        />
        <button
          class="send-btn"
          @click="sendMessage"
          :disabled="!inputText.trim() || ((!isAnonymous && !currentSessionId) || isTyping)"
        >
          发送
        </button>
        <button
          class="deep-think-toggle"
          :class="{ active: deepThinkEnabled }"
          @click="toggleDeepThink"
          :disabled="isTyping"
        >
          {{ deepThinkEnabled ? '深度思考: 开' : '深度思考: 关' }}
        </button>
      </footer>
      <div v-if="lastReplyChars > 0" class="reply-stats">
        本回答共{{ lastReplyChars }}字，约为您平时请求的{{ lastReplyRatio.toFixed(1) }}倍
      </div>
    </section>
  </div>
</template>

<script setup>
import { setLibraryChartOption } from '../../design/chart-registry'
import { getVisualAsset } from '../../design/asset-registry'
const userAvatar = getVisualAsset('studentAvatar').url
const anonymousAvatar = getVisualAsset('anonymousAvatar').url

import { businessAlpha, businessColor } from '../../styles/business-theme.js'
import { ref, nextTick, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { ElMessage, ElMessageBox, ElButton, ElInput, ElDropdown, ElDropdownMenu, ElDropdownItem, ElSwitch, ElIcon, ElAvatar, vLoading } from 'element-plus'
import axios from 'axios'
import * as echarts from '../../design/charts/radar'
import { createChatStorage } from '@/services/chatIndexedDb'
import { createPrivateChatSession, storedSessionToken } from '@/services/privateChatSession'

const sessionAbort = new AbortController()
const chatSession = createPrivateChatSession(storedSessionToken(), storedSessionToken, sessionAbort.signal)
const { deleteConversationLocal, getAllConversations, getUiState, listMessages, putMessage, saveUiState, upsertConversation } = createChatStorage(chatSession)
const sessionRequest = (method, url, data, config = {}) => chatSession.run(() => axios.request({ ...config, method, url, data, signal: sessionAbort.signal }))
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
const latestEmotion = ref(null)
const chatScrollRef = ref(null)
const crisisBannerVisible = ref(false)
let crisisBannerTimer = null

const radarRef = ref(null)
let radarChart = null


const filteredSessions = computed(() => {
  const base = sessions.value.filter((s) => !s.archived)
  if (!searchQuery.value) return base
  return base.filter((s) => s.title.includes(searchQuery.value))
})

const negativeScore = computed(() => {
  if (!latestEmotion.value) return 0
  const e = latestEmotion.value
  return ((e.sadness || 0) + (e.fear || 0) + (e.anger || 0)) / 3
})

const riskLevelText = computed(() => {
  if (negativeScore.value >= 0.75) return '极高'
  if (negativeScore.value >= 0.55) return '较高'
  if (negativeScore.value >= 0.35) return '中等'
  return '较低'
})

const riskClass = computed(() => {
  if (negativeScore.value >= 0.75) return 'risk-high'
  if (negativeScore.value >= 0.55) return 'risk-mid'
  return 'risk-low'
})

const ws = ref(null)

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
          showClose: true
        })
      }
    } catch (e) {
      if (!chatSession.isActive()) return
    }
  }
  ws.value.onclose = (event) => {
    if (chatSession.isActive() && event.code !== 1008) wsReconnectTimer = setTimeout(initWebSocket, 5000)
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
  initRadar()
  window.addEventListener('resize', resizeRadar)
  initWebSocket()
})

onBeforeUnmount(() => {
  sessionAbort.abort()
  clearTimeout(wsReconnectTimer)
  if (radarChart) radarChart.dispose()
  if (crisisBannerTimer) clearTimeout(crisisBannerTimer)
  window.removeEventListener('resize', resizeRadar)
  if (ws.value) ws.value.close()
})

watch(latestEmotion, () => {
  updateTrendAndRadar()
})

watch(isAnonymous, async (val) => {
  if (val) {
    // 匿名模式：仅保留当前内存对话，不做任何持久化。
    chatHistory.value = []
    latestEmotion.value = null
    crisisBannerVisible.value = false
    inputText.value = ''
    await scrollToBottom()
    ElMessage.info('已进入匿名模式：聊天记录不会保存，刷新后自动清空。')
    return
  }
  ElMessage.success('已切回实名模式：聊天记录将正常保存。')
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

const fetchSessions = async () => {
  loadingSessions.value = true
  try {
    const res = await withApiRetry(
      () => sessionHttp.get('/api/advanced-ai/sessions'),
      'fetchSessions',
      3
    )
    const list = res.data.data || []
    const localMap = new Map((await getAllConversations()).map((x) => [x.id, x]))
    const serverIds = new Set(list.map((x) => x.id))
    for (const [localId] of localMap) {
      if (!serverIds.has(localId)) {
        await deleteConversationLocal(localId)
      }
    }
    for (const row of list) {
      const local = localMap.get(row.id)
      await upsertConversation({
        id: row.id,
        title: row.title || '新对话',
        mode: row.mode || 'daily',
        createdAt: local?.createdAt || row.updated_at || new Date().toISOString(),
        updatedAt: row.updated_at || new Date().toISOString(),
        updated_at: row.updated_at || new Date().toISOString(),
        archived: local?.archived || false,
      })
    }
    await loadSessionsFromLocal()
  } finally {
    loadingSessions.value = false
  }
}

const syncSessionsFromServer = async () => {
  try {
    await fetchSessions()
    return true
  } catch (err) {
    if (!chatSession.isActive()) return
    console.warn('[AdvancedAiChat] syncSessionsFromServer failed', {
      status: err?.response?.status || err?.status,
      url: err?.response?.config?.url,
      message: err?.message,
    })
    // 网络波动时保留本地会话可用
    return false
  }
}

const loadSessionsFromLocal = async () => {
  loadingSessions.value = true
  try {
    const rows = await getAllConversations()
    sessions.value = rows
      .map((x) => ({
        id: x.id,
        title: x.title || '新对话',
        mode: x.mode || 'daily',
        createdAt: x.createdAt,
        updated_at: x.updatedAt || x.updated_at || x.createdAt,
        archived: Boolean(x.archived),
      }))
      .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
  } catch {
    if (!chatSession.isActive()) return
    sessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

const persistUiState = async () => {
  if (!chatSession.isActive() || !currentSessionId.value) return
  await saveUiState(currentSessionId.value, {
    draft: inputText.value,
    scrollTop: chatScrollRef.value?.scrollTop || 0,
    updatedAt: new Date().toISOString(),
  })
}

const restoreUiState = async (sessionId) => {
  const state = await getUiState(sessionId)
  chatSession.assertActive()
  inputText.value = state?.draft || ''
  await nextTick()
  if (chatScrollRef.value) {
    if (typeof state?.scrollTop === 'number') chatScrollRef.value.scrollTop = state.scrollTop
    else chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
  }
}

const uuid = () => (globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)

const getStoredToken = () => {
  const raw = localStorage.getItem('token') || localStorage.getItem('access_token') || ''
  const token = String(raw).trim()
  if (!token) return ''
  return token.toLowerCase().startsWith('bearer ') ? token.slice(7).trim() : token
}

const parseSsePacket = (packet) => {
  const lines = packet.split('\n')
  let event = 'message'
  const dataLines = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  return { event, data: dataLines.join('\n') }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const isRetryableHttpError = (err) => {
  const status = err?.response?.status || err?.status || 0
  if (err?.name === 'AbortError' || !chatSession.isActive()) return false
  if (!status) return true
  return status >= 500 || status === 429
}

const withApiRetry = async (fn, label, retries = 2) => {
  let lastErr = null
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (err) {
      if (!chatSession.isActive()) return
      lastErr = err
      if (!isRetryableHttpError(err) || attempt === retries) break
      const waitMs = 400 * (attempt + 1)
      console.warn(`[AdvancedAiChat] ${label} retrying`, {
        attempt: attempt + 1,
        waitMs,
        status: err?.response?.status || err?.status,
        message: err?.message,
      })
      await sleep(waitMs)
    }
  }
  throw lastErr
}

const safeParseJson = (text) => {
  try {
    return JSON.parse(text)
  } catch {
    if (!chatSession.isActive()) return
    return null
  }
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

const createTimeoutController = (ms) => {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new Error(`timeout:${ms}`)), ms)
  return { controller, timer }
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
          const parsed = safeParseJson(data)
          appendThinkingLine(parsed?.text || data)
        } else if (event === 'message_chunk') {
          const parsed = safeParseJson(data)
          aiLocal.content += parsed?.text || ''
        } else if (event === 'done') {
          finalPayload = safeParseJson(data) || null
        } else if (event === 'error') {
          const parsed = safeParseJson(data)
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

const createNewChat = async (mode) => {
  await persistUiState()
  const conversationId = uuid()
  const now = new Date().toISOString()
  await upsertConversation({
    id: conversationId,
    title: '新对话',
    mode,
    createdAt: now,
    updatedAt: now,
    updated_at: now,
    archived: false,
  })
  await loadSessionsFromLocal()
  currentSessionId.value = conversationId
  currentMode.value = mode
  chatHistory.value = []
  latestEmotion.value = null
  crisisBannerVisible.value = false
  try {
    const res = await sessionHttp.post('/api/advanced-ai/sessions', { mode, conversation_id: conversationId })
    currentSessionId.value = res.data.session_id
    currentMode.value = mode
    const initial = { id: `${conversationId}-ai-init`, role: 'ai', content: res.data.initial_message, timestamp: now }
    chatHistory.value = [initial]
    await putMessage({ ...initial, conversationId })
    await upsertConversation({
      id: conversationId,
      title: '新对话',
      mode,
      createdAt: now,
      updatedAt: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      archived: false,
    })
    latestEmotion.value = null
    crisisBannerVisible.value = false
    await loadSessionsFromLocal()
    await restoreUiState(conversationId)
  } catch {
    if (!chatSession.isActive()) return
    await deleteConversationLocal(conversationId)
    await loadSessionsFromLocal()
    ElMessage.error('创建会话失败')
  }
}

const loadSession = async (id) => {
  await persistUiState()
  currentSessionId.value = id
  const session = sessions.value.find((s) => s.id === id)
  if (session) currentMode.value = session.mode
  let hasLocalMessages = false
  try {
    const localMessages = await listMessages(id)
    if (localMessages.length) {
      hasLocalMessages = true
      chatHistory.value = localMessages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        emotion_tags: m.emotion_tags || null,
        is_crisis: m.is_crisis || false,
        created_at: m.timestamp || m.created_at,
      }))
    }
    const res = await withApiRetry(
      () => sessionHttp.get(`/api/advanced-ai/sessions/${id}/messages`),
      'loadSessionMessages',
      2
    )
    chatHistory.value = res.data.data || []
    for (const m of chatHistory.value) {
      await putMessage({
        id: `${id}-${m.id || m.created_at || uuid()}`,
        conversationId: id,
        role: m.role,
        content: m.content,
        model: m.role === 'ai' ? 'emohaa' : '',
        emotion_tags: m.emotion_tags || null,
        is_crisis: Boolean(m.is_crisis),
        timestamp: m.created_at || new Date().toISOString(),
      })
    }
    crisisBannerVisible.value = false
    const lastAiMsg = [...chatHistory.value].reverse().find((m) => m.role === 'ai' && m.emotion_tags)
    latestEmotion.value = lastAiMsg ? lastAiMsg.emotion_tags : null
    await restoreUiState(id)
  } catch (error) {
    if (!chatSession.isActive()) return
    const status = error?.response?.status
    if (status === 401 || status === 403) {
      ElMessage.error('登录状态已失效，请重新登录后继续')
      return
    }
    if (status === 404) {
      await deleteConversationLocal(id)
      await loadSessionsFromLocal()
      const next = sessions.value.find((x) => !x.archived)
      if (next) {
        await loadSession(next.id)
      } else {
        await createNewChat(currentMode.value || 'daily')
      }
      ElMessage.warning('会话不存在，已自动修复并切换到可用会话')
      return
    }
    const synced = await syncSessionsFromServer()
    if (hasLocalMessages && !synced) {
      console.warn('[AdvancedAiChat] server unavailable, fallback to local cache mode', {
        status: status || error?.status,
        url: error?.response?.config?.url,
        message: error?.message,
      })
      return
    }
    if (!navigator.onLine) {
      ElMessage.warning('当前网络不可用，请检查网络后重试')
      return
    }
    if (!synced) {
      ElMessage.error('会话服务暂时不可用，请稍后重试')
      return
    }
    ElMessage.error('加载会话失败')
  }
}

const sendMessage = async () => {
  if (!chatSession.isActive()) return
  if (!inputText.value.trim() || isTyping.value || (!isAnonymous.value && !currentSessionId.value)) return
  const userMsg = inputText.value.trim()
  inputText.value = ''
  const userLocal = {
    id: uuid(),
    role: 'user',
    content: userMsg,
    heatmap: [],
    created_at: new Date().toISOString(),
  }
  chatHistory.value.push(userLocal)
  if (!isAnonymous.value) {
    await putMessage({
      id: userLocal.id,
      conversationId: currentSessionId.value,
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
    session_id: currentSessionId.value,
    message: userMsg,
    modality: 'text',
    anonymous: Boolean(isAnonymous.value),
    mode: currentMode.value,
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
      if (String(error?.name || '').includes('Abort') || String(detail || '').includes('timeout:70000')) {
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

    const baseAvg = normalReplyAvgChars.value > 0 ? normalReplyAvgChars.value : Math.max(currentChars, 1)
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
    latestEmotion.value = data.emotion_tags || null
    if (!isAnonymous.value) {
      await putMessage({
        id: aiLocal.id,
        conversationId: currentSessionId.value,
        role: 'ai',
        content: data.reply,
        model: 'emohaa',
        emotion_tags: data.emotion_tags || null,
        is_crisis: Boolean(data.is_crisis),
        timestamp: aiLocal.created_at,
      })
      await upsertConversation({
        id: currentSessionId.value,
        title: (sessions.value.find((x) => x.id === currentSessionId.value)?.title || userMsg.slice(0, 15) || '新对话'),
        mode: currentMode.value,
        createdAt: sessions.value.find((x) => x.id === currentSessionId.value)?.createdAt || new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        archived: Boolean(sessions.value.find((x) => x.id === currentSessionId.value)?.archived),
      })
    }
    if (data.is_crisis) {
      triggerCrisisBanner()
      ElMessage.error({ message: '触发高危预警，已启动干预流程', duration: 5000 })
    }
    if (!isAnonymous.value) {
      window.dispatchEvent(new CustomEvent('assistant-message-saved', {
        detail: { sessionId: currentSessionId.value, ts: Date.now() },
      }))
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

const renameSession = async (session) => {
  const { value } = await ElMessageBox.prompt('请输入新的会话名称', '重命名会话', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    inputValue: session.title || '',
    inputPattern: /\S+/,
    inputErrorMessage: '名称不能为空',
  })
  const title = (value || '').trim()
  if (!title) return
  await upsertConversation({
    id: session.id,
    title,
    mode: session.mode,
    updatedAt: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    archived: Boolean(session.archived),
  })
  try {
    await sessionHttp.patch(`/api/advanced-ai/sessions/${session.id}`, { title })
  } catch {
    if (!chatSession.isActive()) return
    ElMessage.warning('服务端重命名失败，已保留本地名称')
  }
  await loadSessionsFromLocal()
}

const verifySessionRemovedOnServer = async (sessionId) => {
  const res = await sessionHttp.get('/api/advanced-ai/sessions')
  const list = res?.data?.data || []
  return !list.some((row) => row.id === sessionId)
}

const deleteSessionRemoteWithRetry = async (sessionId, maxRetries = 2) => {
  let lastError = null
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      await sessionHttp.delete(`/api/advanced-ai/sessions/${sessionId}`)
      const verified = await verifySessionRemovedOnServer(sessionId)
      if (!verified) throw new Error('verify_failed')
      return { ok: true, state: 'deleted', attempt: attempt + 1 }
    } catch (error) {
      if (!chatSession.isActive()) return
      lastError = error
      const status = error?.response?.status
      if (status === 404) {
        const verified = await verifySessionRemovedOnServer(sessionId)
        if (verified) return { ok: true, state: 'already_deleted', attempt: attempt + 1 }
        return { ok: false, state: 'inconsistent', attempt: attempt + 1, error }
      }
      if (status === 401 || status === 403) {
        return { ok: false, state: 'auth_failed', attempt: attempt + 1, error }
      }
      const isRetryable = !status || status >= 500
      if (isRetryable && attempt < maxRetries) {
        await sleep(250 * (attempt + 1))
        continue
      }
      return { ok: false, state: isRetryable ? 'server_failed' : 'bad_request', attempt: attempt + 1, error }
    }
  }
  return { ok: false, state: 'server_failed', attempt: maxRetries + 1, error: lastError }
}

const deleteSession = async (session) => {
  await ElMessageBox.confirm('删除后会清空本地缓存和远端会话消息，是否继续？', '删除会话', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  const result = await deleteSessionRemoteWithRetry(session.id, 2)
  if (!result.ok) {
    if (result.state === 'auth_failed') {
      ElMessage.error('服务端删除失败：登录状态已失效，请重新登录后重试（本地未删除）')
      return
    }
    if (result.state === 'inconsistent') {
      ElMessage.error('服务端删除状态不一致：会话同步校验失败（本地未删除）')
      return
    }
    if (!navigator.onLine) {
      ElMessage.warning('服务端删除失败：当前网络不可用（本地未删除）')
      return
    }
    ElMessage.error('服务端删除失败：远端会话未删除（本地未删除）')
    return
  }

  await deleteConversationLocal(session.id)
  await loadSessionsFromLocal()
  if (result.state === 'already_deleted') {
    ElMessage.success('删除成功：服务端会话已不存在，本地索引已同步清理')
  } else {
    ElMessage.success('删除成功：服务端与本地索引已同步删除')
  }
  if (currentSessionId.value === session.id) {
    const next = sessions.value.find((x) => x.id !== session.id && !x.archived)
    if (next) await loadSession(next.id)
    else await createNewChat(currentMode.value)
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

const getHeatmapStyle = (tokenObj) => {
  if (!tokenObj.weight || tokenObj.weight <= 0) return {}
  return {
    backgroundColor: businessAlpha('data-risk-high', Math.min(tokenObj.weight * 0.8, 1)),
    borderRadius: '4px',
    padding: '0 2px'
  }
}

const isDangerText = (text) => /跳楼|自杀|轻生|不想活|结束生命/.test(text || '')

const initRadar = () => {
  if (!radarRef.value) return
  radarChart = echarts.init(radarRef.value, 'xinyu-business')
  drawRadar([])
}

const resizeRadar = () => {
  if (radarChart) radarChart.resize()
}

const drawRadar = (vals) => {
  if (!radarChart) return
  setLibraryChartOption(radarChart, {
    radar: {
      radius: '65%',
      splitNumber: 4,
      axisName: { color: businessColor('text-secondary'), fontSize: 12 },
      splitLine: { lineStyle: { color: businessColor('border') } },
      splitArea: { areaStyle: { color: [businessColor('surface'), businessColor('surface-warm')] } },
      indicator: [
        { name: '学业', max: 100 },
        { name: '人际', max: 100 },
        { name: '家庭', max: 100 },
        { name: '情绪', max: 100 },
        { name: '身体', max: 100 }
      ]
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: vals,
            areaStyle: { color: businessAlpha('data-primary', 0.24) },
            lineStyle: { color: businessColor('data-risk-high'), width: 2 },
            itemStyle: { color: businessColor('data-risk-high') }
          }
        ]
      }
    ]
  })
}

const updateTrendAndRadar = () => {
  if (!latestEmotion.value) return
  const e = latestEmotion.value
  const radarVals = [
    Math.round(((e.fear || 0) * 0.6 + (e.sadness || 0) * 0.4) * 100),
    Math.round(((e.anger || 0) * 0.7 + (e.fear || 0) * 0.3) * 100),
    Math.round(((e.sadness || 0) * 0.6 + (e.neutral || 0) * 0.4) * 100),
    Math.round((((e.sadness || 0) + (e.anger || 0) + (e.fear || 0)) / 3) * 100),
    Math.round(((e.fear || 0) * 0.5 + (e.disgust || 0) * 0.5) * 100)
  ]
  drawRadar(radarVals)
}

const refreshRiskRadar = () => {
  updateTrendAndRadar()
}

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
.support-link { display: inline-flex; align-items: center; color: var(--brand-700); text-decoration: underline; text-underline-offset: 3px; }

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
  animation: bannerFlash .35s ease;
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
.ai-message-text { white-space: pre-wrap; overflow-wrap: anywhere; }

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
  animation-delay: .15s;
}

.typing i:nth-child(3) {
  animation-delay: .3s;
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

.mt-16 {
  margin-top: 16px;
}

@keyframes dot {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.6; }
  40% { transform: scale(1); opacity: 1; }
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
</style>
