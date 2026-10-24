<template>
  <div ref="pageRoot" class="content-container business-page">
    <el-tabs v-model="activeTab" class="content-tabs">
      <!-- Article Management Tab -->
      <el-tab-pane label="文章管理" name="articles">
        <div class="action-bar">
          <el-button type="primary" @click="openArticleDialog(null)">新增文章</el-button>
        </div>

        <el-alert v-if="articleLoadError" type="error" :closable="false" title="文章列表暂时无法加载。"><el-button text type="primary" @click="fetchArticles">重新加载</el-button></el-alert>
        <div class="article-toolbar" v-if="articles.length">
          <el-input v-model="articleSearch" clearable aria-label="搜索文章标题、摘要或来源" placeholder="搜索标题、摘要或来源" @input="articlePage = 1" />
          <el-select v-model="articleCategory" aria-label="按分类筛选文章" @change="articlePage = 1">
            <el-option label="全部分类" value="全部" />
            <el-option v-for="category in articleCategories" :key="category" :label="category" :value="category" />
          </el-select>
        </div>
        <div class="business-table-wrap"><el-table :data="paginatedArticles" style="width: 100%" v-loading="loadingArticles" stripe :empty-text="articles.length ? '没有符合条件的文章。' : '还没有文章记录。'">
          <el-table-column prop="title" label="标题" min-width="200" />
          <el-table-column prop="category" label="分类" width="120" />
          <el-table-column prop="source" label="来源" width="150" />
          <el-table-column prop="views" label="阅读量" width="100" />
          <el-table-column label="发布时间" width="180">
            <template #default="scope">
              {{ formatDate(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170" align="right">
            <template #default="scope">
              <el-button link type="primary" @click="openArticle(scope.row.id)">阅读</el-button>
              <el-button link type="danger" :loading="deletingArticleIds.includes(scope.row.id)" :disabled="deletingArticleIds.includes(scope.row.id)" @click="deleteArticle(scope.row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        </div>
        <div v-if="filteredArticles.length" class="pagination-wrapper">
          <el-pagination
            v-model:current-page="articlePage"
            :page-size="articlePageSize"
            :total="filteredArticles.length"
            :pager-count="5"
            layout="total, prev, pager, next"
            :hide-on-single-page="true"
            aria-label="文章分页"
            @current-change="scrollToArticles"
          />
        </div>
      </el-tab-pane>

      <!-- Teacher Management Tab -->
      <el-tab-pane label="心理老师管理" name="teachers">
        <div class="action-bar">
          <el-button type="primary" @click="openTeacherDialog(null)">编辑我的老师档案</el-button>
        </div>
        
        <el-alert v-if="teacherLoadError" type="error" :closable="false" title="教师档案列表暂时无法加载。"><el-button text type="primary" @click="fetchTeachers">重新加载</el-button></el-alert>
        <div class="business-table-wrap"><el-table :data="teachers" style="width: 100%" v-loading="loadingTeachers" stripe empty-text="暂无教师档案记录。">
          <el-table-column label="头像" width="80">
            <template #default>
              <div class="teacher-avatar-small">
                <el-icon><LibraryIcon name="user"  /></el-icon>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column prop="username" label="账号" width="120" />
          <el-table-column prop="title" label="职称" width="150" />
          <el-table-column prop="location" label="办公地点" min-width="150" />
          <el-table-column label="操作" width="150" align="right">
            <template #default="scope">
              <el-button v-if="String(scope.row.user_id) === String(currentTeacherId)" link type="primary" @click="openTeacherDialog(scope.row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Article Dialog -->
    <el-dialog v-model="articleDialogVisible" title="新增文章" width="600px" :close-on-click-modal="!savingArticle" :close-on-press-escape="!savingArticle" :show-close="!savingArticle">
      <el-form :model="articleForm" label-width="80px" :disabled="savingArticle">
        <el-form-item label="标题" required>
          <el-input v-model="articleForm.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="articleForm.category" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="articleForm.source" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="封面链接">
          <el-input v-model="articleForm.cover_url" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="articleForm.summary" type="textarea" :rows="2" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="正文" required>
          <el-upload
            class="upload-demo"
            :action="uploadUrl"
            accept="image/png,image/jpeg,image/webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            :on-error="handleUploadError"
            :headers="uploadHeaders"
            :on-success="handleUploadSuccess"
            :before-upload="beforeUpload"
            :show-file-list="false"
          >
            <el-button type="success" size="small" plain style="margin-bottom: 10px;">上传PDF / DOCX附件或图片</el-button>
          </el-upload>
          <el-input v-model="articleForm.content" type="textarea" :rows="6" maxlength="100000" show-word-limit placeholder="请输入文章正文" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button :disabled="savingArticle" @click="articleDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingArticle" :disabled="savingArticle" @click="submitArticle">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Teacher Dialog -->
    <el-dialog v-model="teacherDialogVisible" title="编辑老师档案" width="600px">
      <el-form :model="teacherForm" label-width="100px">
        <el-form-item label="绑定用户ID" required>
          <el-input-number v-model="teacherForm.user_id" :min="1" disabled />
          <span class="help-text">当前登录的教师账号</span>
        </el-form-item>
        <el-form-item label="职称">
          <el-input v-model="teacherForm.title" />
        </el-form-item>
        <el-form-item label="办公地点">
          <el-input v-model="teacherForm.location" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="teacherForm.intro" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="可预约时段">
          <el-input v-model="teacherForm.time_slots_str" type="textarea" :rows="3" placeholder='例如: ["周一 09:00-11:00", "周三 14:00-16:00"]' />
          <span class="help-text">请填写合法的 JSON 数组字符串</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="teacherDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitTeacher">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox, ElTabs, ElTabPane, ElButton, ElTable, ElTableColumn, ElIcon, ElDialog, ElForm, ElFormItem, ElInput, ElUpload, ElInputNumber, ElAlert, ElSelect, ElOption, ElPagination, vLoading } from 'element-plus'

const router = useRouter()
const currentTeacherId = (() => { try { return JSON.parse(localStorage.getItem('user') || '{}').id } catch { return null } })()
const activeTab = ref('articles')
const uploadUrl = axios.getUri({ url: '/api/teacher/upload' })
const handleUploadError = () => ElMessage.error('文件上传失败，请检查格式或稍后重试')

const uploadHeaders = computed(() => {
  return { Authorization: `Bearer ${localStorage.getItem('token')}` }
})

const beforeUpload = (file) => {
  const accepted = /\.(pdf|docx|png|jpe?g|webp)$/i.test(file.name)
  if (!accepted || file.size > 5 * 1024 * 1024) {
    ElMessage.error('请选择不超过5MiB的PDF、DOCX、PNG、JPEG或WebP文件')
    return false
  }
  return true
}

const handleUploadSuccess = (res, file) => {
  const url = res.url || res.image_url
  if (!url) { ElMessage.error('上传响应缺少文件地址'); return }
  if (/\.(pdf|docx)$/i.test(file.name)) {
    const name = file.name.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]))
    articleForm.value.content += '\n<br><a href="' + url + '">下载附件：' + name + '</a>'
  } else {
    articleForm.value.cover_url = url
  }
  ElMessage.success('文件上传成功')
}

// Articles
const articles = ref([])
const loadingArticles = ref(false)
const articleLoadError = ref(false)
const articleDialogVisible = ref(false)
const savingArticle = ref(false)
const deletingArticleIds = ref([])
const articleSearch = ref('')
const articleCategory = ref('全部')
const articlePage = ref(1)
const articlePageSize = 12
const pageRoot = ref(null)
const scrollToArticles = () => nextTick(() => pageRoot.value?.scrollIntoView({ block: 'start' }))
const articleCategories = computed(() => [...new Set(articles.value.map(article => article.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN')))
const filteredArticles = computed(() => {
  const query = articleSearch.value.trim().toLocaleLowerCase()
  return articles.value.filter((article) => {
    const matchesCategory = articleCategory.value === '全部' || article.category === articleCategory.value
    const searchable = [article.title, article.summary, article.source].filter(Boolean).join(' ').toLocaleLowerCase()
    return matchesCategory && (!query || searchable.includes(query))
  })
})
const paginatedArticles = computed(() => filteredArticles.value.slice((articlePage.value - 1) * articlePageSize, articlePage.value * articlePageSize))
watch(() => filteredArticles.value.length, (total) => {
  const lastPage = Math.max(1, Math.ceil(total / articlePageSize))
  if (articlePage.value > lastPage) articlePage.value = lastPage
})
const articleForm = ref({
  title: '',
  summary: '',
  content: '',
  cover_url: '',
  category: '心理科普',
  source: ''
})

const fetchArticles = async () => {
  loadingArticles.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/teacher/articles', {
      headers: { Authorization: `Bearer ${token}` }
    })
    articles.value = res.data
    if (articleCategory.value !== '全部' && !articleCategories.value.includes(articleCategory.value)) articleCategory.value = '全部'
    articleLoadError.value = false
  } catch (error) {
    articleLoadError.value = true
    ElMessage.error('获取文章列表失败')
  } finally {
    loadingArticles.value = false
  }
}

const openArticleDialog = () => {
  if (savingArticle.value) return
  articleForm.value = {
    title: '',
    summary: '',
    content: '',
    cover_url: '',
    category: '心理科普',
    source: ''
  }
  articleDialogVisible.value = true
}

const submitArticle = async () => {
  const title = String(articleForm.value.title || '').trim()
  const content = String(articleForm.value.content || '').trim()
  if (!title || !content) {
    ElMessage.warning('标题和正文必填')
    return
  }
  if (title.length > 200 || content.length > 100000 || String(articleForm.value.summary || '').length > 500 || String(articleForm.value.category || '').length > 50 || String(articleForm.value.source || '').length > 100 || String(articleForm.value.cover_url || '').length > 255) {
    ElMessage.warning('请检查各字段长度限制')
    return
  }
  if (savingArticle.value) return
  savingArticle.value = true
  try {
    const token = localStorage.getItem('token')
    const payload = {
      ...articleForm.value,
      title,
      content,
      summary: String(articleForm.value.summary || '').trim(),
      category: String(articleForm.value.category || '').trim(),
      source: String(articleForm.value.source || '').trim(),
      cover_url: String(articleForm.value.cover_url || '').trim()
    }
    await axios.post('/api/teacher/articles', payload, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('保存成功')
    articleDialogVisible.value = false
    articleSearch.value = ''
    articleCategory.value = '全部'
    articlePage.value = 1
    fetchArticles()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    savingArticle.value = false
  }
}

const deleteArticle = async (id) => {
  if (deletingArticleIds.value.includes(id)) return
  deletingArticleIds.value = [...deletingArticleIds.value, id]
  try {
    await ElMessageBox.confirm('确定要删除这篇文章吗？', '警告', { type: 'warning' })
    const token = localStorage.getItem('token')
    await axios.delete(`/api/teacher/articles/${id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('删除成功')
    fetchArticles()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close' && error !== 'closed') ElMessage.error('删除失败')
  } finally {
    deletingArticleIds.value = deletingArticleIds.value.filter(articleId => articleId !== id)
  }
}

const openArticle = (id) => router.push(`/article/${id}`)

// Teachers
const teachers = ref([])
const loadingTeachers = ref(false)
const teacherLoadError = ref(false)
const teacherDialogVisible = ref(false)
const teacherForm = ref({
  user_id: 1,
  title: '',
  intro: '',
  location: '',
  time_slots_str: '[]'
})

const fetchTeachers = async () => {
  loadingTeachers.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/teacher/teachers_profiles', {
      headers: { Authorization: `Bearer ${token}` }
    })
    teachers.value = res.data
    teacherLoadError.value = false
  } catch (error) {
    teacherLoadError.value = true
    ElMessage.error('获取老师列表失败')
  } finally {
    loadingTeachers.value = false
  }
}

const openTeacherDialog = (row) => {
  if (!currentTeacherId || (row && String(row.user_id) !== String(currentTeacherId))) { ElMessage.error('仅可编辑本人档案'); return }
  if (row) {
    teacherForm.value = {
      user_id: row.user_id,
      title: row.title,
      intro: row.intro,
      location: row.location,
      time_slots_str: JSON.stringify(row.time_slots || [])
    }
  } else {
    teacherForm.value = {
      user_id: currentTeacherId,
      title: '',
      intro: '',
      location: '',
      time_slots_str: '[]'
    }
  }
  teacherDialogVisible.value = true
}

const submitTeacher = async () => {
  try {
    const token = localStorage.getItem('token')
    let timeSlots = []
    try {
      timeSlots = JSON.parse(teacherForm.value.time_slots_str)
    } catch (e) {
      ElMessage.error('可预约时段 JSON 格式错误')
      return
    }
    
    const payload = {
      user_id: teacherForm.value.user_id,
      title: teacherForm.value.title,
      intro: teacherForm.value.intro,
      location: teacherForm.value.location,
      time_slots: timeSlots
    }
    
    await axios.post('/api/teacher/teachers_profiles', payload, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('保存成功')
    teacherDialogVisible.value = false
    fetchTeachers()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return d.toLocaleString()
}

onMounted(() => {
  fetchArticles()
  fetchTeachers()
})
</script>

<style scoped>
.content-container {
  background: var(--surface);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--gray-900) 2%, transparent);
  min-height: calc(100vh - 140px);
}

.content-tabs {
  margin-top: -10px;
}

.action-bar {
  margin-bottom: 20px;
  display: flex;
  justify-content: flex-end;
}
.article-toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.article-toolbar :deep(.el-input) { max-width: 320px; }
.article-toolbar :deep(.el-select) { width: 180px; }
.pagination-wrapper { display: flex; justify-content: center; margin-top: 16px; }

.help-text {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: 10px;
  line-height: 1.2;
}

.teacher-avatar-small {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--brand-600);
  color: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.business-table-wrap :deep(.el-table) { min-width: 760px; }
@media (max-width: 760px) {
  .content-container { padding: 14px; }
  .action-bar { justify-content: stretch; }
  .action-bar :deep(.el-button) { width: 100%; }
  .article-toolbar { flex-direction: column; }
  .article-toolbar :deep(.el-input), .article-toolbar :deep(.el-select) { max-width: none; width: 100%; }
}
</style>
