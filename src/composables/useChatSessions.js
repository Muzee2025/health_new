import { nextTick } from 'vue'
import {
  sleep as defaultSleep,
  withApiRetry as defaultWithApiRetry,
} from '../services/advancedChatRetry'

const createUuid = () =>
  globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`

export function useChatSessions({
  chatSession,
  sessionHttp,
  storage,
  state,
  withApiRetry = defaultWithApiRetry,
  sleep = defaultSleep,
  ElMessage,
  ElMessageBox,
  nextTickFn = nextTick,
  uuid = createUuid,
}) {
  const {
    sessions,
    loadingSessions,
    currentSessionId,
    currentMode,
    chatHistory,
    inputText,
    isAnonymous,
    chatScrollRef,
    crisisBannerVisible,
  } = state

  const fetchSessions = async () => {
    loadingSessions.value = true
    try {
      const res = await withApiRetry(
        () => sessionHttp.get('/api/advanced-ai/sessions'),
        'fetchSessions',
        3,
        () => chatSession.isActive(),
      )
      const list = res.data.data || []
      const localMap = new Map((await storage.getAllConversations()).map((row) => [row.id, row]))
      const serverIds = new Set(list.map((row) => row.id))
      for (const [localId] of localMap) {
        if (!serverIds.has(localId)) await storage.deleteConversationLocal(localId)
      }
      for (const row of list) {
        const local = localMap.get(row.id)
        await storage.upsertConversation({
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
    } catch (error) {
      if (!chatSession.isActive()) return
      console.warn('[AdvancedAiChat] syncSessionsFromServer failed', {
        status: error?.response?.status || error?.status,
        url: error?.response?.config?.url,
        message: error?.message,
      })
      // 网络波动时保留本地会话可用
      return false
    }
  }

  const loadSessionsFromLocal = async () => {
    loadingSessions.value = true
    try {
      const rows = await storage.getAllConversations()
      sessions.value = rows
        .map((row) => ({
          id: row.id,
          title: row.title || '新对话',
          mode: row.mode || 'daily',
          createdAt: row.createdAt,
          updated_at: row.updatedAt || row.updated_at || row.createdAt,
          archived: Boolean(row.archived),
        }))
        .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
    } catch (error) {
      if (!chatSession.isActive()) return
      console.error('Failed to load chat sessions:', error)
      sessions.value = []
    } finally {
      loadingSessions.value = false
    }
  }

  const persistUiState = async () => {
    // 匿名对话不会保存草稿或滚动位置。
    if (isAnonymous.value || !chatSession.isActive() || !currentSessionId.value) return
    await storage.saveUiState(currentSessionId.value, {
      draft: inputText.value,
      scrollTop: chatScrollRef.value?.scrollTop || 0,
      updatedAt: new Date().toISOString(),
    })
  }

  const restoreUiState = async (sessionId) => {
    const uiState = await storage.getUiState(sessionId)
    chatSession.assertActive()
    inputText.value = uiState?.draft || ''
    await nextTickFn()
    if (chatScrollRef.value) {
      if (typeof uiState?.scrollTop === 'number') chatScrollRef.value.scrollTop = uiState.scrollTop
      else chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
    }
  }

  const createNewChat = async (mode) => {
    await persistUiState()
    const conversationId = uuid()
    const now = new Date().toISOString()
    await storage.upsertConversation({
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
    crisisBannerVisible.value = false
    try {
      const res = await sessionHttp.post('/api/advanced-ai/sessions', {
        mode,
        conversation_id: conversationId,
      })
      currentSessionId.value = res.data.session_id
      currentMode.value = mode
      const initial = {
        id: `${conversationId}-ai-init`,
        role: 'ai',
        content: res.data.initial_message,
        timestamp: now,
      }
      chatHistory.value = [initial]
      await storage.putMessage({ ...initial, conversationId })
      await storage.upsertConversation({
        id: conversationId,
        title: '新对话',
        mode,
        createdAt: now,
        updatedAt: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        archived: false,
      })
      crisisBannerVisible.value = false
      await loadSessionsFromLocal()
      await restoreUiState(conversationId)
    } catch {
      if (!chatSession.isActive()) return
      await storage.deleteConversationLocal(conversationId)
      await loadSessionsFromLocal()
      ElMessage.error('创建会话失败')
    }
  }

  const loadSession = async (id) => {
    await persistUiState()
    currentSessionId.value = id
    const session = sessions.value.find((row) => row.id === id)
    if (session) currentMode.value = session.mode
    let hasLocalMessages = false
    try {
      const localMessages = await storage.listMessages(id)
      if (localMessages.length) {
        hasLocalMessages = true
        chatHistory.value = localMessages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          emotion_tags: message.emotion_tags || null,
          is_crisis: message.is_crisis || false,
          created_at: message.timestamp || message.created_at,
        }))
      }
      const res = await withApiRetry(
        () => sessionHttp.get(`/api/advanced-ai/sessions/${id}/messages`),
        'loadSessionMessages',
        2,
        () => chatSession.isActive(),
      )
      chatHistory.value = res.data.data || []
      for (const message of chatHistory.value) {
        await storage.putMessage({
          id: `${id}-${message.id || message.created_at || uuid()}`,
          conversationId: id,
          role: message.role,
          content: message.content,
          model: message.role === 'ai' ? 'emohaa' : '',
          emotion_tags: message.emotion_tags || null,
          is_crisis: Boolean(message.is_crisis),
          timestamp: message.created_at || new Date().toISOString(),
        })
      }
      crisisBannerVisible.value = false
      await restoreUiState(id)
    } catch (error) {
      if (!chatSession.isActive()) return
      const status = error?.response?.status
      if (status === 401 || status === 403) {
        ElMessage.error('登录状态已失效，请重新登录后继续')
        return
      }
      if (status === 404) {
        await storage.deleteConversationLocal(id)
        await loadSessionsFromLocal()
        const next = sessions.value.find((row) => !row.archived)
        if (next) await loadSession(next.id)
        else await createNewChat(currentMode.value || 'daily')
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
    await storage.upsertConversation({
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
        return {
          ok: false,
          state: isRetryable ? 'server_failed' : 'bad_request',
          attempt: attempt + 1,
          error,
        }
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

    await storage.deleteConversationLocal(session.id)
    await loadSessionsFromLocal()
    if (result.state === 'already_deleted') {
      ElMessage.success('删除成功：服务端会话已不存在，本地索引已同步清理')
    } else {
      ElMessage.success('删除成功：服务端与本地索引已同步删除')
    }
    if (currentSessionId.value === session.id) {
      const next = sessions.value.find((row) => row.id !== session.id && !row.archived)
      if (next) await loadSession(next.id)
      else await createNewChat(currentMode.value)
    }
  }

  return {
    fetchSessions,
    syncSessionsFromServer,
    loadSessionsFromLocal,
    persistUiState,
    restoreUiState,
    createNewChat,
    loadSession,
    renameSession,
    verifySessionRemovedOnServer,
    deleteSessionRemoteWithRetry,
    deleteSession,
  }
}
