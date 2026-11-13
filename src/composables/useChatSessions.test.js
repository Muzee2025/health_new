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
})
