export type ReportSnapshot = {
  updated_at?: string
  msgCount?: number
}

export type RenderStrategy = 'skip' | 'incremental' | 'full'

export function computeRenderStrategy(
  prev: ReportSnapshot | null,
  next: ReportSnapshot,
): RenderStrategy {
  if (
    prev &&
    prev.updated_at === next.updated_at &&
    Number(prev.msgCount || 0) === Number(next.msgCount || 0)
  ) {
    return 'skip'
  }
  const delta = Math.max(0, Number(next.msgCount || 0) - Number(prev?.msgCount || 0))
  if (prev && delta > 0 && delta <= 80) return 'incremental'
  return 'full'
}

export function parseSseBlocks(raw: string) {
  const chunks = raw.split('\n\n')
  const rest = chunks.pop() || ''
  const events = chunks
    .map((block) => {
      const lines = block.split('\n')
      const eventLine = lines.find((l) => l.startsWith('event:'))
      const dataLine = lines.find((l) => l.startsWith('data:'))
      if (!dataLine) return null
      const event = eventLine?.replace('event:', '').trim() || 'step'
      const data = JSON.parse(dataLine.replace('data:', '').trim())
      return { event, data }
    })
    .filter(Boolean)
  return { events, rest }
}

export type StepWarningPayload = {
  status?: string
  elapsedMs?: number | string
}

export function shouldWarnForStep(payload: StepWarningPayload | null | undefined) {
  return payload?.status === 'degraded' || Number(payload?.elapsedMs || 0) > 30000
}

export function getReconnectDelay(retry: number, maxRetry = 2) {
  if (retry >= maxRetry) return null
  return (retry + 1) * 1000
}
