import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'
import { useArticleCatalog } from './useArticleCatalog'

const pageData = (overrides = {}) => ({
  items: [{ id: 1, title: '摘要', summary: '内容', views: 2 }],
  total: 1,
  page: 1,
  page_size: 12,
  categories: ['分类'],
  ...overrides,
})
const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}

afterEach(() => vi.useRealTimers())

describe('useArticleCatalog', () => {
  it('debounces search, sends normalized bounded query, and fetches filter changes immediately', async () => {
    vi.useFakeTimers()
    const client = { get: vi.fn().mockResolvedValue({ data: pageData() }) }
    const scope = effectScope()
    const catalog = scope.run(() => useArticleCatalog({ endpoint: '/page', client }))
    catalog.query.value = '  hello  '
    expect(client.get).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(299)
    expect(client.get).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    await flush()
    expect(client.get).toHaveBeenCalledTimes(1)
    expect(client.get.mock.calls[0][1].params.q).toBe('hello')
    catalog.sort.value = 'most-read'
    await flush()
    expect(client.get).toHaveBeenCalledTimes(2)
    expect(client.get.mock.calls[1][1].params.sort).toBe('most-read')
    scope.stop()
  })

  it('ignores late responses from superseded requests and clamps page from server without refetch loop', async () => {
    const pending = []
    const client = {
      get: vi.fn((url, config) => new Promise((resolve) => pending.push({ resolve, config }))),
    }
    const scope = effectScope()
    const catalog = scope.run(() => useArticleCatalog({ endpoint: '/page', client }))
    catalog.fetchPage()
    catalog.setPage(4)
    expect(client.get).toHaveBeenCalledTimes(2)
    pending[1].resolve({ data: pageData({ items: [], total: 25, page: 3 }) })
    await flush()
    expect(catalog.page.value).toBe(3)
    expect(client.get).toHaveBeenCalledTimes(2)
    pending[0].resolve({ data: pageData({ items: [{ id: 9, title: '过期' }] }) })
    await flush()
    expect(catalog.items.value).toEqual([])
    expect(catalog.total.value).toBe(25)
    scope.stop()
  })

  it('resets page on category and sort changes with one immediate request each', async () => {
    const client = {
      get: vi
        .fn()
        .mockImplementation((url, config) =>
          Promise.resolve({
            data: pageData({ total: 50, page: config.params.page, categories: ['分类', '新分类'] }),
          }),
        ),
    }
    const scope = effectScope()
    const catalog = scope.run(() => useArticleCatalog({ endpoint: '/page', client }))
    catalog.setPage(3)
    await flush()
    expect(catalog.page.value).toBe(3)
    catalog.category.value = '新分类'
    await flush()
    expect(catalog.page.value).toBe(1)
    expect(client.get).toHaveBeenCalledTimes(2)
    expect(client.get.mock.calls[1][1].params).toMatchObject({ page: 1, category: '新分类' })
    catalog.setPage(3)
    await flush()
    catalog.sort.value = 'most-read'
    await flush()
    expect(catalog.page.value).toBe(1)
    expect(client.get).toHaveBeenCalledTimes(4)
    expect(client.get.mock.calls[3][1].params).toMatchObject({ page: 1, sort: 'most-read' })
    scope.stop()
  })

  it('resets a category missing from the server category set and refreshes once', async () => {
    const client = {
      get: vi
        .fn()
        .mockResolvedValueOnce({ data: pageData({ items: [], total: 0, categories: ['分类'] }) })
        .mockResolvedValueOnce({ data: pageData({ categories: ['分类'] }) }),
    }
    const scope = effectScope()
    const catalog = scope.run(() => useArticleCatalog({ endpoint: '/page', client }))
    catalog.category.value = '已失效分类'
    await flush()
    expect(client.get).toHaveBeenCalledTimes(2)
    expect(client.get.mock.calls[0][1].params.category).toBe('已失效分类')
    expect(client.get.mock.calls[1][1].params).toMatchObject({ page: 1, category: '' })
    expect(catalog.category.value).toBe('全部')
    expect(catalog.items.value).toHaveLength(1)
    scope.stop()
  })

  it('rejects malformed responses without exposing stale rows and aborts on scope disposal', async () => {
    const client = {
      get: vi
        .fn()
        .mockResolvedValueOnce({
          data: pageData({ items: [{ id: 1, content: 'unexpected body' }] }),
        })
        .mockResolvedValueOnce({ data: pageData() }),
    }
    const scope = effectScope()
    const catalog = scope.run(() => useArticleCatalog({ endpoint: '/page', client }))
    await catalog.fetchPage()
    expect(catalog.error.value).toBe(true)
    expect(catalog.items.value).toEqual([])
    await catalog.fetchPage()
    expect(catalog.items.value).toHaveLength(1)
    catalog.setPage(2)
    const signal = client.get.mock.calls.at(-1)[1].signal
    scope.stop()
    expect(signal.aborted).toBe(true)
  })
})
