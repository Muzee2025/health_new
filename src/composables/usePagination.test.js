import { describe, expect, it } from 'vitest'
import { computed, ref } from 'vue'
import { usePagination } from './usePagination'

const rows = (n) => Array.from({ length: n }, (_, i) => i + 1)

describe('usePagination', () => {
  it('defaults to page 1 and a page size of 10', () => {
    const { currentPage, pageSize, pageSizes } = usePagination(computed(() => rows(25)))
    expect(currentPage.value).toBe(1)
    expect(pageSize.value).toBe(10)
    expect(pageSizes).toEqual([10, 20, 50])
  })

  it('returns the rows for the current page', () => {
    const { currentPage, paginatedData } = usePagination(computed(() => rows(25)))
    expect(paginatedData.value).toEqual(rows(10))

    currentPage.value = 2
    expect(paginatedData.value).toEqual([11, 12, 13, 14, 15, 16, 17, 18, 19, 20])

    currentPage.value = 3
    expect(paginatedData.value).toEqual([21, 22, 23, 24, 25])
  })

  it('follows a page size change', () => {
    const { pageSize, paginatedData } = usePagination(computed(() => rows(25)))
    pageSize.value = 20
    expect(paginatedData.value).toHaveLength(20)
  })

  it('re-slices when the filtered rows change', () => {
    const source = ref(rows(25))
    const { currentPage, paginatedData } = usePagination(computed(() => source.value))

    currentPage.value = 2
    expect(paginatedData.value).toEqual([11, 12, 13, 14, 15, 16, 17, 18, 19, 20])

    source.value = rows(12)
    expect(paginatedData.value).toEqual([11, 12])
  })

  it('returns an empty page past the end instead of throwing', () => {
    const { currentPage, paginatedData } = usePagination(computed(() => rows(5)))
    currentPage.value = 99
    expect(paginatedData.value).toEqual([])
  })

  it('keeps independent state per call', () => {
    const a = usePagination(computed(() => rows(25)))
    const b = usePagination(computed(() => rows(25)))

    a.currentPage.value = 3
    expect(a.currentPage.value).toBe(3)
    expect(b.currentPage.value).toBe(1)
  })
})
