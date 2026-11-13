import { computed, ref } from 'vue'

/**
 * Client-side pagination shared by the teacher list screens.
 *
 * The three screens (appointments, intervention records, students) all held the
 * same three refs plus the same slice expression. Keeping one copy means a page
 * size default or a boundary fix only has to be made once.
 *
 * @param {import('vue').Ref<Array<unknown>>} filteredData rows for the current filter
 * @param {number} [initialPageSize] rows per page; the screens all use 10
 * @returns {{
 *   currentPage: import('vue').Ref<number>,
 *   pageSize: import('vue').Ref<number>,
 *   pageSizes: number[],
 *   paginatedData: import('vue').ComputedRef<Array<unknown>>,
 * }}
 */
export function usePagination(filteredData, initialPageSize = 10) {
  const currentPage = ref(1)
  const pageSize = ref(initialPageSize)
  const pageSizes = [10, 20, 50]

  const paginatedData = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return filteredData.value.slice(start, start + pageSize.value)
  })

  return { currentPage, pageSize, pageSizes, paginatedData }
}
