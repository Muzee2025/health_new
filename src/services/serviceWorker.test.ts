import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

describe('private report service worker retirement', () => {
  it('deletes only the retired report cache and leaves private requests on the network', async () => {
    const listeners: Record<string, (event: { waitUntil: (work: Promise<unknown>) => void }) => void> = {}
    const deleted: string[] = []
    let skipped = false
    let claimed = false
    runInNewContext(readFileSync(new URL('../../public/sw.js', import.meta.url), 'utf8'), {
      self: {
        addEventListener: (name: string, callback: typeof listeners[string]) => { listeners[name] = callback },
        skipWaiting: async () => { skipped = true },
        clients: { claim: async () => { claimed = true } },
      },
      caches: { delete: async (name: string) => { deleted.push(name); return true } },
    })
    const pending: Promise<unknown>[] = []
    const event = { waitUntil: (work: Promise<unknown>) => { pending.push(work) } }
    listeners.install(event)
    listeners.activate(event)
    await Promise.all(pending)
    expect(skipped).toBe(true)
    expect(claimed).toBe(true)
    expect(deleted).toEqual(['report-api-cache-v1'])
    // No fetch listener can replay identity A's report for identity B.
    expect(listeners.fetch).toBeUndefined()
  })
})
