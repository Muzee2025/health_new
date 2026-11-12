<template>
  <main class="article-detail-container" :aria-busy="loading">
    <div v-if="loading" class="article-state" role="status" aria-label="正在加载文章">
      <el-skeleton :rows="7" animated />
    </div>
    <section v-else-if="loadError" class="article-state" aria-labelledby="article-error-title">
      <LibraryEmpty role="networkError" :description="loadError" />
      <h1 id="article-error-title">文章暂时无法打开</h1>
      <div class="article-recovery">
        <el-button type="primary" @click="fetchArticle">重新加载</el-button
        ><el-button @click="goBack">返回列表</el-button>
      </div>
    </section>
    <template v-else-if="article">
      <div class="header-card">
        <el-page-header
          @back="goBack"
          @keydown.enter.prevent="goBack"
          @keydown.space.prevent="goBack"
          title="返回"
          class="page-header"
        >
          <template #content>
            <span class="header-title">文章详情</span>
          </template>
        </el-page-header>
      </div>

      <div class="content-card">
        <h1 class="article-title">{{ article.title }}</h1>
        <div class="article-meta">
          <span
            >分类：<el-tag size="small">{{ article.category || '心理科普' }}</el-tag></span
          >
          <span v-if="article.source">来源：{{ article.source }}</span>
          <span>阅读量：{{ article.views }}</span>
          <span>发布时间：{{ formatDate(article.created_at) }}</span>
        </div>

        <div v-if="article.cover_url" class="article-cover-wrapper">
          <img :src="article.cover_url" class="article-cover" :alt="article.title" />
        </div>

        <article
          class="article-content"
          aria-label="文章正文"
          v-html="safeArticleContent"
          @click="handleArticleContentClick"
        ></article>
      </div>
    </template>
  </main>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue'
import DOMPurify from 'dompurify'
import { downloadArticleDocument } from '../utils/articleDocuments'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElPageHeader, ElTag, ElButton, ElSkeleton } from 'element-plus'

const handleArticleContentClick = async (event) => {
  try {
    await downloadArticleDocument(event)
  } catch {
    ElMessage.error('附件下载失败，请重新登录或稍后重试')
  }
}
const route = useRoute()
const router = useRouter()
const article = ref(null)
const loading = ref(true)
const loadError = ref('')
let articleRequest
let disposed = false
const safeArticleContent = computed(() =>
  DOMPurify.sanitize(article.value?.content || '', { USE_PROFILES: { html: true } }),
)
const VIEW_DEDUP_WINDOW_MS = 5 * 60 * 1000
const VIEW_RETRY_QUEUE_KEY = 'article_view_retry_queue_v1'
let retryTimer = null

const goBack = () => {
  const back = window.history.state?.back
  if (typeof back === 'string' && back.startsWith('/') && !back.startsWith('//')) router.back()
  else
    router.push(
      localStorage.getItem('role') === 'teacher' ? '/teacher/content' : '/student/articles',
    )
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
  const deduped = queue.filter(
    (x) =>
      !(
        Number(x.articleId) === Number(task.articleId) &&
        String(x.viewerId) === String(task.viewerId)
      ),
  )
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
    const res = await axios.post(
      `/api/student/articles/${task.articleId}/view`,
      { viewer_id: task.viewerId },
      { timeout: 5000 },
    )
    const nextViews = Number(res?.data?.views || 0)
    if (
      !disposed &&
      article.value &&
      Number(article.value.id) === Number(task.articleId) &&
      Number.isFinite(nextViews)
    ) {
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
  if (!disposed) retryTimer = setTimeout(flushRetryQueue, 2000)
}

const trackArticleView = async (articleId) => {
  const viewerId = getViewerId()
  if (shouldSkipTrack(articleId, viewerId)) return
  try {
    const res = await axios.post(
      `/api/student/articles/${articleId}/view`,
      { viewer_id: viewerId },
      { timeout: 5000 },
    )
    const nextViews = Number(res?.data?.views || 0)
    if (
      !disposed &&
      Number.isFinite(nextViews) &&
      Number(article.value?.id) === Number(articleId)
    ) {
      const syncedViews = Math.max(0, nextViews)
      article.value.views = syncedViews
      dispatchArticleViewUpdated(articleId, syncedViews)
    }
  } catch {
    enqueueRetryTask({ articleId, viewerId, retryCount: 0, createdAt: Date.now() })
    if (retryTimer) clearTimeout(retryTimer)
    if (!disposed) retryTimer = setTimeout(flushRetryQueue, 1500)
  }
}

const fetchArticle = async () => {
  const id = Number(route.params.id)
  articleRequest?.abort()
  const request = new AbortController()
  articleRequest = request
  loading.value = true
  loadError.value = ''
  article.value = null
  try {
    if (!Number.isSafeInteger(id) || id <= 0) throw new Error('invalid-article')
    const res = await axios.get(`/api/student/articles/${id}`, {
      signal: request.signal,
      timeout: 15000,
    })
    if (disposed || request.signal.aborted) return
    if (!res.data || typeof res.data.title !== 'string') throw new Error('invalid-article')
    article.value = res.data
    article.value.views = Math.max(0, Number(article.value.views) || 0)
    trackArticleView(id)
  } catch (error) {
    if (disposed || request.signal.aborted) return
    const status = error.status || error.response?.status
    loadError.value =
      status === 403 || status === 404
        ? '文章不存在或当前账号无权查看。'
        : '文章加载失败，请检查连接后重试。'
  } finally {
    if (!disposed && !request.signal.aborted) loading.value = false
  }
}

const formatDate = (dateString) => {
  if (!dateString) return '未提供'
  const d = new Date(dateString)
  return Number.isNaN(d.getTime()) ? '未提供' : d.toLocaleString('zh-CN')
}

onMounted(() => {
  flushRetryQueue()
  fetchArticle()
})

onBeforeUnmount(() => {
  disposed = true
  articleRequest?.abort()
  if (retryTimer) clearTimeout(retryTimer)
})
watch(
  () => route.params.id,
  () => {
    fetchArticle()
  },
)
</script>

<style scoped>
.article-detail-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 960px;
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
  text-align: left;
  overflow-wrap: anywhere;
}

.article-meta {
  display: flex;
  justify-content: flex-start;
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
  overflow-wrap: anywhere;
  white-space: pre-line;
}
.article-state {
  padding: var(--space-7);
  background: var(--surface);
  border-radius: var(--radius-lg);
}
.article-state h1 {
  font-size: var(--text-h3);
  text-align: center;
}
.article-recovery {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-5);
}
:deep(.article-content table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
}
:deep(.article-content pre) {
  overflow-x: auto;
  max-width: 100%;
  padding: var(--space-4);
  background: var(--surface-subtle);
}
@media (max-width: 600px) {
  .article-detail-container {
    padding: var(--space-3);
    gap: var(--space-3);
  }
  .content-card,
  .header-card,
  .article-state {
    padding: var(--space-4);
    box-shadow: none;
  }
  .article-title {
    font-size: var(--text-h3);
    line-height: var(--line-height-heading);
  }
  .article-meta {
    gap: var(--space-2) var(--space-4);
    margin-bottom: var(--space-5);
  }
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
