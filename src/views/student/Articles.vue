<template>
  <div ref="pageRoot" class="articles business-page business-page--reading">
    <el-card class="business-card">
      <header class="header-wrapper flex-between mb-20 business-page__header">
        <h2 class="page-title">心理科普精选</h2>
        <div class="article-filters">
          <el-input
            v-model="searchQuery"
            class="article-search"
            maxlength="100"
            clearable
            aria-label="搜索文章标题、摘要或来源"
            placeholder="搜索标题、摘要或来源"
          />
          <el-select v-model="sortOrder" aria-label="文章排序">
            <el-option label="最新发布" value="newest" />
            <el-option label="阅读最多" value="most-read" />
          </el-select>
        </div>
        <div class="category-filter">
          <el-radio-group v-model="selectedCategory" size="default" aria-label="按分类筛选文章">
            <el-radio-button value="全部">全部</el-radio-button>
            <el-radio-button v-for="cat in categories" :key="cat" :value="cat">{{
              cat
            }}</el-radio-button>
          </el-radio-group>
        </div>
      </header>
      <el-alert
        v-if="loadError"
        type="error"
        :closable="false"
        show-icon
        title="文章暂时无法加载，请检查网络后重试。"
      >
        <el-button link type="primary" @click="fetchArticles">重新加载</el-button>
      </el-alert>
      <div
        v-if="loading && !loadError"
        v-loading="loading"
        class="article-loading"
        role="status"
        aria-label="正在加载文章"
      />

      <el-row v-if="!loading && !loadError && articles.length" :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="article in articles" :key="article.id">
          <el-card
            shadow="hover"
            class="article-card"
            role="link"
            tabindex="0"
            :aria-label="`阅读文章：${article.title}`"
            @click="showArticle(article)"
            @keydown.enter.prevent="showArticle(article)"
            @keydown.space.prevent="showArticle(article)"
            :body-style="{ padding: '0px' }"
          >
            <div class="image-wrapper">
              <img
                :src="article.cover_url || articleFallback"
                class="image"
                :alt="article.title"
                width="300"
                height="200"
                loading="lazy"
                @error="handleImageError"
              />
              <el-tag v-if="article.category" class="category-tag" effect="dark" size="small">{{
                article.category
              }}</el-tag>
            </div>
            <div style="padding: 14px">
              <h3 class="article-title">{{ article.title }}</h3>
              <p class="summary">{{ article.summary }}</p>
              <div class="bottom">
                <span class="source-tag text-xs text-gray-500" v-if="article.source">
                  <el-icon><LibraryIcon name="collection" /></el-icon> {{ article.source }}
                </span>
                <span class="views text-xs text-gray-500">
                  <el-icon><LibraryIcon name="view" /></el-icon> {{ article.views || 0 }}
                </span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <LibraryEmpty
        v-if="
          !loading && !loadError && !total && selectedCategory === '全部' && !searchQuery.trim()
        "
        description="暂时还没有文章"
      />
      <div v-else-if="!loading && !loadError && !total" class="empty-results">
        <LibraryEmpty description="没有找到符合条件的文章" />
        <el-button v-if="selectedCategory !== '全部' || searchQuery" @click="clearFilters"
          >清空筛选</el-button
        >
      </div>
      <PagedFooter
        v-if="!loading && !loadError && total"
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        :hide-on-single-page="true"
        align="center"
        aria-label="文章分页"
        @change="scrollToArticles"
      />
    </el-card>
  </div>
</template>

<script setup>
import { getVisualAsset } from '../../design/asset-registry'
const articleFallback = getVisualAsset('articleFallback').url

import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElAlert,
  ElButton,
  ElCard,
  ElInput,
  ElSelect,
  ElOption,
  ElRadioGroup,
  ElRadioButton,
  ElRow,
  ElCol,
  ElTag,
  ElIcon,
} from 'element-plus'
import { useArticleCatalog } from '../../composables/useArticleCatalog'
import PagedFooter from '../../components/PagedFooter.vue'

const router = useRouter()

const pageSize = 12
const catalog = useArticleCatalog({ endpoint: '/api/student/articles/page', pageSize })
const {
  items: articles,
  total,
  categories,
  category: selectedCategory,
  query: searchQuery,
  sort: sortOrder,
  page,
  loading,
  error: loadError,
  fetchPage: fetchArticles,
  resetFilters,
} = catalog
const pageRoot = ref(null)
const scrollToArticles = () => nextTick(() => pageRoot.value?.scrollIntoView({ block: 'start' }))

onMounted(() => {
  fetchArticles()
  window.addEventListener('article-view-updated', handleArticleViewUpdated)
})

onBeforeUnmount(() => {
  window.removeEventListener('article-view-updated', handleArticleViewUpdated)
})
const clearFilters = () => resetFilters()

const handleArticleViewUpdated = (event) => {
  const detail = event?.detail || {}
  const articleId = Number(detail.articleId || 0)
  const views = Number(detail.views || 0)
  if (!articleId || !Number.isFinite(views) || views < 0) return
  const updateRows = (rows) =>
    rows.map((item) => {
      if (Number(item.id) !== articleId) return item
      return { ...item, views }
    })
  articles.value = updateRows(articles.value)
  if (sortOrder.value === 'most-read') fetchArticles()
}

const showArticle = (article) => {
  router.push(`/article/${article.id}`)
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
.article-filters {
  display: flex;
  align-items: center;
  gap: 10px;
}
.article-search {
  width: min(280px, 42vw);
}
.article-filters :deep(.el-select) {
  width: 132px;
}
.mb-20 {
  margin-bottom: 20px;
}
.mr-10 {
  margin-right: 10px;
}
.text-xs {
  font-size: 12px;
}
.text-gray-500 {
  color: var(--text-secondary);
}
.text-blue-500 {
  color: var(--brand-600);
}
.cursor-pointer {
  cursor: pointer;
}

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
.article-card:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 3px;
}
.article-loading {
  min-height: 180px;
}
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
.empty-results {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.source-tag,
.views {
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
  .header-wrapper {
    align-items: stretch;
  }
  .article-filters {
    width: 100%;
  }
  .article-search {
    flex: 1;
    min-width: 0;
  }
  .category-filter {
    max-width: 100%;
    overflow-x: auto;
  }
  .category-filter :deep(.el-radio-group) {
    display: inline-flex;
    flex-wrap: nowrap;
  }
  .article-card:hover {
    transform: none;
  }
}
</style>
