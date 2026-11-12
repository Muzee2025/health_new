<template>
  <div class="treehole-container business-page">
    <div class="treehole-header">
      <div class="header-left">
        <h2><LibraryIcon name="treehole" /> 匿名树洞</h2>
        <p class="desc">
          这里以匿名方式展示内容，匿名展示不等于平台不可关联。请勿写入可识别个人身份的信息。
        </p>
      </div>
      <div class="header-right">
        <el-tag type="danger" effect="dark" round size="large">红色能量: {{ redEnergy }}</el-tag>
      </div>
    </div>

    <div class="post-card glass-card">
      <el-input
        aria-label="树洞内容"
        v-model="newPost"
        type="textarea"
        :rows="4"
        placeholder="分享你今天对生活、成长或价值观的思考...（深度分享将获得红色能量积分）"
        maxlength="500"
        show-word-limit
        class="custom-textarea"
      />
      <div class="post-actions">
        <div class="tags-selector">
          <span class="tags-label">选择标签 (1-2个):</span>
          <div class="tags-scroll">
            <el-tag
              v-for="tag in PRESET_TAGS"
              :key="tag"
              :effect="selectedTags.includes(tag) ? 'dark' : 'plain'"
              class="selectable-tag"
              role="button"
              tabindex="0"
              :aria-pressed="selectedTags.includes(tag)"
              @click="toggleTagSelection(tag)"
              @keydown.enter.prevent="toggleTagSelection(tag)"
              @keydown.space.prevent="toggleTagSelection(tag)"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
        <div class="action-buttons">
          <button
            class="publish-btn"
            @click="submitPost"
            :disabled="loading || selectedTags.length > 2"
          >
            发布
          </button>
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="custom-tabs" @tab-change="fetchPosts">
      <el-tab-pane label="树洞首页" name="home"></el-tab-pane>
      <el-tab-pane label="我的发布" name="my"></el-tab-pane>
      <el-tab-pane label="我的收藏" name="favorites"></el-tab-pane>
    </el-tabs>

    <div class="filter-tags" v-if="activeTab === 'home'">
      <div class="tags-scroll">
        <el-tag
          :effect="filterTag === '' ? 'dark' : 'plain'"
          class="selectable-tag"
          role="button"
          tabindex="0"
          :aria-pressed="filterTag === ''"
          @click="setFilterTag('')"
          @keydown.enter.prevent="setFilterTag('')"
          @keydown.space.prevent="setFilterTag('')"
        >
          全部
        </el-tag>
        <el-tag
          v-for="tag in PRESET_TAGS"
          :key="tag"
          :effect="filterTag === tag ? 'dark' : 'plain'"
          class="selectable-tag"
          role="button"
          tabindex="0"
          :aria-pressed="filterTag === tag"
          @click="setFilterTag(tag)"
          @keydown.enter.prevent="setFilterTag(tag)"
          @keydown.space.prevent="setFilterTag(tag)"
        >
          {{ tag }}
        </el-tag>
      </div>
    </div>

    <el-alert
      v-if="postsError"
      type="error"
      :closable="false"
      show-icon
      title="树洞列表暂时无法加载，请检查网络后重试。"
    >
      <el-button link type="primary" @click="fetchPosts">重新加载</el-button>
    </el-alert>
    <div v-else class="post-list" v-loading="loadingPosts">
      <LibraryEmpty v-if="!loadingPosts && posts.length === 0" description="还没有可显示的内容。" />

      <div v-for="post in posts" :key="post.id" class="post-item glass-card">
        <div class="post-item-header">
          <div class="author-info">
            <el-avatar :size="40" class="anonymous-avatar">匿</el-avatar>
            <div class="author-details">
              <span class="author-name">{{ post.anonymous_id }}</span>
              <span class="post-time">{{ new Date(post.created_at).toLocaleString() }}</span>
            </div>
          </div>
          <el-tag v-if="post.is_deep" type="warning" effect="light" round size="small"
            ><LibraryIcon name="book" /> 深度好文</el-tag
          >
        </div>

        <div class="post-content">{{ post.content }}</div>

        <div class="post-tags" v-if="post.tags">
          <el-tag
            v-for="t in post.tags.split(',')"
            :key="t"
            size="small"
            class="mr-2"
            type="info"
            >{{ t }}</el-tag
          >
        </div>

        <div v-if="post.reply_tip" class="reply-tip mt-10">
          <el-icon><LibraryIcon name="support" /></el-icon> <strong>心晴小助手：</strong>
          {{ post.reply_tip }}
        </div>

        <div class="post-footer">
          <button
            type="button"
            class="interaction-btn"
            :class="{ active: post.is_liked }"
            :aria-pressed="!!post.is_liked"
            :aria-label="post.is_liked ? '取消点赞' : '点赞'"
            @click="toggleLike(post)"
          >
            <LibraryIcon name="heart" />
            <span>{{ post.likes_count || '点赞' }}</span>
          </button>
          <button type="button" class="interaction-btn" @click="openComments(post)">
            <el-icon><LibraryIcon name="chat" /></el-icon>
            <span>{{ post.comments_count || '评论' }}</span>
          </button>
          <button
            type="button"
            class="interaction-btn"
            :class="{ active: post.is_favorited }"
            :aria-pressed="!!post.is_favorited"
            :aria-label="post.is_favorited ? '取消收藏' : '收藏'"
            @click="toggleFavorite(post)"
          >
            <el-icon
              ><LibraryIcon name="star-filled" v-if="post.is_favorited" /><LibraryIcon
                name="star"
                v-else
            /></el-icon>
            <span>{{ post.favorites_count || '收藏' }}</span>
          </button>
        </div>

        <!-- Comments Section -->
        <div v-if="activeCommentPostId === post.id" class="comments-section">
          <el-divider border-style="dashed" />
          <div class="comment-input-box">
            <el-input
              v-model="newComment"
              placeholder="写下你的评论..."
              size="small"
              @keyup.enter="submitComment(post)"
            />
            <el-button
              type="primary"
              size="small"
              @click="submitComment(post)"
              :disabled="!newComment.trim()"
              >发送</el-button
            >
          </div>

          <div class="comments-list mt-10">
            <div
              v-for="comment in postComments"
              :key="comment.id"
              class="comment-item"
              :class="{ 'sub-comment': comment.parent_id }"
            >
              <div class="comment-author">
                <span class="c-name">{{ comment.anonymous_id }}</span>
                <span class="c-time">{{ new Date(comment.created_at).toLocaleString() }}</span>
              </div>
              <div class="c-content">
                <span v-if="comment.parent_id" class="reply-to"
                  >@{{ getParentAuthor(comment.parent_id) }}
                </span>
                {{ comment.content }}
              </div>
              <div class="c-actions">
                <button type="button" class="reply-btn" @click="replyToComment(comment)">
                  回复
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import {
  ElMessage,
  ElMessageBox,
  ElTag,
  ElInput,
  ElTabs,
  ElTabPane,
  ElAvatar,
  ElIcon,
  ElDivider,
  ElButton,
  ElAlert,
} from 'element-plus'

const PRESET_TAGS = [
  '#人生意义',
  '#自我成长',
  '#抗压故事',
  '#红色精神与我',
  '#价值观碰撞',
  '#情绪洞察',
  '#人际关系',
  '#未来规划',
]

const redEnergy = ref(0)
const newPost = ref('')
const selectedTags = ref([])
const loading = ref(false)
const loadingPosts = ref(false)
const postsError = ref(false)
const posts = ref([])
const activeTab = ref('home')
const filterTag = ref('')

const activeCommentPostId = ref(null)
const newComment = ref('')
const replyParentId = ref(null)
const postComments = ref([])

onMounted(() => {
  fetchDashboardStats()
  fetchPosts()
})

const fetchDashboardStats = async () => {
  try {
    const res = await axios.get('/api/student/dashboard/stats')
    redEnergy.value = res.data.red_energy || 0
  } catch (e) {
    console.error(e)
  }
}

const toggleTagSelection = (tag) => {
  const idx = selectedTags.value.indexOf(tag)
  if (idx > -1) {
    selectedTags.value.splice(idx, 1)
  } else {
    if (selectedTags.value.length >= 2) {
      ElMessage.warning('最多只能选择2个标签')
      return
    }
    selectedTags.value.push(tag)
  }
}

const setFilterTag = (tag) => {
  filterTag.value = tag
  fetchPosts()
}

const fetchPosts = async () => {
  loadingPosts.value = true
  postsError.value = false
  try {
    const res = await axios.get('/api/student/treehole/posts', {
      params: {
        tab: activeTab.value,
        tag: filterTag.value || null,
      },
    })
    posts.value = Array.isArray(res.data) ? res.data : []
  } catch (error) {
    postsError.value = true
  } finally {
    loadingPosts.value = false
  }
}

const submitPost = async () => {
  if (!newPost.value.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }

  loading.value = true
  try {
    const res = await axios.post('/api/student/treehole/post', {
      content: newPost.value,
      tags: selectedTags.value,
    })

    if (res.data.is_deep) {
      ElMessageBox.alert('感谢你的深度分享！+5红色能量积分', '能量到账', {
        confirmButtonText: '收下',
        type: 'success',
      })
      redEnergy.value += 5
    } else {
      ElMessage.success('发布成功')
    }

    newPost.value = ''
    selectedTags.value = []

    if (activeTab.value === 'home' || activeTab.value === 'my') {
      fetchPosts() // refresh to get updated counts
    }

    if (res.data.reply_tip) {
      setTimeout(() => {
        ElMessage({
          message: '心晴小助手有一条悄悄话给你，请查看你的树洞记录。',
          type: 'warning',
          duration: 5000,
        })
      }, 1000)
    }
  } catch (error) {
    ElMessage.error('发布失败')
  } finally {
    loading.value = false
  }
}

const toggleLike = async (post) => {
  try {
    const res = await axios.post(`/api/student/treehole/${post.id}/like`)
    if (res.data.status === 'liked') {
      post.is_liked = true
      post.likes_count++
    } else {
      post.is_liked = false
      post.likes_count--
    }
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const toggleFavorite = async (post) => {
  try {
    const res = await axios.post(`/api/student/treehole/${post.id}/favorite`)
    if (res.data.status === 'favorited') {
      post.is_favorited = true
      post.favorites_count++
      if (activeTab.value === 'favorites') fetchPosts()
    } else {
      post.is_favorited = false
      post.favorites_count--
      if (activeTab.value === 'favorites') fetchPosts()
    }
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const openComments = async (post) => {
  if (activeCommentPostId.value === post.id) {
    activeCommentPostId.value = null
    return
  }
  activeCommentPostId.value = post.id
  replyParentId.value = null
  newComment.value = ''
  await fetchComments(post.id)
}

const fetchComments = async (postId) => {
  try {
    const res = await axios.get(`/api/student/treehole/${postId}/comments`)
    postComments.value = res.data
  } catch (e) {
    console.error('fetch comments error:', e)
  }
}

const submitComment = async (post) => {
  if (!newComment.value.trim()) return

  try {
    let content = newComment.value
    if (replyParentId.value) {
      // Remove @username from beginning if exists
      const match = content.match(/^@\S+\s+/)
      if (match) {
        content = content.substring(match[0].length)
      }
    }

    await axios.post(`/api/student/treehole/${post.id}/comment`, {
      content: content,
      parent_id: replyParentId.value,
    })

    post.comments_count++
    newComment.value = ''
    replyParentId.value = null
    await fetchComments(post.id)
  } catch (e) {
    console.error('submit comment error:', e)
    ElMessage.error('评论失败')
  }
}

const replyToComment = (comment) => {
  replyParentId.value = comment.id
  newComment.value = `@${comment.anonymous_id} `
  // focus input manually if needed
}

const getParentAuthor = (parentId) => {
  const parent = postComments.value.find((c) => c.id === parentId)
  return parent ? parent.anonymous_id : '未知'
}
</script>

<style scoped>
.treehole-container {
  min-height: 100%;
  background: linear-gradient(135deg, var(--surface-subtle) 0%, var(--brand-50) 100%);
  padding: 20px;
  border-radius: 16px;
}

.treehole-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.treehole-header h2 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
}
.desc {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0;
}

.glass-card {
  background: color-mix(in srgb, var(--surface) 70%, transparent);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid color-mix(in srgb, var(--surface) 50%, transparent);
  border-radius: 24px;
  box-shadow: 0 4px 15px color-mix(in srgb, var(--gray-900) 5%, transparent);
  padding: 20px;
  margin-bottom: 20px;
}

.custom-textarea :deep(.el-textarea__inner) {
  background: color-mix(in srgb, var(--surface) 50%, transparent);
  border: 1px solid var(--border);
  border-radius: 16px;
  font-size: 15px;
  padding: 15px;
}

.post-actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-top: 15px;
}

.tags-selector {
  flex: 1;
  overflow: hidden;
}
.tags-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 5px;
  display: block;
}
.tags-scroll {
  display: flex;
  overflow-x: auto;
  gap: 8px;
  padding-bottom: 5px;
}
.tags-scroll::-webkit-scrollbar {
  height: 4px;
}
.tags-scroll::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.selectable-tag {
  cursor: pointer;
  border-radius: 12px;
  user-select: none;
}
.selectable-tag:focus-visible,
.interaction-btn:focus-visible,
.reply-btn:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 2px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-left: 15px;
}

.publish-btn {
  background: linear-gradient(135deg, var(--brand-600) 0%, var(--brand-600) 100%);
  color: var(--surface);
  border: none;
  padding: 10px 24px;
  border-radius: 20px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 10px color-mix(in srgb, var(--brand-500) 30%, transparent);
}
.publish-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 6px 15px color-mix(in srgb, var(--brand-500) 40%, transparent);
}
.publish-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.custom-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: color-mix(in srgb, var(--gray-900) 5%, transparent);
}
.custom-tabs :deep(.el-tabs__item) {
  font-size: 16px;
  font-weight: 500;
}

.filter-tags {
  margin-bottom: 20px;
}

.post-item {
  transition: transform 0.2s;
}
.post-item:hover {
  transform: translateY(-2px);
}

.post-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.author-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.anonymous-avatar {
  background: var(--brand-100);
  color: var(--brand-600);
  font-weight: bold;
}
.author-details {
  display: flex;
  flex-direction: column;
}
.author-name {
  font-weight: 600;
  color: var(--text-primary);
}
.post-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.post-content {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: 15px;
  white-space: pre-wrap;
}
.post-tags {
  margin-bottom: 15px;
}

.reply-tip {
  background: var(--warning-100);
  color: var(--warning-text);
  padding: 10px 15px;
  border-radius: 12px;
  font-size: 13px;
  margin-bottom: 15px;
}

.post-footer {
  display: flex;
  gap: 30px;
  border-top: 1px solid color-mix(in srgb, var(--gray-900) 5%, transparent);
  padding-top: 12px;
}

.interaction-btn {
  border: 0;
  background: transparent;
  font: inherit;
  padding: 6px 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.2s;
}
.interaction-btn:hover {
  color: var(--brand-600);
}
.interaction-btn.active {
  color: var(--danger-text);
}

.comments-section {
  margin-top: 10px;
  background: color-mix(in srgb, var(--surface) 40%, transparent);
  border-radius: 12px;
  padding: 15px;
}
.comment-input-box {
  display: flex;
  gap: 10px;
}
.comments-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.comment-item {
  padding-bottom: 10px;
  border-bottom: 1px dashed color-mix(in srgb, var(--gray-900) 5%, transparent);
}
.comment-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.sub-comment {
  margin-left: 30px;
  padding-left: 10px;
  border-left: 2px solid color-mix(in srgb, var(--gray-900) 5%, transparent);
}
.comment-author {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}
.c-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-secondary);
}
.c-time {
  font-size: 12px;
  color: var(--text-secondary);
}
.c-content {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.reply-to {
  color: var(--brand-600);
  font-weight: 500;
}
.c-actions {
  display: flex;
  justify-content: flex-end;
}
.reply-btn {
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  border: 0;
  background: transparent;
  font: inherit;
  padding: 6px 10px;
}
.reply-btn:hover {
  color: var(--brand-600);
}
@media (max-width: 600px) {
  .treehole-container {
    padding: 14px 0;
    border-radius: var(--radius-md);
  }
  .treehole-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
  .glass-card {
    padding: 16px;
    border-radius: var(--radius-lg);
  }
  .post-actions {
    align-items: stretch;
    flex-direction: column;
    gap: 14px;
  }
  .action-buttons {
    margin-left: 0;
    justify-content: flex-end;
  }
  .post-footer {
    gap: 8px;
    justify-content: space-between;
  }
  .interaction-btn {
    font-size: 13px;
  }
  .comment-input-box {
    align-items: stretch;
    flex-direction: column;
  }
  .comment-input-box :deep(.el-button) {
    align-self: flex-end;
    min-height: 40px;
  }
  .comment-author {
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }
  .sub-comment {
    margin-left: 12px;
  }
}
</style>
