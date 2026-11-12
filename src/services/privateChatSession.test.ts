import { describe, expect, it } from 'vitest'
import { createPrivateChatSession } from './privateChatSession'

describe('private chat session isolation', () => {
  it('uses different non-token database names and blocks the previous identity after a switch', async () => {
    let identity = 'synthetic-session-A'
    const a = createPrivateChatSession(identity, () => identity)
    const nameA = await a.databaseName()
    identity = 'synthetic-session-B'
    const b = createPrivateChatSession(identity, () => identity)
    const nameB = await b.databaseName()
    expect(nameA).not.toBe(nameB)
    expect(nameA).not.toContain('synthetic-session-A')
    expect(nameB).toMatch(/^health_new_chat_v2_[a-f0-9]{64}$/)
    await expect(a.databaseName()).rejects.toMatchObject({ name: 'AbortError' })
    expect(b.isActive()).toBe(true)
  })

  it('rejects a late response before a caller can render or persist it', async () => {
    let identity = 'synthetic-session-A'
    const a = createPrivateChatSession(identity, () => identity)
    let complete!: (value: string) => void
    const result = a.run(
      () =>
        new Promise<string>((resolve) => {
          complete = resolve
        }),
    )
    identity = 'synthetic-session-B'
    complete('private-A-result')
    await expect(result).rejects.toMatchObject({ name: 'AbortError' })
    const loggedOut = createPrivateChatSession('', () => '')
    await expect(loggedOut.databaseName()).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('blocks requests and cache operations after component cancellation', async () => {
    const controller = new AbortController()
    const session = createPrivateChatSession('synthetic-A', () => 'synthetic-A', controller.signal)
    controller.abort()
    let started = false
    await expect(
      session.run(async () => {
        started = true
        return 'private'
      }),
    ).rejects.toMatchObject({ name: 'AbortError' })
    expect(started).toBe(false)
  })
})
