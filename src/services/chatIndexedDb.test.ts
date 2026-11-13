import { afterEach, describe, expect, it, vi } from 'vitest'
import { createChatStorage } from './chatIndexedDb'
import { createPrivateChatSession } from './privateChatSession'

type StoredRow = Record<string, unknown>
type RequestLike = {
  result: unknown
  onsuccess: null | (() => void)
  onerror: null | (() => void)
}

function requestFor(result: unknown): RequestLike {
  const request: RequestLike = { result: undefined, onsuccess: null, onerror: null }
  queueMicrotask(() => {
    request.result = result
    request.onsuccess?.()
  })
  return request
}

class MemoryStore {
  constructor(
    private readonly name: string,
    private readonly rows: Map<string, StoredRow>,
  ) {}

  createIndex() {
    return undefined
  }

  put(row: StoredRow) {
    const key = this.name === 'ui_states' ? row.conversationId : row.id
    this.rows.set(String(key), structuredClone(row))
    return requestFor(undefined)
  }

  get(key: string) {
    const row = this.rows.get(String(key))
    return requestFor(row ? structuredClone(row) : undefined)
  }

  getAll() {
    return requestFor([...this.rows.values()].map((row) => structuredClone(row)))
  }

  delete(key: string) {
    this.rows.delete(String(key))
    return requestFor(undefined)
  }

  index(name: string) {
    return new MemoryIndex(name, this.rows)
  }
}

class MemoryIndex {
  constructor(
    private readonly name: string,
    private readonly rows: Map<string, StoredRow>,
  ) {}

  getAll(key: { value: unknown }) {
    const result = [...this.rows.values()].filter((row) => row[this.name] === key.value)
    return requestFor(result.map((row) => structuredClone(row)))
  }
}

class MemoryTransaction {
  oncomplete: null | (() => void) = null
  onerror: null | (() => void) = null
  onabort: null | (() => void) = null

  constructor(private readonly database: MemoryDatabase) {
    setTimeout(() => this.oncomplete?.(), 0)
  }

  objectStore(name: string) {
    return this.database.store(name)
  }

  abort() {
    this.onabort?.()
  }
}

class MemoryDatabase {
  readonly objectStoreNames = {
    contains: (name: string) => this.rows.has(name),
  }
  private readonly rows = new Map<string, Map<string, StoredRow>>()

  constructor(
    readonly name: string,
    private readonly version: number,
  ) {}

  createObjectStore(name: string) {
    const rows = new Map<string, StoredRow>()
    this.rows.set(name, rows)
    return new MemoryStore(name, rows)
  }

  store(name: string) {
    let rows = this.rows.get(name)
    if (!rows) {
      rows = new Map<string, StoredRow>()
      this.rows.set(name, rows)
    }
    return new MemoryStore(name, rows)
  }

  transaction() {
    return new MemoryTransaction(this)
  }

  close() {}

  getVersion() {
    return this.version
  }
}

class MemoryIndexedDB {
  private readonly databases = new Map<string, MemoryDatabase>()

  open(name: string, version: number) {
    const request: RequestLike & {
      onupgradeneeded: null | (() => void)
    } = { result: undefined, onsuccess: null, onerror: null, onupgradeneeded: null }
    queueMicrotask(() => {
      let database = this.databases.get(name)
      const oldVersion = database?.getVersion() || 0
      if (!database) {
        database = new MemoryDatabase(name, version)
        this.databases.set(name, database)
      }
      request.result = database
      if (oldVersion < version) request.onupgradeneeded?.()
      request.onsuccess?.()
    })
    return request
  }
}

class MemoryKeyRange {
  static only(value: unknown) {
    return { value }
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('chatIndexedDb persistence', () => {
  it('persists conversations, messages, and UI state while keeping account databases isolated', async () => {
    vi.stubGlobal('indexedDB', new MemoryIndexedDB())
    vi.stubGlobal('IDBKeyRange', MemoryKeyRange)
    const identityA = 'synthetic-account-A'
    const sessionA = createPrivateChatSession(identityA, () => identityA)
    const storageA = createChatStorage(sessionA)

    await storageA.upsertConversation({
      id: 'conversation-1',
      title: 'Local session',
      mode: 'daily',
    })
    await storageA.putMessage({
      id: 'message-1',
      conversationId: 'conversation-1',
      role: 'ai',
      content: 'persisted reply',
      timestamp: '2026-11-14T00:00:00.000Z',
    })
    await storageA.saveUiState('conversation-1', { draft: 'persisted draft', scrollTop: 42 })

    const reopenedA = createChatStorage(createPrivateChatSession(identityA, () => identityA))
    expect(await reopenedA.getAllConversations()).toMatchObject([{ id: 'conversation-1' }])
    expect(await reopenedA.listMessages('conversation-1')).toMatchObject([
      { id: 'message-1', content: 'persisted reply' },
    ])
    expect(await reopenedA.getUiState('conversation-1')).toMatchObject({
      draft: 'persisted draft',
      scrollTop: 42,
    })

    const identityB = 'synthetic-account-B'
    const storageB = createChatStorage(createPrivateChatSession(identityB, () => identityB))
    expect(await storageB.getAllConversations()).toEqual([])
    expect(await storageB.getUiState('conversation-1')).toBeNull()
  })
})
