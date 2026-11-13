import { afterEach, describe, expect, it, vi } from 'vitest'
import { createTimeoutController, parseSsePacket, safeParseJson } from './advancedChatStream'

describe('advancedChatStream', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('parses a packet with a default event and joins all data lines', () => {
    expect(parseSsePacket('data: first\ndata: second')).toEqual({
      event: 'message',
      data: 'first\nsecond',
    })
    expect(parseSsePacket('event: phase\ndata: ready')).toEqual({
      event: 'phase',
      data: 'ready',
    })
  })

  it('keeps invalid JSON behavior tied to the active session', () => {
    expect(safeParseJson('{"reply":"ok"}', () => true)).toEqual({ reply: 'ok' })
    expect(safeParseJson('{', () => true)).toBeNull()
    expect(safeParseJson('{', () => false)).toBeUndefined()
  })

  it('aborts when the timeout elapses and returns its timer for cleanup', () => {
    vi.useFakeTimers()
    const { controller, timer } = createTimeoutController(70)

    expect(controller.signal.aborted).toBe(false)
    vi.advanceTimersByTime(70)
    expect(controller.signal.aborted).toBe(true)

    clearTimeout(timer)
  })
})
