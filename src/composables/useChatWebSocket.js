import { ref } from 'vue'

const RECONNECT_DELAY_MS = 5000
const WARNING_PROCESSED_FALLBACK = '老师已收到您的预警信息，正在处理中，请保持通讯畅通。'

export function useChatWebSocket({
  chatSession,
  getStoredToken,
  axios,
  ElMessage,
  WebSocketImpl,
  locationHref,
  schedule = globalThis.setTimeout,
  cancel = globalThis.clearTimeout,
}) {
  const socket = ref(null)
  let reconnectTimer = null
  let isClosed = false

  const connect = () => {
    const token = getStoredToken()
    if (isClosed || !token || !chatSession.isActive()) return

    const wsUrl = new URL(
      axios.getUri({ url: '/api/ws' }),
      locationHref || globalThis.window.location.href,
    )
    wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    const WebSocketConstructor = WebSocketImpl || globalThis.WebSocket
    const currentSocket = new WebSocketConstructor(wsUrl.href, ['access_token', token])
    socket.value = currentSocket

    currentSocket.onopen = () => {
      console.log('Student WS connected')
    }

    currentSocket.onmessage = (event) => {
      if (!chatSession.isActive()) return
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'warning_processed') {
          ElMessage.success({
            message: msg.data.message || WARNING_PROCESSED_FALLBACK,
            duration: 10000,
            showClose: true,
          })
        }
      } catch {
        if (!chatSession.isActive()) return
      }
    }

    currentSocket.onclose = (event) => {
      if (!isClosed && chatSession.isActive() && event.code !== 1008) {
        if (reconnectTimer !== null) cancel(reconnectTimer)
        reconnectTimer = schedule(() => {
          reconnectTimer = null
          connect()
        }, RECONNECT_DELAY_MS)
      }
    }
  }

  const close = () => {
    isClosed = true
    if (reconnectTimer !== null) {
      cancel(reconnectTimer)
      reconnectTimer = null
    }
    if (socket.value) {
      socket.value.close()
      socket.value = null
    }
  }

  return { connect, close, socket }
}
