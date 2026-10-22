export function storedSessionToken() {
  const raw = localStorage.getItem('token') || localStorage.getItem('access_token') || ''
  return raw.trim().replace(/^bearer\s+/i, '').trim()
}

/** Client session isolation only. Server authorization remains the security boundary. */
export function createPrivateChatSession(token: string, readToken = storedSessionToken, signal?: AbortSignal) {
  const identity = token.trim().replace(/^bearer\s+/i, '').trim()
  const isActive = () => Boolean(identity) && !signal?.aborted && readToken() === identity
  const assertActive = () => {
    if (!isActive()) throw new DOMException('Chat session changed', 'AbortError')
  }
  let database: Promise<string> | null = null
  return {
    isActive,
    assertActive,
    signal,
    async databaseName() {
      assertActive()
      database ||= crypto.subtle.digest('SHA-256', new TextEncoder().encode(identity)).then(buffer =>
        'health_new_chat_v2_' + Array.from(new Uint8Array(buffer), byte => byte.toString(16).padStart(2, '0')).join(''))
      const name = await database
      assertActive()
      return name
    },
    async run<T>(operation: () => Promise<T>): Promise<T> {
      assertActive()
      const result = await operation()
      assertActive()
      return result
    },
  }
}
