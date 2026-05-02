const DB_NAME = "health_new_chat_db"
const DB_VERSION = 1
const CONVERSATIONS = "conversations"
const MESSAGES = "messages"
const UI_STATES = "ui_states"

function openDb() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(CONVERSATIONS)) {
        const store = db.createObjectStore(CONVERSATIONS, { keyPath: "id" })
        store.createIndex("updatedAt", "updatedAt", { unique: false })
      }
      if (!db.objectStoreNames.contains(MESSAGES)) {
        const store = db.createObjectStore(MESSAGES, { keyPath: "id" })
        store.createIndex("conversationId", "conversationId", { unique: false })
        store.createIndex("timestamp", "timestamp", { unique: false })
      }
      if (!db.objectStoreNames.contains(UI_STATES)) {
        db.createObjectStore(UI_STATES, { keyPath: "conversationId" })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function withStore<T>(storeName: string, mode: IDBTransactionMode, run: (store: IDBObjectStore) => void | Promise<T>) {
  const db = await openDb()
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(storeName, mode)
    const store = tx.objectStore(storeName)
    Promise.resolve(run(store))
      .then((res) => {
        tx.oncomplete = () => resolve(res as T)
        tx.onerror = () => reject(tx.error)
        tx.onabort = () => reject(tx.error)
      })
      .catch(reject)
  })
}

export async function upsertConversation(record: any) {
  await withStore<void>(CONVERSATIONS, "readwrite", (store) => {
    store.put(record)
  })
}

export async function getAllConversations() {
  return withStore<any[]>(CONVERSATIONS, "readonly", (store) => {
    return new Promise<any[]>((resolve, reject) => {
      const req = store.getAll()
      req.onsuccess = () => resolve(req.result || [])
      req.onerror = () => reject(req.error)
    })
  })
}

export async function deleteConversationLocal(conversationId: string) {
  await withStore<void>(CONVERSATIONS, "readwrite", (store) => {
    store.delete(conversationId)
  })
  await withStore<void>(UI_STATES, "readwrite", (store) => {
    store.delete(conversationId)
  })
  await withStore<void>(MESSAGES, "readwrite", (store) => {
    const index = store.index("conversationId")
    const req = index.openCursor(IDBKeyRange.only(conversationId))
    req.onsuccess = () => {
      const cursor = req.result
      if (!cursor) return
      cursor.delete()
      cursor.continue()
    }
  })
}

export async function putMessage(record: any) {
  await withStore<void>(MESSAGES, "readwrite", (store) => {
    store.put(record)
  })
}

export async function listMessages(conversationId: string) {
  return withStore<any[]>(MESSAGES, "readonly", (store) => {
    const index = store.index("conversationId")
    return new Promise<any[]>((resolve, reject) => {
      const req = index.getAll(IDBKeyRange.only(conversationId))
      req.onsuccess = () => {
        const rows = req.result || []
        rows.sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)))
        resolve(rows)
      }
      req.onerror = () => reject(req.error)
    })
  })
}

export async function saveUiState(conversationId: string, state: any) {
  await withStore<void>(UI_STATES, "readwrite", (store) => {
    store.put({ conversationId, ...state })
  })
}

export async function getUiState(conversationId: string) {
  return withStore<any | null>(UI_STATES, "readonly", (store) => {
    return new Promise<any | null>((resolve, reject) => {
      const req = store.get(conversationId)
      req.onsuccess = () => resolve(req.result || null)
      req.onerror = () => reject(req.error)
    })
  })
}

