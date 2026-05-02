import { describe, expect, it } from "vitest"
import {
  computeRenderStrategy,
  getReconnectDelay,
  parseSseBlocks,
  shouldWarnForStep,
} from "./reportStream"

describe("reportStream", () => {
  it("computes render strategy for skip/incremental/full", () => {
    expect(computeRenderStrategy({ updated_at: "1", msgCount: 10 }, { updated_at: "1", msgCount: 10 })).toBe("skip")
    expect(computeRenderStrategy({ updated_at: "1", msgCount: 10 }, { updated_at: "2", msgCount: 15 })).toBe("incremental")
    expect(computeRenderStrategy({ updated_at: "1", msgCount: 10 }, { updated_at: "2", msgCount: 500 })).toBe("full")
    expect(computeRenderStrategy(null, { updated_at: "2", msgCount: 5 })).toBe("full")
  })

  it("parses SSE blocks and keeps trailing rest", () => {
    const raw = `event: step\ndata: {"step":"风险评级","status":"running"}\n\nevent: done\ndata: {"ok":true}\n\nevent: step\ndata: {"x":1}`
    const { events, rest } = parseSseBlocks(raw)
    expect(events).toHaveLength(2)
    expect(events[0]).toEqual({ event: "step", data: { step: "风险评级", status: "running" } })
    expect(events[1]).toEqual({ event: "done", data: { ok: true } })
    expect(rest).toContain(`event: step`)
  })

  it("flags degraded or timeout steps", () => {
    expect(shouldWarnForStep({ status: "degraded", elapsedMs: 100 })).toBe(true)
    expect(shouldWarnForStep({ status: "done", elapsedMs: 31000 })).toBe(true)
    expect(shouldWarnForStep({ status: "done", elapsedMs: 1000 })).toBe(false)
  })

  it("provides reconnect delay and stop signal", () => {
    expect(getReconnectDelay(0, 3)).toBe(1000)
    expect(getReconnectDelay(1, 3)).toBe(2000)
    expect(getReconnectDelay(2, 3)).toBe(3000)
    expect(getReconnectDelay(3, 3)).toBeNull()
  })
})
