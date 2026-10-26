import { computed, onScopeDispose, ref, watch } from 'vue'
import axios from 'axios'

const validPagePayload = (data) => data && typeof data === 'object'
  && Array.isArray(data.items) && data.items.every(item => item && typeof item === 'object' && !('content' in item))
  && Number.isInteger(data.total) && data.total >= 0
  && Number.isInteger(data.page) && data.page >= 1
  && Number.isInteger(data.page_size) && data.page_size >= 1 && data.page_size <= 50
  && Array.isArray(data.categories) && data.categories.every(category => typeof category === 'string')

export function useArticleCatalog({ endpoint, client = axios, pageSize = 12, debounceMs = 300, initialSort = 'newest' }) {
  const items = ref([])
  const total = ref(0)
  const categories = ref([])
  const page = ref(1)
  const query = ref('')
  const category = ref('全部')
  const sort = ref(initialSort)
  const loading = ref(false)
  const error = ref(false)
  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
  let timer
  let controller
  let version = 0
  let stopped = false
  let suppressPageFetch = false

  const fetchPage = async () => {
    clearTimeout(timer)
    const requestVersion = ++version
    controller?.abort()
    controller = new AbortController()
    const request = controller
    loading.value = true
    error.value = false
    items.value = []
    try {
      const response = await client.get(endpoint, { params: {
        page: page.value, page_size: pageSize, q: Array.from(query.value.trim()).slice(0, 100).join(''),
        category: category.value === '全部' ? '' : Array.from(category.value).slice(0, 50).join(''),
        sort: sort.value === 'most-read' ? 'most-read' : 'newest'
      }, signal: request.signal, timeout: 15000 })
      if (stopped || requestVersion !== version || request.signal.aborted) return
      const data = response?.data
      if (!validPagePayload(data) || data.page_size !== pageSize || data.items.length > pageSize || data.items.length > data.total
        || data.page > Math.max(1, Math.ceil(data.total / data.page_size))
        || data.categories.some(value => !value.trim() || Array.from(value).length > 50)) throw new Error('invalid-article-page')
      categories.value = [...new Set(data.categories)].sort((a, b) => a.localeCompare(b, 'zh-CN'))
      if (category.value !== '全部' && !categories.value.includes(category.value)) {
        suppressPageFetch = true
        category.value = '全部'
        page.value = 1
        suppressPageFetch = false
        await fetchPage()
        return
      }
      suppressPageFetch = true
      page.value = data.page
      suppressPageFetch = false
      total.value = data.total
      items.value = data.items.map(item => ({ ...item, views: Number.isFinite(Number(item.views)) ? Math.max(0, Number(item.views)) : 0 }))
    } catch {
      if (!stopped && requestVersion === version && !request.signal.aborted) error.value = true
    } finally {
      if (!stopped && requestVersion === version && !request.signal.aborted) loading.value = false
    }
  }

  const stopPageWatch = watch(page, () => { if (!suppressPageFetch) fetchPage() }, { flush: 'sync' })
  const stopFilterWatch = watch([category, sort], () => {
    if (suppressPageFetch) return
    if (page.value !== 1) {
      suppressPageFetch = true
      page.value = 1
      suppressPageFetch = false
    }
    fetchPage()
  }, { flush: 'sync' })
  const stopSearch = watch(query, () => {
    if (page.value !== 1) {
      suppressPageFetch = true
      page.value = 1
      suppressPageFetch = false
    }
    clearTimeout(timer)
    controller?.abort()
    const requestVersion = ++version
    loading.value = true
    error.value = false
    items.value = []
    timer = setTimeout(() => { if (!stopped && requestVersion === version) fetchPage() }, debounceMs)
  }, { flush: 'sync' })

  const setPage = (value) => { page.value = Math.max(1, Math.floor(Number(value) || 1)) }
  const resetFilters = () => { query.value = ''; category.value = '全部'; page.value = 1 }
  const stop = () => {
    stopped = true
    clearTimeout(timer)
    controller?.abort()
    version++
    stopPageWatch()
    stopFilterWatch()
    stopSearch()
  }
  onScopeDispose(stop)

  return { items, total, categories, page, query, category, sort, loading, error, pageCount, fetchPage, setPage, resetFilters, stop }
}
