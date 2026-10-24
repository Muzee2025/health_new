<template>
  <div ref="pageRoot" class="articles business-page business-page--reading">
    <el-card class="business-card">
      <header class="header-wrapper flex-between mb-20 business-page__header">
        <h2 class="page-title">心理科普精选</h2>
        <div class="article-filters">
          <el-input
            v-model="searchQuery"
            class="article-search"
            clearable
            aria-label="搜索文章标题、摘要或来源"
            placeholder="搜索标题、摘要或来源"
            @input="page = 1"
          />
          <el-select v-model="sortOrder" aria-label="文章排序" @change="page = 1">
            <el-option label="最新发布" value="newest" />
            <el-option label="阅读最多" value="most-read" />
          </el-select>
        </div>
        <div class="category-filter">
          <el-radio-group v-model="selectedCategory" size="default" aria-label="按分类筛选文章" @change="page = 1">
            <el-radio-button value="全部">全部</el-radio-button>
            <el-radio-button v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</el-radio-button>
          </el-radio-group>
        </div>
      </header>
      <el-alert v-if="loadError" type="error" :closable="false" show-icon title="文章暂时无法加载，请检查网络后重试。">
        <el-button link type="primary" @click="fetchArticles">重新加载</el-button>
      </el-alert>
      <div v-else-if="loading" v-loading="loading" class="article-loading" role="status" aria-label="正在加载文章" />
      
      <el-row v-else-if="articles.length" :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="article in paginatedArticles" :key="article.id">
          <el-card shadow="hover" class="article-card" role="link" tabindex="0" :aria-label="`阅读文章：${article.title}`" @click="showArticle(article)" @keydown.enter.prevent="showArticle(article)" @keydown.space.prevent="showArticle(article)" :body-style="{ padding: '0px' }">
            <div class="image-wrapper">
              <img :src="article.cover_url || articleFallback" class="image" :alt="article.title" width="300" height="200" loading="lazy" @error="handleImageError" />
              <el-tag v-if="article.category" class="category-tag" effect="dark" size="small">{{ article.category }}</el-tag>
            </div>
            <div style="padding: 14px">
              <h3 class="article-title">{{ article.title }}</h3>
              <p class="summary">{{ article.summary }}</p>
              <div class="bottom">
                <span class="source-tag text-xs text-gray-500" v-if="article.source">
                  <el-icon><LibraryIcon name="collection"  /></el-icon> {{ article.source }}
                </span>
                <span class="views text-xs text-gray-500">
                  <el-icon><LibraryIcon name="view"  /></el-icon> {{ article.views || 0 }}
                </span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <LibraryEmpty v-if="!loading && !loadError && !articles.length" description="暂时还没有文章" />
      <div v-else-if="!loading && !loadError && !filteredArticles.length" class="empty-results">
        <LibraryEmpty :description="selectedCategory === '全部' && !searchQuery.trim() ? '暂时还没有文章' : '没有找到符合条件的文章'" />
        <el-button v-if="selectedCategory !== '全部' || searchQuery" @click="clearFilters">清空筛选</el-button>
      </div>
      <div v-if="!loading && !loadError && filteredArticles.length" class="pagination-wrapper">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="filteredArticles.length"
          :pager-count="5"
          layout="total, prev, pager, next"
          :hide-on-single-page="true"
          aria-label="文章分页"
          @current-change="scrollToArticles"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { getVisualAsset } from '../../design/asset-registry'
const articleFallback = getVisualAsset('articleFallback').url

import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElAlert, ElButton, ElCard, ElInput, ElSelect, ElOption, ElRadioGroup, ElRadioButton, ElRow, ElCol, ElTag, ElIcon, ElPagination } from 'element-plus'

const router = useRouter()

const articles = ref([])
const loading = ref(false)
const loadError = ref(false)
const categories = ref([])
const selectedCategory = ref('全部')
const searchQuery = ref('')
const sortOrder = ref('newest')
const page = ref(1)
const pageSize = 12
const pageRoot = ref(null)
const scrollToArticles = () => nextTick(() => pageRoot.value?.scrollIntoView({ block: 'start' }))
const publishedAt = (article) => Date.parse(article.created_at || '') || 0
let articleRequest
const normalizeArticleViews = (rows) => (rows || []).map(item => ({ ...item, views: Number.isFinite(Number(item.views)) ? Math.max(0, Number(item.views)) : 0 }))
const filteredArticles = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase()
  const rows = articles.value.filter((article) => {
    const matchesCategory = selectedCategory.value === '全部' || article.category === selectedCategory.value
    const searchable = [article.title, article.summary, article.source].filter(Boolean).join(' ').toLocaleLowerCase()
    return matchesCategory && (!query || searchable.includes(query))
  })
  return rows.sort((a, b) => sortOrder.value === 'most-read'
    ? b.views - a.views || publishedAt(b) - publishedAt(a)
    : publishedAt(b) - publishedAt(a))
})
const paginatedArticles = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredArticles.value.slice(start, start + pageSize)
})

watch(() => filteredArticles.value.length, (total) => {
  const lastPage = Math.max(1, Math.ceil(total / pageSize))
  if (page.value > lastPage) page.value = lastPage
})

onMounted(() => {
  fetchArticles()
  window.addEventListener('article-view-updated', handleArticleViewUpdated)
})

onBeforeUnmount(() => {
  articleRequest?.abort()
  window.removeEventListener('article-view-updated', handleArticleViewUpdated)
})

const fetchArticles = async () => {
  articleRequest?.abort()
  const request = new AbortController()
  articleRequest = request
  loading.value = true
  loadError.value = false
  try {
    const res = await axios.get('/api/student/articles', { signal: request.signal, timeout: 15000 })
    if (request.signal.aborted) return
    if (!Array.isArray(res.data)) throw new Error('invalid-articles')
    const rows = normalizeArticleViews(res.data)
    articles.value = rows
    
    // Extract unique categories
    const cats = new Set(rows.map(a => a.category).filter(Boolean))
    categories.value = Array.from(cats)
    if (selectedCategory.value !== '全部' && !cats.has(selectedCategory.value)) selectedCategory.value = '全部'
  } catch (error) {
    if (!request.signal.aborted) loadError.value = true
  } finally {
    if (!request.signal.aborted) loading.value = false
  }
}

const clearFilters = () => {
  searchQuery.value = ''
  selectedCategory.value = '全部'
  page.value = 1
}

const handleArticleViewUpdated = (event) => {
  const detail = event?.detail || {}
  const articleId = Number(detail.articleId || 0)
  const views = Number(detail.views || 0)
  if (!articleId || !Number.isFinite(views) || views < 0) return
  const updateRows = (rows) => rows.map((item) => {
    if (Number(item.id) !== articleId) return item
    return { ...item, views }
  })
  articles.value = updateRows(articles.value)
}

const showArticle = (article) => {
  router.push(`/article/${article.id}`)
}

const openSource = (url) => {
  if (url) {
    window.open(url, '_blank')
  }
}

const handleImageError = (e) => {
  e.target.onerror = null
  e.target.src = articleFallback
}
</script>

<style scoped>
.page-title {
  font-size: 24px;
  color: var(--text-primary);
  margin: 0;
}
.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
}
.article-filters { display: flex; align-items: center; gap: 10px; }
.article-search { width: min(280px, 42vw); }
.article-filters :deep(.el-select) { width: 132px; }
.mb-20 { margin-bottom: 20px; }
.mr-10 { margin-right: 10px; }
.text-xs { font-size: 12px; }
.text-gray-500 { color: var(--text-secondary); }
.text-blue-500 { color: var(--brand-600); }
.cursor-pointer { cursor: pointer; }

.article-card {
  cursor: pointer;
  margin-bottom: 20px;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s;
}
.article-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 20px color-mix(in srgb, var(--gray-900) 10%, transparent);
}
.article-card:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 3px; }
.article-loading { min-height: 180px; }
.image-wrapper {
  position: relative;
  width: 100%;
  height: 180px;
}
.image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.category-tag {
  position: absolute;
  top: 10px;
  right: 10px;
  opacity: 0.9;
}
.article-title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
  min-height: 2.8em;
  margin-top: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.summary {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 10px 0;
  height: 38px;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.bottom {
  margin-top: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--surface-warm);
  padding-top: 10px;
}
.empty-results { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.pagination-wrapper { display: flex; justify-content: center; margin-top: 8px; }
.source-tag, .views {
  display: flex;
  align-items: center;
  gap: 4px;
}

.article-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.article-content {
  line-height: 1.8;
  font-size: 16px;
  color: var(--text-primary);
}
:deep(.article-content p) {
  margin-bottom: 1em;
}
:deep(.article-content img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 10px 0;
}
@media (max-width: 600px) {
  .header-wrapper { align-items: stretch; }
  .article-filters { width: 100%; }
  .article-search { flex: 1; min-width: 0; }
  .category-filter { max-width: 100%; overflow-x: auto; }
  .category-filter :deep(.el-radio-group) { display: inline-flex; flex-wrap: nowrap; }
  .article-card:hover { transform: none; }
}
</style>
