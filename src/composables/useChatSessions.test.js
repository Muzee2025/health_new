import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { createPrivateChatSession } from '../services/privateChatSession'
import { useChatSessions } from './useChatSessions'

function createLocalStorage() {
  const values = new Map([['token', 'synthetic-session-A']])
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
    clear: () => values.clear(),
  }
}

function conversation(id) {
  return {
    id,
    title: id,
    mode: 'daily',
    createdAt: '2026-11-14T00:00:00.000Z',
    updatedAt: '2026-11-14T00:00:00.000Z',
    updated_at: '2026-11-14T00:00:00.000Z',
    archived: false,
  }
}

function createHarness() {
  const chatSession = createPrivateChatSession(
    'synthetic-session-A',
    () => localStorage.getItem('token') || '',
  )
  const conversations = new Map()
  const messageRows = new Map()
  const uiStates = new Map()
  const storage = {
    getAllConversations: vi.fn(async () => [...conversations.values()]),
    deleteConversationLocal: vi.fn(async (id) => {
      conversations.delete(id)
      uiStates.delete(id)
      for (const [messageId, row] of messageRows) {
        if (row.conversationId === id) messageRows.delete(messageId)
      }
    }),
    listMessages: vi.fn(async (id) =>
      [...messageRows.values()].filter((row) => row.conversationId === id),
    ),
    putMessage: vi.fn(async (row) => messageRows.set(row.id, row)),
    getUiState: vi.fn(async (id) => uiStates.get(id) || null),
    saveUiState: vi.fn(async (id, row) => uiStates.set(id, row)),
    upsertConversation: vi.fn(async (row) => conversations.set(row.id, row)),
  }
  const guardedStorage = Object.fromEntries(
    Object.entries(storage).map(([name, operation]) => [
      name,
      (...args) => chatSession.run(() => operation(...args)),
    ]),
  )
  const sessionHttp = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
  const withApiRetry = vi.fn((request) => request())
  const sleep = vi.fn(async () => {})
  const messages = {
    info: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  }
  const state = {
    sessions: ref([]),
    loadingSessions: ref(false),
    currentSessionId: ref(null),
    currentMode: ref('daily'),
    chatHistory: ref([]),
    inputText: ref(''),
    isAnonymous: ref(false),
    chatScrollRef: ref(null),
    crisisBannerVisible: ref(false),
  }
  const lifecycle = useChatSessions({
    chatSession,
    sessionHttp,
    storage: guardedStorage,
    state,
    withApiRetry,
    sleep,
    ElMessage: messages,
    ElMessageBox: { confirm: vi.fn(), prompt: vi.fn() },
  })
  return { lifecycle, state, storage, sessionHttp, messages, conversations, messageRows, uiStates }
}

beforeEach(() => {
  vi.stubGlobal('localStorage', createLocalStorage())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useChatSessions contract', () => {
  it('self-heals a stale local session after a server 404 and loads the next session', async () => {
    const context = createHarness()
    context.conversations.set('missing-session', conversation('missing-session'))
    context.conversations.set('survivor-session', conversation('survivor-session'))
    context.sessionHttp.get.mockImplementation(async (url) => {
      if (url === '/api/advanced-ai/sessions/missing-session/messages') {
        throw { response: { status: 404 } }
      }
      if (url === '/api/advanced-ai/sessions/survivor-session/messages') {
        return {
          data: {
            data: [
              {
                id: 'server-message',
                role: 'ai',
                content: 'surviving session',
                created_at: '2026-11-14T00:00:00.000Z',
              },
            ],
          },
        }
      }
      throw new Error(`Unexpected URL: ${url}`)
    })

    await context.lifecycle.loadSessionsFromLocal()
    await context.lifecycle.loadSession('missing-session')

    expect(context.storage.deleteConversationLocal).toHaveBeenCalledWith('missing-session')
    expect(context.state.currentSessionId.value).toBe('survivor-session')
    expect(context.state.sessions.value.map((row) => row.id)).toEqual(['survivor-session'])
    expect(context.state.chatHistory.value[0].content).toBe('surviving session')
  })

  it('cascades a 404 cleanup and creates a session when no survivor exists', async () => {
    const context = createHarness()
    context.conversations.set('missing-session', conversation('missing-session'))
    context.messageRows.set('stale-message', {
      id: 'stale-message',
      conversationId: 'missing-session',
      role: 'ai',
      content: 'stale content',
      timestamp: '2026-11-14T00:00:00.000Z',
    })
    context.uiStates.set('missing-session', { draft: 'stale draft', scrollTop: 12 })
    context.sessionHttp.get.mockRejectedValue({ response: { status: 404 } })
    context.sessionHttp.post.mockImplementation(async (_url, payload) => ({
      data: { session_id: payload.conversation_id, initial_message: 'new chat' },
    }))

    await context.lifecycle.loadSessionsFromLocal()
    await context.lifecycle.loadSession('missing-session')

    expect(context.storage.deleteConversationLocal).toHaveBeenCalledWith('missing-session')
    expect(context.conversations.has('missing-session')).toBe(false)
    expect(context.messageRows.has('stale-message')).toBe(false)
    expect(context.uiStates.has('missing-session')).toBe(false)
    expect(context.sessionHttp.post).toHaveBeenCalledWith(
      '/api/advanced-ai/sessions',
      expect.objectContaining({ mode: 'daily', conversation_id: expect.any(String) }),
    )
    const createdId = context.sessionHttp.post.mock.calls[0][1].conversation_id
    expect(context.state.currentSessionId.value).toBe(createdId)
    expect(context.state.sessions.value).toMatchObject([{ id: createdId, mode: 'daily' }])
  })

  it('keeps cached messages visible when both message loading and server sync fail', async () => {
    const context = createHarness()
    context.conversations.set('cached-session', conversation('cached-session'))
    context.messageRows.set('cached-message', {
      id: 'cached-message',
      conversationId: 'cached-session',
      role: 'ai',
      content: 'cached reply',
      timestamp: '2026-11-14T00:00:00.000Z',
    })
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    context.sessionHttp.get.mockRejectedValue(new Error('synthetic network failure'))

    await context.lifecycle.loadSessionsFromLocal()
    await context.lifecycle.loadSession('cached-session')

    expect(context.state.chatHistory.value).toHaveLength(1)
    expect(context.state.chatHistory.value[0]).toMatchObject({
      content: 'cached reply',
      role: 'ai',
    })
    expect(context.storage.deleteConversationLocal).not.toHaveBeenCalled()
    expect(context.messages.error).not.toHaveBeenCalled()
  })

  it('does not read prior account sessions after the login identity changes', async () => {
    const context = createHarness()
    localStorage.setItem('token', 'synthetic-session-B')

    await context.lifecycle.loadSessionsFromLocal()

    expect(context.storage.getAllConversations).not.toHaveBeenCalled()
    expect(context.sessionHttp.get).not.toHaveBeenCalled()
    expect(context.state.sessions.value).toEqual([])
  })

  it('skips draft persistence in anonymous mode and restores real-session draft and scroll state', async () => {
    const context = createHarness()
    context.state.currentSessionId.value = 'saved-session'
    context.state.inputText.value = 'draft text'
    context.state.chatScrollRef.value = { scrollTop: 42, scrollHeight: 120 }

    await context.lifecycle.persistUiState()
    expect(context.storage.saveUiState).toHaveBeenCalledWith(
      'saved-session',
      expect.objectContaining({ draft: 'draft text', scrollTop: 42 }),
    )

    context.state.isAnonymous.value = true
    context.state.inputText.value = 'anonymous draft'
    await context.lifecycle.persistUiState()
    expect(context.storage.saveUiState).toHaveBeenCalledTimes(1)

    context.state.isAnonymous.value = false
    context.state.inputText.value = ''
    context.state.chatScrollRef.value = { scrollTop: 0, scrollHeight: 120 }
    await context.lifecycle.restoreUiState('saved-session')
    expect(context.state.inputText.value).toBe('draft text')
    expect(context.state.chatScrollRef.value.scrollTop).toBe(42)
  })

  it('keeps local messages and UI state when remote deletion fails', async () => {
    const context = createHarness()
    context.conversations.set('delete-failure', conversation('delete-failure'))
    context.messageRows.set('delete-message', {
      id: 'delete-message',
      conversationId: 'delete-failure',
      role: 'ai',
      content: 'keep this cache',
      timestamp: '2026-11-14T00:00:00.000Z',
    })
    context.uiStates.set('delete-failure', { draft: 'keep this draft', scrollTop: 25 })
    context.sessionHttp.delete.mockRejectedValue({ response: { status: 500 } })

    await context.lifecycle.deleteSession({ id: 'delete-failure', title: 'delete-failure' })

    expect(context.sessionHttp.delete).toHaveBeenCalledTimes(3)
    expect(context.storage.deleteConversationLocal).not.toHaveBeenCalled()
    expect(context.conversations.has('delete-failure')).toBe(true)
    expect(context.messageRows.has('delete-message')).toBe(true)
    expect(context.uiStates.has('delete-failure')).toBe(true)
  })

  it('deletes local messages and UI state after remote deletion succeeds', async () => {
    const context = createHarness()
    context.conversations.set('delete-success', conversation('delete-success'))
    context.messageRows.set('delete-message', {
      id: 'delete-message',
      conversationId: 'delete-success',
      role: 'ai',
      content: 'remove this cache',
      timestamp: '2026-11-14T00:00:00.000Z',
    })
    context.uiStates.set('delete-success', { draft: 'remove this draft', scrollTop: 25 })
    context.state.currentSessionId.value = 'delete-success'
    context.sessionHttp.delete.mockResolvedValue({})
    context.sessionHttp.get.mockResolvedValue({ data: { data: [] } })
    context.sessionHttp.post.mockImplementation(async (_url, payload) => ({
      data: { session_id: payload.conversation_id, initial_message: 'replacement chat' },
    }))

    await context.lifecycle.deleteSession({ id: 'delete-success', title: 'delete-success' })

    expect(context.storage.deleteConversationLocal).toHaveBeenCalledWith('delete-success')
    expect(context.conversations.has('delete-success')).toBe(false)
    expect(context.messageRows.has('delete-message')).toBe(false)
    expect(context.uiStates.has('delete-success')).toBe(false)
    expect(context.state.sessions.value.map((row) => row.id)).not.toContain('delete-success')
  })
})
