import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as Vue from 'vue'
import { createRenderer, effectScope, nextTick } from 'vue'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import AdvancedAiChat from './AdvancedAiChat.vue'
import ChatComposer from './chat/ChatComposer.vue'
import ChatSessionSidebar from './chat/ChatSessionSidebar.vue'
import ChatMessageList from './chat/ChatMessageList.vue'

const mocks = vi.hoisted(() => ({
  request: vi.fn(),
  conversations: new Map(),
  messageRows: new Map(),
  uiStates: new Map(),
  getAllConversations: vi.fn(),
  deleteConversationLocal: vi.fn(),
  listMessages: vi.fn(),
  putMessage: vi.fn(),
  getUiState: vi.fn(),
  saveUiState: vi.fn(),
  upsertConversation: vi.fn(),
  messageInfo: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn(),
  mountedHooks: [],
  unmountedHooks: [],
}))

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    onMounted: (callback) => mocks.mountedHooks.push(callback),
    onBeforeUnmount: (callback) => mocks.unmountedHooks.push(callback),
    useSSRContext: () => ({ modules: new Set() }),
  }
})

vi.mock('axios', () => ({
  default: {
    request: (...args) => mocks.request(...args),
    getUri: () => 'http://127.0.0.1:5173/api/ws',
  },
}))

vi.mock('element-plus', () => {
  const message = vi.fn()
  const emptyComponent = { render: () => null }
  Object.assign(message, {
    info: mocks.messageInfo,
    success: mocks.messageSuccess,
    warning: mocks.messageWarning,
    error: mocks.messageError,
  })
  return {
    ElMessage: message,
    ElMessageBox: { confirm: vi.fn(), prompt: vi.fn() },
    ElButton: emptyComponent,
    ElInput: emptyComponent,
    ElDropdown: emptyComponent,
    ElDropdownMenu: emptyComponent,
    ElDropdownItem: emptyComponent,
    ElSwitch: emptyComponent,
    ElIcon: emptyComponent,
    ElAvatar: emptyComponent,
    vLoading: {},
  }
})

vi.mock('../../components/RiskFactorFiveDimension.vue', () => ({
  default: { render: () => null },
}))

vi.mock('@/services/advancedChatRetry', () => ({
  sleep: vi.fn(async () => {}),
  withApiRetry: vi.fn(async (request) => request()),
}))

vi.mock('@/services/advancedChatStream', () => ({
  createTimeoutController: vi.fn(),
  parseSsePacket: vi.fn(),
  safeParseJson: vi.fn(),
}))

vi.mock('@/services/chatIndexedDb', () => ({
  createChatStorage: (session) => {
    const guard =
      (operation) =>
      (...args) =>
        session.run(() => operation(...args))
    return {
      getAllConversations: guard(mocks.getAllConversations),
      deleteConversationLocal: guard(mocks.deleteConversationLocal),
      listMessages: guard(mocks.listMessages),
      putMessage: guard(mocks.putMessage),
      getUiState: guard(mocks.getUiState),
      saveUiState: guard(mocks.saveUiState),
      upsertConversation: guard(mocks.upsertConversation),
    }
  },
}))

function createLocalStorage() {
  const values = new Map([['token', 'synthetic-session-A']])
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
    clear: () => values.clear(),
  }
}

function createPage() {
  const scope = effectScope()
  const page = scope.run(() => AdvancedAiChat.setup?.({}, { expose: vi.fn() }))
  if (!page) throw new Error('AdvancedAiChat setup did not return its bindings')
  return { page: page, scope }
}

const pageSource = readFileSync(new URL('./AdvancedAiChat.vue', import.meta.url), 'utf8')
const pageFilename = 'src/views/student/AdvancedAiChat.vue'
const { descriptor: pageDescriptor } = parse(pageSource, { filename: pageFilename })
const pageScript = compileScript(pageDescriptor, { id: 'advanced-chat-composer-integration' })
const pageTemplate = compileTemplate({
  source: pageDescriptor.template.content,
  filename: pageFilename,
  id: 'advanced-chat-composer-integration',
  compilerOptions: { bindingMetadata: pageScript.bindings, mode: 'function' },
})
if (pageTemplate.errors.length) throw pageTemplate.errors[0]
const integrationRender = runInNewContext(`(Vue) => { ${pageTemplate.code} }`)(Vue)

const messageListSource = readFileSync(
  new URL('./chat/ChatMessageList.vue', import.meta.url),
  'utf8',
)
const messageListFilename = 'src/views/student/chat/ChatMessageList.vue'
const { descriptor: messageListDescriptor } = parse(messageListSource, {
  filename: messageListFilename,
})
const messageListScript = compileScript(messageListDescriptor, {
  id: 'advanced-chat-message-list-integration',
})
const messageListTemplate = compileTemplate({
  source: messageListDescriptor.template.content,
  filename: messageListFilename,
  id: 'advanced-chat-message-list-integration',
  compilerOptions: { bindingMetadata: messageListScript.bindings, mode: 'function' },
})
if (messageListTemplate.errors.length) throw messageListTemplate.errors[0]
const messageListRender = runInNewContext(`(Vue) => { ${messageListTemplate.code} }`)(Vue)

function createTreeRenderer() {
  const insert = (node, parent, anchor = null) => {
    if (node.parent) {
      const oldIndex = node.parent.children.indexOf(node)
      if (oldIndex >= 0) node.parent.children.splice(oldIndex, 1)
    }
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index < 0) parent.children.push(node)
    else parent.children.splice(index, 0, node)
    node.parent = parent
  }

  return createRenderer({
    patchProp(node, key, _previous, next) {
      node.props[key] = next
    },
    insert,
    remove(node) {
      if (!node.parent) return
      const index = node.parent.children.indexOf(node)
      if (index >= 0) node.parent.children.splice(index, 1)
      node.parent = null
    },
    createElement(type) {
      return { type, props: {}, children: [], parent: null, text: '' }
    },
    createText(text) {
      return { type: '#text', props: {}, children: [], parent: null, text }
    },
    createComment(text) {
      return { type: '#comment', props: {}, children: [], parent: null, text }
    },
    setText(node, text) {
      node.text = text
    },
    setElementText(node, text) {
      node.text = text
      node.children = []
    },
    parentNode(node) {
      return node.parent
    },
    nextSibling(node) {
      if (!node.parent) return null
      const index = node.parent.children.indexOf(node)
      return node.parent.children[index + 1] || null
    },
    insertStaticContent(content, parent, anchor) {
      const node = {
        type: '#static',
        props: {},
        children: [],
        parent: null,
        text: content,
      }
      insert(node, parent, anchor)
      return [node, node]
    },
  })
}

function findVNode(vnode, predicate) {
  if (!vnode) return null
  if (predicate(vnode)) return vnode
  if (Array.isArray(vnode.children)) {
    for (const child of vnode.children) {
      const match = findVNode(child, predicate)
      if (match) return match
    }
  }
  return null
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

function deferred() {
  let resolve
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.conversations.clear()
  mocks.messageRows.clear()
  mocks.uiStates.clear()
  mocks.mountedHooks.length = 0
  mocks.unmountedHooks.length = 0
  vi.stubGlobal('localStorage', createLocalStorage())

  mocks.getAllConversations.mockImplementation(async () => [...mocks.conversations.values()])
  mocks.deleteConversationLocal.mockImplementation(async (id) => {
    mocks.conversations.delete(id)
    mocks.uiStates.delete(id)
    for (const [messageId, row] of mocks.messageRows) {
      if (row.conversationId === id) mocks.messageRows.delete(messageId)
    }
  })
  mocks.listMessages.mockImplementation(async (id) =>
    [...mocks.messageRows.values()].filter((row) => row.conversationId === id),
  )
  mocks.putMessage.mockImplementation(async (row) => {
    mocks.messageRows.set(String(row.id), row)
  })
  mocks.getUiState.mockImplementation(async (id) => mocks.uiStates.get(id) || null)
  mocks.saveUiState.mockImplementation(async (id, row) => {
    mocks.uiStates.set(id, row)
  })
  mocks.upsertConversation.mockImplementation(async (row) => {
    mocks.conversations.set(String(row.id), row)
  })
  mocks.request.mockRejectedValue(new Error('Unexpected API request in characterization test'))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AdvancedAiChat session lifecycle integration contract', () => {
  it('wires composer model and actions to the existing page bindings', async () => {
    const originalSetup = AdvancedAiChat.setup
    const originalRender = AdvancedAiChat.render
    const originalComposerRender = ChatComposer.render
    const originalSidebarRender = ChatSessionSidebar.render
    const originalMessageListRender = ChatMessageList.render
    const sendMessage = vi.fn()
    const toggleDeepThink = vi.fn()
    AdvancedAiChat.setup = (props, context) => {
      const bindings = originalSetup(props, context)
      bindings.sendMessage = sendMessage
      bindings.toggleDeepThink = toggleDeepThink
      return bindings
    }
    AdvancedAiChat.render = integrationRender
    ChatComposer.render = () => null
    ChatSessionSidebar.render = () => null
    ChatMessageList.render = messageListRender
    const root = { type: 'root', props: {}, children: [], parent: null, text: '' }
    const app = createTreeRenderer().createApp(AdvancedAiChat)
    app.component('LibraryIcon', { render: () => null })
    app.component('router-link', { render: () => null })
    try {
      app.mount(root)
      const composer = findVNode(app._instance.subTree, (vnode) => vnode.type === ChatComposer)
      expect(composer).toBeTruthy()
      expect(composer.props['onUpdate:modelValue']).toBeTypeOf('function')
      composer.props['onUpdate:modelValue']('composer integration draft')
      expect(app._instance.setupState.inputText).toBe('composer integration draft')

      expect(composer.props.onSend).toBe(sendMessage)
      composer.props.onSend()
      expect(sendMessage).toHaveBeenCalledOnce()
      expect(composer.props.onToggleDeep).toBe(toggleDeepThink)
      composer.props.onToggleDeep()
      expect(toggleDeepThink).toHaveBeenCalledOnce()
    } finally {
      app.unmount()
      AdvancedAiChat.setup = originalSetup
      AdvancedAiChat.render = originalRender
      ChatComposer.render = originalComposerRender
      ChatSessionSidebar.render = originalSidebarRender
      ChatMessageList.render = originalMessageListRender
    }
  })

  it('routes sidebar events to the existing session actions', () => {
    const originalSetup = AdvancedAiChat.setup
    const originalRender = AdvancedAiChat.render
    const originalSidebarRender = ChatSessionSidebar.render
    const originalComposerRender = ChatComposer.render
    const originalMessageListRender = ChatMessageList.render
    const createNewChat = vi.fn()
    const loadSession = vi.fn()
    const handleSessionCommand = vi.fn()
    AdvancedAiChat.setup = (props, context) => {
      const bindings = originalSetup(props, context)
      bindings.createNewChat = createNewChat
      bindings.loadSession = loadSession
      bindings.handleSessionCommand = handleSessionCommand
      return bindings
    }
    AdvancedAiChat.render = integrationRender
    ChatSessionSidebar.render = () => null
    ChatComposer.render = () => null
    ChatMessageList.render = () => null
    const root = { type: 'root', props: {}, children: [], parent: null, text: '' }
    const app = createTreeRenderer().createApp(AdvancedAiChat)
    app.component('LibraryIcon', { render: () => null })
    app.component('router-link', { render: () => null })
    try {
      app.mount(root)
      const sidebar = findVNode(app._instance.subTree, (vnode) => vnode.type === ChatSessionSidebar)
      expect(sidebar).toBeTruthy()
      expect(sidebar.props.onCreate).toBe(createNewChat)
      expect(sidebar.props.onSelect).toBe(loadSession)

      const target = { id: 'sidebar-session', title: 'A session' }
      sidebar.props.onCreate('counseling')
      sidebar.props.onSelect('sidebar-session')
      sidebar.props.onRename(target)
      sidebar.props.onDelete(target)

      expect(createNewChat).toHaveBeenCalledWith('counseling')
      expect(loadSession).toHaveBeenCalledWith('sidebar-session')
      expect(handleSessionCommand).toHaveBeenNthCalledWith(1, 'rename', target)
      expect(handleSessionCommand).toHaveBeenNthCalledWith(2, 'delete', target)
    } finally {
      app.unmount()
      AdvancedAiChat.setup = originalSetup
      AdvancedAiChat.render = originalRender
      ChatSessionSidebar.render = originalSidebarRender
      ChatComposer.render = originalComposerRender
      ChatMessageList.render = originalMessageListRender
    }
  })

  it('removes a locally cached session after a server 404 and loads the next available session', async () => {
    mocks.conversations.set('missing-session', conversation('missing-session'))
    mocks.conversations.set('survivor-session', conversation('survivor-session'))
    mocks.request.mockImplementation(async ({ url }) => {
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

    const { page, scope } = createPage()
    try {
      await page.loadSessionsFromLocal()
      await page.loadSession('missing-session')

      expect(mocks.deleteConversationLocal).toHaveBeenCalledWith('missing-session')
      expect(page.currentSessionId.value).toBe('survivor-session')
      expect(page.sessions.value.map((row) => row.id)).toEqual(['survivor-session'])
      expect(page.chatHistory.value[0].content).toBe('surviving session')
    } finally {
      scope.stop()
    }
  })

  it('keeps cached messages visible when the message endpoint and session sync both fail', async () => {
    mocks.conversations.set('cached-session', conversation('cached-session'))
    mocks.messageRows.set('cached-message', {
      id: 'cached-message',
      conversationId: 'cached-session',
      role: 'ai',
      content: 'cached reply',
      timestamp: '2026-11-14T00:00:00.000Z',
    })
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    mocks.request.mockRejectedValue(new Error('synthetic network failure'))

    const { page, scope } = createPage()
    try {
      await page.loadSessionsFromLocal()
      await page.loadSession('cached-session')

      expect(page.chatHistory.value).toHaveLength(1)
      expect(page.chatHistory.value[0]).toMatchObject({ content: 'cached reply', role: 'ai' })
      expect(mocks.deleteConversationLocal).not.toHaveBeenCalled()
      expect(mocks.messageError).not.toHaveBeenCalled()
    } finally {
      scope.stop()
    }
  })

  it('clears anonymous content without persisting it or contacting the session API', async () => {
    const { page, scope } = createPage()
    try {
      page.inputText.value = 'ephemeral draft'
      page.chatHistory.value = [{ id: 'temporary', role: 'user', content: 'ephemeral message' }]
      page.isAnonymous.value = true
      await nextTick()
      await page.persistUiState()

      expect(page.inputText.value).toBe('')
      expect(page.chatHistory.value).toEqual([])
      expect(mocks.saveUiState).not.toHaveBeenCalled()
      expect(mocks.request).not.toHaveBeenCalled()
    } finally {
      scope.stop()
    }
  })

  it('ignores account A late responses after the login token switches to account B', async () => {
    mocks.conversations.set('account-A-session', conversation('account-A-session'))
    mocks.conversations.set('account-B-session', conversation('account-B-session'))
    mocks.messageRows.set('account-B-message', {
      id: 'account-B-message',
      conversationId: 'account-B-session',
      role: 'ai',
      content: 'account B cache',
      timestamp: '2026-11-14T00:00:00.000Z',
    })
    const lateResponse = deferred()
    mocks.request.mockImplementation(({ url }) => {
      if (url === '/api/advanced-ai/sessions/account-A-session/messages') {
        return lateResponse.promise
      }
      throw new Error(`Unexpected URL: ${url}`)
    })

    const { page: pageA, scope: scopeA } = createPage()
    const pendingLoad = pageA.loadSession('account-A-session')
    try {
      await new Promise((resolve) => setTimeout(resolve, 0))
      expect(mocks.request).toHaveBeenCalledTimes(1)
      localStorage.setItem('token', 'synthetic-session-B')
      const { page: pageB, scope: scopeB } = createPage()
      try {
        const accountBHistory = [
          { id: 'account-B-message', role: 'ai', content: 'account B cache' },
        ]
        pageB.currentSessionId.value = 'account-B-session'
        pageB.chatHistory.value = accountBHistory

        lateResponse.resolve({
          data: {
            data: [
              {
                id: 'late-account-A-message',
                role: 'ai',
                content: 'late account A response',
                created_at: '2026-11-14T00:00:01.000Z',
              },
            ],
          },
        })
        await pendingLoad

        expect(pageA.chatHistory.value).toEqual([])
        expect(pageB.chatHistory.value).toEqual(accountBHistory)
        expect(mocks.putMessage).not.toHaveBeenCalled()
        expect([...mocks.messageRows.keys()]).toEqual(['account-B-message'])
        expect(mocks.conversations.has('account-A-session')).toBe(true)
      } finally {
        scopeB.stop()
      }
    } finally {
      scopeA.stop()
    }
  })

  it('blocks local reads from the previous identity after the login token changes', async () => {
    const { page, scope } = createPage()
    try {
      localStorage.setItem('token', 'synthetic-session-B')
      await page.loadSessionsFromLocal()

      expect(mocks.getAllConversations).not.toHaveBeenCalled()
      expect(mocks.request).not.toHaveBeenCalled()
      expect(page.sessions.value).toEqual([])
    } finally {
      scope.stop()
    }
  })
  it('keeps C2 draft and scroll persistence connected to the message list scroll element', async () => {
    const originalSetup = AdvancedAiChat.setup
    const originalRender = AdvancedAiChat.render
    const originalComposerRender = ChatComposer.render
    const originalSidebarRender = ChatSessionSidebar.render
    const originalMessageListRender = ChatMessageList.render
    const originalMessageListSetup = ChatMessageList.setup
    const scrollElement = { scrollTop: 0, scrollHeight: 180 }
    const scrollToBottom = vi.fn(async () => {
      scrollElement.scrollTop = scrollElement.scrollHeight
    })
    AdvancedAiChat.render = integrationRender
    ChatComposer.render = () => null
    ChatSessionSidebar.render = () => null
    ChatMessageList.setup = (_props, { expose }) => {
      expose({ scrollElement: Vue.ref(scrollElement), scrollToBottom })
      return () => null
    }

    const root = { type: 'root', props: {}, children: [], parent: null, text: '' }
    const app = createTreeRenderer().createApp(AdvancedAiChat)
    app.component('LibraryIcon', { render: () => null })
    app.component('router-link', { render: () => null })
    try {
      app.mount(root)
      const messageList = findVNode(
        app._instance.subTree,
        (vnode) => vnode.type === ChatMessageList,
      )
      expect(messageList).toBeTruthy()
      expect(messageList.ref).toBeTruthy()
      expect(messageList.props.messages).toBe(app._instance.setupState.chatHistory)

      const page = app._instance.setupState
      expect(page.messageListRef).toBeTruthy()
      expect(page.chatScrollRef.scrollTop).toBe(0)
      expect(page.chatScrollRef.scrollHeight).toBe(180)
      scrollElement.scrollTop = 27
      scrollElement.scrollHeight = 180
      page.currentSessionId = 'message-list-scroll'
      page.inputText = 'persisted message draft'

      expect(page.chatScrollRef.scrollTop).toBe(27)
      expect(page.chatScrollRef.scrollHeight).toBe(180)
      await page.persistUiState()
      expect(mocks.saveUiState).toHaveBeenCalledWith(
        'message-list-scroll',
        expect.objectContaining({ draft: 'persisted message draft', scrollTop: 27 }),
      )

      mocks.uiStates.set('message-list-scroll', {
        draft: 'restored draft',
        scrollTop: 42,
      })
      page.inputText = ''
      scrollElement.scrollTop = 0
      page.currentSessionId = null
      mocks.request.mockResolvedValue({ data: { data: [] } })
      await page.loadSession('message-list-scroll')
      expect(page.inputText).toBe('restored draft')
      expect(scrollElement.scrollTop).toBe(42)

      await page.scrollToBottom()
      expect(scrollElement.scrollTop).toBe(180)
    } finally {
      app.unmount()
      AdvancedAiChat.setup = originalSetup
      AdvancedAiChat.render = originalRender
      ChatComposer.render = originalComposerRender
      ChatSessionSidebar.render = originalSidebarRender
      ChatMessageList.render = originalMessageListRender
      ChatMessageList.setup = originalMessageListSetup
    }
  })
})
