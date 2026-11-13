export function parseSsePacket(packet: string): { event: string; data: string } {
  const lines = packet.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  return { event, data: dataLines.join('\n') }
}

export function safeParseJson(text: string, isActive: () => boolean = () => true) {
  try {
    return JSON.parse(text) as unknown
  } catch {
    if (!isActive()) return undefined
    return null
  }
}

export function createTimeoutController(ms: number) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new Error(`timeout:${ms}`)), ms)
  return { controller, timer }
}
