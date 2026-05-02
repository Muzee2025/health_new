<template>
  <div class="treehole-container">
    <div class="treehole-header">
      <div class="header-left">
        <h2>🌳 匿名树洞</h2>
        <p class="desc">放下伪装，说出心里话。深度分享将获得红色能量积分。</p>
      </div>
      <div class="header-right">
        <el-tag type="danger" effect="dark" round size="large">红色能量: {{ redEnergy }}</el-tag>
      </div>
    </div>
    
    <div class="post-card glass-card">
      <el-input
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
              @click="toggleTagSelection(tag)"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
        <div class="action-buttons">
          <span class="emoji-btn">😊</span>
          <button class="publish-btn" @click="submitPost" :disabled="loading || selectedTags.length > 2">
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
          @click="setFilterTag('')"
        >
          全部
        </el-tag>
        <el-tag
          v-for="tag in PRESET_TAGS"
          :key="tag"
          :effect="filterTag === tag ? 'dark' : 'plain'"
          class="selectable-tag"
          @click="setFilterTag(tag)"
        >
          {{ tag }}
        </el-tag>
      </div>
    </div>

    <div class="post-list">
      <el-empty v-if="posts.length === 0" description="这里静悄悄的，快来发布第一条树洞吧！" />
      
      <div v-for="post in posts" :key="post.id" class="post-item glass-card">
        <div class="post-item-header">
          <div class="author-info">
            <el-avatar :size="40" class="anonymous-avatar">匿</el-avatar>
            <div class="author-details">
              <span class="author-name">{{ post.anonymous_id }}</span>
              <span class="post-time">{{ new Date(post.created_at).toLocaleString() }}</span>
            </div>
          </div>
          <el-tag v-if="post.is_deep" type="warning" effect="light" round size="small">✨深度好文</el-tag>
        </div>
        
        <div class="post-content">{{ post.content }}</div>
        
        <div class="post-tags" v-if="post.tags">
          <el-tag v-for="t in post.tags.split(',')" :key="t" size="small" class="mr-2" type="info">{{ t }}</el-tag>
        </div>
        
        <div v-if="post.reply_tip" class="reply-tip mt-10">
          <el-icon><Microphone /></el-icon> <strong>心晴小助手：</strong> {{ post.reply_tip }}
        </div>
        
        <div class="post-footer">
          <div class="interaction-btn" :class="{ active: post.is_liked }" @click="toggleLike(post)">
            <el-icon><i class="fas fa-heart" v-if="post.is_liked"></i><i class="far fa-heart" v-else></i></el-icon>
            <span>{{ post.likes_count || '点赞' }}</span>
          </div>
          <div class="interaction-btn" @click="openComments(post)">
            <el-icon><i class="far fa-comment"></i></el-icon>
            <span>{{ post.comments_count || '评论' }}</span>
          </div>
          <div class="interaction-btn" :class="{ active: post.is_favorited }" @click="toggleFavorite(post)">
            <el-icon><i class="fas fa-star" v-if="post.is_favorited"></i><i class="far fa-star" v-else></i></el-icon>
            <span>{{ post.favorites_count || '收藏' }}</span>
          </div>
        </div>
        
        <!-- Comments Section -->
        <div v-if="activeCommentPostId === post.id" class="comments-section">
          <el-divider border-style="dashed" />
          <div class="comment-input-box">
            <el-input v-model="newComment" placeholder="写下你的评论..." size="small" @keyup.enter="submitComment(post)" />
            <el-button type="primary" size="small" @click="submitComment(post)" :disabled="!newComment.trim()">发送</el-button>
          </div>
          
          <div class="comments-list mt-10">
            <div v-for="comment in postComments" :key="comment.id" class="comment-item" :class="{ 'sub-comment': comment.parent_id }">
              <div class="comment-author">
                <span class="c-name">{{ comment.anonymous_id }}</span>
                <span class="c-time">{{ new Date(comment.created_at).toLocaleString() }}</span>
              </div>
              <div class="c-content">
                <span v-if="comment.parent_id" class="reply-to">@{{ getParentAuthor(comment.parent_id) }} </span>
                {{ comment.content }}
              </div>
              <div class="c-actions">
                <span class="reply-btn" @click="replyToComment(comment)">回复</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Microphone } from '@element-plus/icons-vue'

const PRESET_TAGS = ['#人生意义', '#自我成长', '#抗压故事', '#红色精神与我', '#价值观碰撞', '#情绪洞察', '#人际关系', '#未来规划']

const redEnergy = ref(0)
const newPost = ref('')
const selectedTags = ref([])
const loading = ref(false)
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
  
  // Inject FontAwesome if not present
  if (!document.getElementById('font-awesome')) {
    const link = document.createElement('link')
    link.id = 'font-awesome'
    link.rel = 'stylesheet'
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
    document.head.appendChild(link)
  }
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
  try {
    const res = await axios.get('/api/student/treehole/posts', {
      params: {
        tab: activeTab.value,
        tag: filterTag.value || null
      }
    })
    posts.value = res.data
  } catch (error) {
    console.error('Fetch treehole error:', error)
    ElMessage.error('获取树洞列表失败')
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
      tags: selectedTags.value
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
          duration: 5000
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
      parent_id: replyParentId.value
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
  const parent = postComments.value.find(c => c.id === parentId)
  return parent ? parent.anonymous_id : '未知'
}
</script>

<style scoped>
.treehole-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #F9FAFB 0%, #E0E7FF 100%);
  padding: 20px;
  border-radius: 16px;
}

.treehole-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.treehole-header h2 { margin: 0 0 8px 0; color: #1F2937; }
.desc { color: #6B7280; font-size: 14px; margin: 0; }

.glass-card {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 24px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  padding: 20px;
  margin-bottom: 20px;
}

.custom-textarea :deep(.el-textarea__inner) {
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid #E5E7EB;
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
.tags-label { font-size: 13px; color: #6B7280; margin-bottom: 5px; display: block; }
.tags-scroll {
  display: flex;
  overflow-x: auto;
  gap: 8px;
  padding-bottom: 5px;
}
.tags-scroll::-webkit-scrollbar { height: 4px; }
.tags-scroll::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }

.selectable-tag {
  cursor: pointer;
  border-radius: 12px;
  user-select: none;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-left: 15px;
}

.emoji-btn { font-size: 24px; cursor: pointer; transition: transform 0.2s; }
.emoji-btn:hover { transform: scale(1.2); }

.publish-btn {
  background: linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%);
  color: white;
  border: none;
  padding: 10px 24px;
  border-radius: 20px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
}
.publish-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 6px 15px rgba(139, 92, 246, 0.4);
}
.publish-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.custom-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background-color: rgba(0,0,0,0.05); }
.custom-tabs :deep(.el-tabs__item) { font-size: 16px; font-weight: 500; }

.filter-tags { margin-bottom: 20px; }

.post-item { transition: transform 0.2s; }
.post-item:hover { transform: translateY(-2px); }

.post-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.author-info { display: flex; align-items: center; gap: 10px; }
.anonymous-avatar { background: linear-gradient(135deg, #93C5FD, #C4B5FD); color: white; font-weight: bold; }
.author-details { display: flex; flex-direction: column; }
.author-name { font-weight: 600; color: #374151; }
.post-time { font-size: 12px; color: #9CA3AF; }

.post-content { font-size: 15px; color: #1F2937; line-height: 1.6; margin-bottom: 15px; white-space: pre-wrap; }
.post-tags { margin-bottom: 15px; }

.reply-tip {
  background: rgba(254, 243, 199, 0.5);
  color: #D97706;
  padding: 10px 15px;
  border-radius: 12px;
  font-size: 13px;
  margin-bottom: 15px;
}

.post-footer {
  display: flex;
  gap: 30px;
  border-top: 1px solid rgba(0,0,0,0.05);
  padding-top: 12px;
}

.interaction-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6B7280;
  cursor: pointer;
  transition: color 0.2s;
}
.interaction-btn:hover { color: #3B82F6; }
.interaction-btn.active { color: #EF4444; }

.comments-section {
  margin-top: 10px;
  background: rgba(255, 255, 255, 0.4);
  border-radius: 12px;
  padding: 15px;
}
.comment-input-box { display: flex; gap: 10px; }
.comments-list { display: flex; flex-direction: column; gap: 12px; }
.comment-item { padding-bottom: 10px; border-bottom: 1px dashed rgba(0,0,0,0.05); }
.comment-item:last-child { border-bottom: none; padding-bottom: 0; }
.sub-comment { margin-left: 30px; padding-left: 10px; border-left: 2px solid rgba(0,0,0,0.05); }
.comment-author { display: flex; justify-content: space-between; margin-bottom: 4px; }
.c-name { font-weight: 600; font-size: 13px; color: #4B5563; }
.c-time { font-size: 12px; color: #9CA3AF; }
.c-content { font-size: 14px; color: #374151; margin-bottom: 4px; }
.reply-to { color: #3B82F6; font-weight: 500; }
.c-actions { display: flex; justify-content: flex-end; }
.reply-btn { font-size: 12px; color: #6B7280; cursor: pointer; }
.reply-btn:hover { color: #3B82F6; }
</style>
