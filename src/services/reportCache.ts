const DEFAULT_TTL_MS = 5 * 60 * 1000
const MAX_CACHE_SIZE = 50

type CacheEntry<T> = {
  data: T
  expiresAt: number
}

const cacheStore = new Map<string, CacheEntry<unknown>>()

function touchKey(key: string) {
  const found = cacheStore.get(key)
  if (!found) return
  cacheStore.delete(key)
  cacheStore.set(key, found)
}

function ensureCapacity() {
  if (cacheStore.size < MAX_CACHE_SIZE) return
  const firstKey = cacheStore.keys().next().value
  if (firstKey) {
    cacheStore.delete(firstKey)
  }
}

export function getReportFromCache<T>(key: string): T | null {
  const hit = cacheStore.get(key)
  if (!hit) return null
  if (Date.now() > hit.expiresAt) {
    cacheStore.delete(key)
    return null
  }
  touchKey(key)
  return hit.data as T
}

export function setReportToCache<T>(key: string, data: T, ttlMs: number = DEFAULT_TTL_MS) {
  if (!key) return
  ensureCapacity()
  cacheStore.set(key, {
    data,
    expiresAt: Date.now() + Math.max(1000, ttlMs),
  })
}

export function invalidateReportCache(key?: string) {
  if (!key) {
    cacheStore.clear()
    return
  }
  cacheStore.delete(key)
}

export function __getReportCacheSizeForTest() {
  return cacheStore.size
}
