import { describe, expect, it, vi } from "vitest"
import {
  __getReportCacheSizeForTest,
  getReportFromCache,
  invalidateReportCache,
  setReportToCache,
} from "./reportCache"

describe("reportCache", () => {
  it("can set and get cache", () => {
    invalidateReportCache()
    setReportToCache("k1", { ok: true })
    expect(getReportFromCache("k1")).toEqual({ ok: true })
  })

  it("expires by ttl", () => {
    vi.useFakeTimers()
    invalidateReportCache()
    setReportToCache("k2", { value: 1 }, 1000)
    vi.advanceTimersByTime(1001)
    expect(getReportFromCache("k2")).toBeNull()
    vi.useRealTimers()
  })

  it("supports invalidating single key and all", () => {
    invalidateReportCache()
    setReportToCache("k3", 1)
    setReportToCache("k4", 2)
    invalidateReportCache("k3")
    expect(getReportFromCache("k3")).toBeNull()
    expect(getReportFromCache("k4")).toBe(2)
    invalidateReportCache()
    expect(__getReportCacheSizeForTest()).toBe(0)
  })

  it("evicts least recently used item when over capacity", () => {
    invalidateReportCache()
    for (let i = 0; i < 52; i += 1) {
      setReportToCache(`k-${i}`, i)
    }
    expect(__getReportCacheSizeForTest()).toBeLessThanOrEqual(50)
    expect(getReportFromCache("k-0")).toBeNull()
  })
})
