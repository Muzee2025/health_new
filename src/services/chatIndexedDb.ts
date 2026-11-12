import type { createPrivateChatSession } from './privateChatSession'

export function createChatStorage(session: ReturnType<typeof createPrivateChatSession>) {
  const DB_VERSION = 1
  const CONVERSATIONS = 'conversations'
  const MESSAGES = 'messages'
  const UI_STATES = 'ui_states'

  async function openDb() {
    const DB_NAME = await session.databaseName()
    session.assertActive()
    return new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains(CONVERSATIONS)) {
          const store = db.createObjectStore(CONVERSATIONS, { keyPath: 'id' })
          store.createIndex('updatedAt', 'updatedAt', { unique: false })
        }
        if (!db.objectStoreNames.contains(MESSAGES)) {
          const store = db.createObjectStore(MESSAGES, { keyPath: 'id' })
          store.createIndex('conversationId', 'conversationId', { unique: false })
          store.createIndex('timestamp', 'timestamp', { unique: false })
        }
        if (!db.objectStoreNames.contains(UI_STATES)) {
          db.createObjectStore(UI_STATES, { keyPath: 'conversationId' })
        }
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  }

  async function withStore<T>(
    storeName: string,
    mode: IDBTransactionMode,
    run: (store: IDBObjectStore) => void | Promise<T>,
  ) {
    session.assertActive()
    const db = await openDb()
    try {
      session.assertActive()
    } catch (error) {
      db.close()
      throw error
    }
    return new Promise<T>((resolve, reject) => {
      const tx = db.transaction(storeName, mode)
      const abort = () => {
        try {
          tx.abort()
        } catch {}
      }
      session.signal?.addEventListener('abort', abort, { once: true })
      const close = () => {
        session.signal?.removeEventListener('abort', abort)
        db.close()
      }
      const store = tx.objectStore(storeName)
      let result: T
      let operationDone = false
      let transactionDone = false
      const finish = () => {
        if (!operationDone || !transactionDone) return
        try {
          session.assertActive()
          resolve(result)
        } catch (error) {
          reject(error)
        }
      }
      tx.oncomplete = () => {
        transactionDone = true
        close()
        finish()
      }
      tx.onerror = () => {
        close()
        reject(tx.error)
      }
      tx.onabort = () => {
        close()
        reject(tx.error || new DOMException('Chat transaction cancelled', 'AbortError'))
      }
      Promise.resolve()
        .then(() => {
          session.assertActive()
          return run(store)
        })
        .then((res) => {
          result = res as T
          operationDone = true
          finish()
        })
        .catch((error) => {
          abort()
          close()
          reject(error)
        })
    })
  }

  async function upsertConversation(record: any) {
    await withStore<void>(CONVERSATIONS, 'readwrite', (store) => {
      store.put(record)
    })
  }

  async function getAllConversations() {
    return withStore<any[]>(CONVERSATIONS, 'readonly', (store) => {
      return new Promise<any[]>((resolve, reject) => {
        const req = store.getAll()
        req.onsuccess = () => resolve(req.result || [])
        req.onerror = () => reject(req.error)
      })
    })
  }

  async function deleteConversationLocal(conversationId: string) {
    await withStore<void>(CONVERSATIONS, 'readwrite', (store) => {
      store.delete(conversationId)
    })
    await withStore<void>(UI_STATES, 'readwrite', (store) => {
      store.delete(conversationId)
    })
    await withStore<void>(MESSAGES, 'readwrite', (store) => {
      const index = store.index('conversationId')
      const req = index.openCursor(IDBKeyRange.only(conversationId))
      req.onsuccess = () => {
        const cursor = req.result
        if (!cursor) return
        cursor.delete()
        cursor.continue()
      }
    })
  }

  async function putMessage(record: any) {
    await withStore<void>(MESSAGES, 'readwrite', (store) => {
      store.put(record)
    })
  }

  async function listMessages(conversationId: string) {
    return withStore<any[]>(MESSAGES, 'readonly', (store) => {
      const index = store.index('conversationId')
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

  async function saveUiState(conversationId: string, state: any) {
    await withStore<void>(UI_STATES, 'readwrite', (store) => {
      store.put({ conversationId, ...state })
    })
  }

  async function getUiState(conversationId: string) {
    return withStore<any | null>(UI_STATES, 'readonly', (store) => {
      return new Promise<any | null>((resolve, reject) => {
        const req = store.get(conversationId)
        req.onsuccess = () => resolve(req.result || null)
        req.onerror = () => reject(req.error)
      })
    })
  }

  return {
    upsertConversation,
    getAllConversations,
    deleteConversationLocal,
    putMessage,
    listMessages,
    saveUiState,
    getUiState,
  }
}
