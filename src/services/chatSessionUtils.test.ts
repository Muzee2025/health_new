import { describe, expect, it } from "vitest"
import { buildNewConversation, buildUiStatePayload, filterVisibleSessions } from "./chatSessionUtils"

describe("chatSessionUtils", () => {
  it("creates new conversation record", () => {
    const rec = buildNewConversation("c1", "counseling", "2026-01-01T00:00:00.000Z")
    expect(rec.id).toBe("c1")
    expect(rec.mode).toBe("counseling")
    expect(rec.title).toBe("新对话")
    expect(rec.archived).toBe(false)
  })

  it("filters sessions by archive and query", () => {
    const rows = [
      { id: "1", title: "学习压力", archived: false },
      { id: "2", title: "人际关系", archived: true },
    ]
    expect(filterVisibleSessions(rows, "", false).map((x) => x.id)).toEqual(["1"])
    expect(filterVisibleSessions(rows, "人际", true).map((x) => x.id)).toEqual(["2"])
  })

  it("builds ui state payload", () => {
    const state = buildUiStatePayload("草稿", 120)
    expect(state.draft).toBe("草稿")
    expect(state.scrollTop).toBe(120)
    expect(typeof state.updatedAt).toBe("string")
  })
})
