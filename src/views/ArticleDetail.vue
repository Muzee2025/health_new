<template>
  <div class="article-detail-container" v-if="article">
    <div class="header-card">
      <el-page-header @back="goBack" title="返回" class="page-header">
        <template #content>
          <span class="header-title">文章详情</span>
        </template>
      </el-page-header>
    </div>
    
    <div class="content-card">
      <h1 class="article-title">{{ article.title }}</h1>
      <div class="article-meta">
        <span>分类：<el-tag size="small">{{ article.category || '心理科普' }}</el-tag></span>
        <span v-if="article.source">来源：{{ article.source }}</span>
        <span>阅读量：{{ article.views }}</span>
        <span>发布时间：{{ formatDate(article.created_at) }}</span>
      </div>
      
      <div v-if="article.cover_url" class="article-cover-wrapper">
        <img :src="article.cover_url" class="article-cover" :alt="article.title" />
      </div>
      
      <div class="article-content" v-html="safeArticleContent" @click="handleArticleContentClick"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import DOMPurify from 'dompurify'
import { downloadArticleDocument } from '../utils/articleDocuments'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const handleArticleContentClick = async (event) => {
  try { await downloadArticleDocument(event) } catch { ElMessage.error('附件下载失败，请重新登录或稍后重试') }
}
const route = useRoute()
const router = useRouter()
const article = ref(null)
const safeArticleContent = computed(() => DOMPurify.sanitize(article.value?.content || '', { USE_PROFILES: { html: true } }))
const VIEW_DEDUP_WINDOW_MS = 5 * 60 * 1000
const VIEW_RETRY_QUEUE_KEY = 'article_view_retry_queue_v1'
let retryTimer = null

const goBack = () => {
  router.back()
}

const getViewerId = () => {
  try {
    const rawUser = localStorage.getItem('user')
    if (rawUser) {
      const user = JSON.parse(rawUser)
      if (user?.id) return `u_${user.id}`
      if (user?.username) return `u_${user.username}`
    }
  } catch {
    // ignore parse error
  }
  let deviceId = localStorage.getItem('device_fingerprint')
  if (!deviceId) {
    deviceId = `d_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`
    localStorage.setItem('device_fingerprint', deviceId)
  }
  return deviceId
}

const getDedupKey = (articleId, viewerId) => `article_view_dedup_${viewerId}_${articleId}`

const shouldSkipTrack = (articleId, viewerId) => {
  const key = getDedupKey(articleId, viewerId)
  const lastTs = Number(localStorage.getItem(key) || 0)
  const now = Date.now()
  if (lastTs && now - lastTs < VIEW_DEDUP_WINDOW_MS) return true
  localStorage.setItem(key, String(now))
  return false
}

const readRetryQueue = () => {
  try {
    const raw = localStorage.getItem(VIEW_RETRY_QUEUE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const writeRetryQueue = (queue) => {
  localStorage.setItem(VIEW_RETRY_QUEUE_KEY, JSON.stringify(queue))
}

const enqueueRetryTask = (task) => {
  const queue = readRetryQueue()
  const deduped = queue.filter((x) => !(Number(x.articleId) === Number(task.articleId) && String(x.viewerId) === String(task.viewerId)))
  deduped.push(task)
  writeRetryQueue(deduped)
}

const dispatchArticleViewUpdated = (articleId, views) => {
  window.dispatchEvent(new CustomEvent('article-view-updated', { detail: { articleId, views } }))
}

const flushRetryQueue = async () => {
  const queue = readRetryQueue()
  if (!queue.length) return
  const [task, ...rest] = queue
  try {
    const res = await axios.post(`/api/student/articles/${task.articleId}/view`, { viewer_id: task.viewerId }, { timeout: 5000 })
    const nextViews = Number(res?.data?.views || 0)
    if (article.value && Number(article.value.id) === Number(task.articleId) && Number.isFinite(nextViews)) {
      article.value.views = Math.max(0, nextViews)
    }
    dispatchArticleViewUpdated(task.articleId, Math.max(0, nextViews))
    writeRetryQueue(rest)
  } catch {
    const retryCount = Number(task.retryCount || 0) + 1
    if (retryCount >= 5) {
      writeRetryQueue(rest)
      return
    }
    writeRetryQueue([{ ...task, retryCount }, ...rest])
  }
  if (retryTimer) clearTimeout(retryTimer)
  retryTimer = setTimeout(flushRetryQueue, 2000)
}

const trackArticleView = async (articleId) => {
  const viewerId = getViewerId()
  if (shouldSkipTrack(articleId, viewerId)) return
  try {
    const res = await axios.post(`/api/student/articles/${articleId}/view`, { viewer_id: viewerId }, { timeout: 5000 })
    const nextViews = Number(res?.data?.views || 0)
    if (Number.isFinite(nextViews) && article.value) {
      const syncedViews = Math.max(0, nextViews)
      article.value.views = syncedViews
      dispatchArticleViewUpdated(articleId, syncedViews)
    }
  } catch {
    enqueueRetryTask({ articleId, viewerId, retryCount: 0, createdAt: Date.now() })
    if (retryTimer) clearTimeout(retryTimer)
    retryTimer = setTimeout(flushRetryQueue, 1500)
  }
}

const fetchArticle = async () => {
  const id = Number(route.params.id)
  try {
    const res = await axios.get(`/api/student/articles/${id}`)
    article.value = res.data
    article.value.views = Math.max(0, Number(article.value.views) || 0)
    await trackArticleView(id)
  } catch (error) {
    ElMessage.error('获取文章失败')
  }
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return d.toLocaleString()
}

onMounted(() => {
  flushRetryQueue()
  fetchArticle()
})

onBeforeUnmount(() => {
  if (retryTimer) clearTimeout(retryTimer)
})
</script>

<style scoped>
.article-detail-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.header-card {
  background: var(--surface);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--gray-900) 2%, transparent);
}

.page-header {
  margin: 0;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.content-card {
  background: var(--surface);
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--gray-900) 2%, transparent);
}

.article-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-top: 0;
  margin-bottom: 20px;
  text-align: center;
}

.article-meta {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 20px;
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--surface-warm);
}

.article-cover-wrapper {
  display: flex;
  justify-content: center;
  margin-bottom: 30px;
}

.article-cover {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  object-fit: contain;
}

.article-content {
  font-size: 16px;
  line-height: 1.8;
  color: var(--text-primary);
}

/* Add some styles for rich text content */
:deep(.article-content p) {
  margin-bottom: 1em;
}
:deep(.article-content img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}
:deep(.article-content h2, .article-content h3) {
  color: var(--text-primary);
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}
</style>
