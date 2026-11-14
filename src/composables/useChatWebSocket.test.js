import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatWebSocket } from './useChatWebSocket'

class FakeWebSocket {
  static instances = []

  constructor(url, protocols) {
    this.url = url
    this.protocols = protocols
    this.close = vi.fn()
    FakeWebSocket.instances.push(this)
  }
}

function createHarness({ active = true, token = 'synthetic-token' } = {}) {
  const chatSession = { isActive: vi.fn(() => active) }
  const messages = { success: vi.fn() }
  const axios = { getUri: vi.fn(() => '/api/ws') }
  const websocket = useChatWebSocket({
    chatSession,
    getStoredToken: () => token,
    axios,
    ElMessage: messages,
    WebSocketImpl: FakeWebSocket,
    locationHref: 'https://chat.example.test/student/chat',
  })
  return { websocket, chatSession, messages, axios }
}

beforeEach(() => {
  FakeWebSocket.instances.length = 0
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useChatWebSocket lifecycle contract', () => {
  it('uses the current secure websocket URL and handles processed warnings only for an active session', () => {
    const context = createHarness()
    context.websocket.connect()

    const socket = FakeWebSocket.instances[0]
    expect(socket.url).toBe('wss://chat.example.test/api/ws')
    expect(socket.protocols).toEqual(['access_token', 'synthetic-token'])

    socket.onmessage({
      data: JSON.stringify({ type: 'warning_processed', data: { message: '已收到' } }),
    })
    context.chatSession.isActive.mockReturnValue(false)
    socket.onmessage({
      data: JSON.stringify({ type: 'warning_processed', data: { message: '迟到消息' } }),
    })
    expect(context.messages.success).toHaveBeenCalledExactlyOnceWith({
      message: '已收到',
      duration: 10000,
      showClose: true,
    })
  })

  it('reconnects after an unexpected close but does not reconnect after policy close', () => {
    const context = createHarness()
    context.websocket.connect()
    FakeWebSocket.instances[0].onclose({ code: 1006 })

    vi.advanceTimersByTime(4999)
    expect(FakeWebSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeWebSocket.instances).toHaveLength(2)

    FakeWebSocket.instances[1].onclose({ code: 1008 })
    vi.advanceTimersByTime(5000)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it('clears a pending reconnect and closes the active socket during teardown', () => {
    const context = createHarness()
    context.websocket.connect()
    const socket = FakeWebSocket.instances[0]
    socket.onclose({ code: 1006 })

    context.websocket.close()
    expect(socket.close).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(5000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('does not connect when the session is inactive or the stored token is empty', () => {
    createHarness({ active: false }).websocket.connect()
    createHarness({ token: '' }).websocket.connect()

    expect(FakeWebSocket.instances).toHaveLength(0)
  })
})
