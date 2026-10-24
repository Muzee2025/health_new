<template>
  <div class="articles business-page business-page--reading">
    <el-card class="business-card">
      <header class="header-wrapper flex-between mb-20 business-page__header">
        <h2 class="page-title">心理科普精选</h2>
        <div class="category-filter">
          <el-radio-group v-model="selectedCategory" size="default" aria-label="按分类筛选文章" @change="filterArticles">
            <el-radio-button value="全部">全部</el-radio-button>
            <el-radio-button v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</el-radio-button>
          </el-radio-group>
        </div>
      </header>
      <el-alert v-if="loadError" type="error" :closable="false" show-icon title="文章暂时无法加载，请检查网络后重试。">
        <el-button link type="primary" @click="fetchArticles">重新加载</el-button>
      </el-alert>
      <div v-else-if="loading" v-loading="loading" class="article-loading" role="status" aria-label="正在加载文章" />
      
      <el-row v-else :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="article in filteredArticles" :key="article.id">
          <el-card shadow="hover" class="article-card" role="link" tabindex="0" :aria-label="`阅读文章：${article.title}`" @click="showArticle(article)" @keydown.enter.prevent="showArticle(article)" @keydown.space.prevent="showArticle(article)" :body-style="{ padding: '0px' }">
            <div class="image-wrapper">
              <img :src="article.cover_url || articleFallback" class="image" :alt="article.title" width="300" height="200" @error="handleImageError" />
              <el-tag v-if="article.category" class="category-tag" effect="dark" size="small">{{ article.category }}</el-tag>
            </div>
            <div style="padding: 14px">
              <h3 class="text-truncate">{{ article.title }}</h3>
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
      
      <LibraryEmpty v-if="!loading && !loadError && filteredArticles.length === 0" description="暂无该分类的文章" />
    </el-card>
  </div>
</template>

<script setup>
import { getVisualAsset } from '../../design/asset-registry'
const articleFallback = getVisualAsset('articleFallback').url

import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElAlert, ElButton, ElCard, ElRadioGroup, ElRadioButton, ElRow, ElCol, ElTag, ElIcon } from 'element-plus'

const router = useRouter()

const articles = ref([])
const loading = ref(false)
const loadError = ref(false)
const filteredArticles = ref([])
const categories = ref([])
const selectedCategory = ref('全部')
const normalizeArticleViews = (rows) => (rows || []).map(item => ({ ...item, views: Number.isFinite(Number(item.views)) ? Math.max(0, Number(item.views)) : 0 }))

onMounted(() => {
  fetchArticles()
  window.addEventListener('article-view-updated', handleArticleViewUpdated)
})

onBeforeUnmount(() => {
  window.removeEventListener('article-view-updated', handleArticleViewUpdated)
})

const fetchArticles = async () => {
  loading.value = true
  loadError.value = false
  try {
    const res = await axios.get('/api/student/articles')
    const rows = normalizeArticleViews(res.data)
    articles.value = rows
    filteredArticles.value = rows
    
    // Extract unique categories
    const cats = new Set(rows.map(a => a.category).filter(Boolean))
    categories.value = Array.from(cats)
  } catch (error) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

const filterArticles = () => {
  if (selectedCategory.value === '全部') {
    filteredArticles.value = articles.value
  } else {
    filteredArticles.value = articles.value.filter(a => a.category === selectedCategory.value)
  }
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
  filteredArticles.value = updateRows(filteredArticles.value)
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
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  .category-filter { max-width: 100%; overflow-x: auto; }
  .category-filter :deep(.el-radio-group) { display: inline-flex; flex-wrap: nowrap; }
  .article-card:hover { transform: none; }
}
</style>
