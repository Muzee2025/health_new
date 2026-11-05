<template>
  <div v-if="!studentData" class="detail-state" role="status">
    <p v-if="detailLoading">正在加载学生档案…</p>
    <template v-else><p>{{ detailError || '学生档案暂时无法显示。' }}</p><el-button type="primary" plain @click="fetchStudentDetail">重新加载</el-button></template>
  </div>
  <div class="detail-container business-page" v-else>
    <div class="header-card">
      <el-page-header @back="$router.back()" title="返回" class="page-header">
        <template #content>
          <div class="header-title-wrapper">
            <div class="text-avatar" :style="{ backgroundColor: getAvatarColor(studentData.student_info.name) }">
              {{ getSurname(studentData.student_info.name) }}
            </div>
            <span class="header-title"><span>{{ studentData.student_info.name }}</span><span>的心理档案</span></span>
          </div>
        </template>
        <template #extra>
          <el-button type="warning" plain :loading="exporting" :disabled="exporting" @click="exportWord">
            <el-icon><LibraryIcon name="report"  /></el-icon> 导出个人心理报告 (Word)
          </el-button>
        </template>
      </el-page-header>
    </div>
    
    <div class="content-grid">
      <!-- Left Column -->
      <div class="left-col">
        <!-- Personal Info -->
        <div class="info-card">
          <h3 class="card-title">基本信息</h3>
          <div class="info-list">
            <div class="info-item">
              <span class="label">姓名</span>
              <span class="value">{{ studentData.student_info.name }}</span>
            </div>
            <div class="info-item">
              <span class="label">学号</span>
              <span class="value">{{ studentData.student_info.student_id }}</span>
            </div>
            <div class="info-item">
              <span class="label">班级</span>
              <span class="value">{{ studentData.student_info.class_name || '暂无' }}</span>
            </div>
            <div class="info-item">
              <span class="label">辅导员</span>
              <span class="value">{{ studentData.student_info.advisor || '暂无' }}</span>
            </div>
            <div class="info-item">
              <span class="label">联系电话</span>
              <span class="value">{{ studentData.student_info.phone || '暂无' }}</span>
            </div>
          </div>
        </div>

        <!-- AI Analysis -->
        <div class="info-card ai-card">
          <h3 class="card-title"><el-icon><LibraryIcon name="audit"  /></el-icon> 风险预警分析与建议</h3>
          <p class="ai-text">{{ studentData.ai_analysis }}</p>
        </div>

        <!-- Risk Warning Timeline -->
        <div class="info-card">
          <h3 class="card-title">风险预警时间轴</h3>
          <div class="risk-timeline">
            <el-timeline>
              <el-timeline-item
                v-for="item in riskTimelineData"
                :key="item.id"
                :timestamp="formatDate(item.date)"
                :type="item.type"
                :color="item.color"
                :icon="item.icon"
              >
                <div class="timeline-content">
                  <span class="timeline-title">{{ item.title }}</span>
                  <span v-if="item.score" class="timeline-score">得分: {{ item.score }}</span>
                </div>
              </el-timeline-item>
              <LibraryEmpty v-if="!riskTimelineData.length" description="暂无时间轴记录" :image-size="60" />
            </el-timeline>
          </div>
        </div>

        <!-- Intervention Records -->
        <div class="info-card">
          <h3 class="card-title">教师干预记录</h3>
          <div class="intervention-add">
            <el-input v-model="newRecordText" type="textarea" :rows="3" placeholder="添加新的干预记录..." />
            <el-button type="primary" class="add-btn" @click="submitIntervention" :disabled="!newRecordText.trim()">保存记录</el-button>
          </div>
          <div class="intervention-list">
            <el-timeline>
              <el-timeline-item
                v-for="record in studentData.intervention_records"
                :key="record.id"
                :timestamp="formatDate(record.created_at)"
                type="primary"
              >
                <div class="record-content">
                  <p>{{ record.notes }}</p>
                  <small class="record-date">记录日期: {{ record.record_date }}</small>
                </div>
              </el-timeline-item>
              <LibraryEmpty v-if="!studentData.intervention_records?.length" description="暂无干预记录" :image-size="60" />
            </el-timeline>
          </div>
        </div>
      </div>

      <!-- Right Column -->
      <div class="right-col">
        <!-- AI Chat History (Desensitized) -->
        <div class="info-card">
          <h3 class="card-title">最近对话记录 (脱敏)</h3>
          <div class="chat-sessions-list" v-if="studentData.desensitized_chats && studentData.desensitized_chats.length > 0">
            <el-collapse accordion>
              <el-collapse-item v-for="(session, idx) in studentData.desensitized_chats" :key="session.session_id" :title="`${formatDate(session.created_at)} - ${session.title}`" :name="idx">
                <div class="chat-messages">
                  <div v-for="(msg, midx) in session.messages" :key="midx" :class="['chat-msg', msg.role === 'user' ? 'msg-user' : 'msg-ai']">
                    <div class="msg-header">
                      <span class="msg-role">{{ msg.role === 'user' ? '学生' : 'AI' }}</span>
                      <span class="msg-time">{{ formatDate(msg.created_at) }}</span>
                    </div>
                    <div class="msg-content" :class="{'text-red': msg.is_crisis}">
                      {{ msg.content }}
                    </div>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
          <LibraryEmpty v-else description="暂无对话记录" :image-size="60" />
        </div>

        <!-- Appointments & Treehole -->
        <div class="bottom-grid mt-20">
          <div class="info-card flex-col">
            <h3 class="card-title">预约记录</h3>
            <div class="business-table-wrap"><el-table :data="studentData.appointments" style="width: 100%" height="250" stripe empty-text="暂无预约记录。">
              <el-table-column prop="time_slot" label="时间" width="160" />
              <el-table-column prop="teacher_name" label="咨询老师" />
              <el-table-column prop="status" label="状态">
                <template #default="scope">
                  <el-tag :type="getStatusType(scope.row.status)">
                    {{ getStatusText(scope.row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table></div>
          </div>
          
          <div class="info-card flex-col">
            <h3 class="card-title">树洞发言汇总 (隐私保护)</h3>
            <div class="treehole-list">
              <el-timeline>
                <el-timeline-item
                  v-for="post in studentData.treehole_summary"
                  :key="post.id"
                  :timestamp="formatDate(post.created_at)"
                >
                  <div class="treehole-tags">
                    <span class="tag-label">提取标签/情绪：</span>
                    <el-tag v-if="post.emotion_keywords" type="danger" size="small" class="mr-5">{{ post.emotion_keywords }}</el-tag>
                    <el-tag v-if="post.tags" type="info" size="small">{{ post.tags }}</el-tag>
                    <span v-if="!post.emotion_keywords && !post.tags" class="no-tags">无明显情绪标签</span>
                  </div>
                </el-timeline-item>
                <LibraryEmpty v-if="!studentData.treehole_summary?.length" description="暂无树洞发言" :image-size="60" />
              </el-timeline>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { interventionIcon } from '../../design/icon-registry'
import { businessColor } from '../../styles/business-theme.js'
import { ref, onMounted, onUnmounted, computed, markRaw } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElPageHeader, ElButton, ElIcon, ElTimeline, ElTimelineItem, ElInput, ElCollapse, ElCollapseItem, ElTable, ElTableColumn, ElTag } from 'element-plus'

const route = useRoute()
const studentData = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const newRecordText = ref('')
const exporting = ref(false)

const exportWord = async () => {
  if (exporting.value) return
  exporting.value = true
  try {
    const response = await axios.get(`/api/advanced-teacher/students/${encodeURIComponent(route.params.id)}/export/docx`, { responseType: 'blob' })
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const studentName = studentData.value?.student_info?.name || '学生'
    link.download = `${studentName}-心理档案.docx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('已导出 Word 报告')
  } catch (error) {
    ElMessage.error(error?.response?.status === 404 || error?.response?.status === 403 ? '该学生不在你的分配范围内，无法导出。' : '个体档案导出失败，请稍后重试。')
  } finally {
    exporting.value = false
  }
}

const getAvatarColor = (name) => {
  const colors = [businessColor('brand-100'), businessColor('accent-sage-soft'), businessColor('warning-100'), businessColor('warning-100'), businessColor('brand-100'), businessColor('accent-sage-soft')];
  const charCode = name ? name.charCodeAt(0) : 0;
  return colors[charCode % colors.length];
}

const getSurname = (name) => {
  return name ? name.charAt(0) : '未';
}

const riskTimelineData = computed(() => {
  if (!studentData.value) return []
  
  const timeline = []
  
  // Add test results
  if (studentData.value.test_history) {
    studentData.value.test_history.forEach(test => {
      const pendingReview = test.assessment_status === 'pending_professional_review' || (test.risk_level == null && ['SDS', 'SAS'].includes(test.test_type))
      const entertainmentOnly = test.assessment_status === 'entertainment_only'
      const riskLabel = test.risk_level != null ? `；服务器状态：${test.risk_level}` : ''
      timeline.push({
        id: `test_${test.id}`,
        date: test.created_at,
        type: pendingReview ? 'warning' : entertainmentOnly ? 'info' : 'primary',
        color: pendingReview ? businessColor('data-risk-mid') : businessColor('data-primary'),
        title: entertainmentOnly ? '趣味问答记录' : pendingReview ? '测评记录 · 待专业复核' : `测评记录${riskLabel}`,
        score: test.score,
      })
    })
  }
  
  // Add interventions
  if (studentData.value.intervention_records) {
    studentData.value.intervention_records.forEach(rec => {
      timeline.push({
        id: `rec_${rec.id}`,
        date: rec.created_at,
        type: 'primary',
        color: businessColor('data-primary'),
        icon: markRaw(interventionIcon),
        title: '教师干预: ' + rec.notes.substring(0, 15) + '...',
        score: null
      })
    })
  }
  
  // Sort by date descending
  return timeline.sort((a, b) => new Date(b.date) - new Date(a.date))
})

const fetchStudentDetail = async () => {
  const id = route.params.id
  detailLoading.value = true
  detailError.value = ''
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get(`/api/teacher/student/${id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (unmounted) return
    studentData.value = res.data
  } catch (error) {
    if (unmounted) return
    detailError.value = error?.response?.status === 403 || error?.response?.status === 404
      ? '该学生不在你的分配范围内，无法查看档案。'
      : '学生档案暂时无法加载，请重试。'
  } finally {
    if (!unmounted) detailLoading.value = false
  }
}

const submitIntervention = async () => {
  if (!newRecordText.value.trim()) return
  try {
    const token = localStorage.getItem('token')
    const today = new Date().toISOString().split('T')[0]
    await axios.post('/api/teacher/interventions', {
      student_id: studentData.value.student_info.id,
      record_date: today,
      notes: newRecordText.value
    }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('记录添加成功')
    newRecordText.value = ''
    fetchStudentDetail() // Refresh data
  } catch (error) {
    ElMessage.error('添加记录失败')
  }
}

const getStatusType = (status) => {
  const normalized = status === 'approved' ? 'confirmed' : status
  const map = { pending: 'warning', confirmed: 'primary', completed: 'success', cancelled: 'info' }
  return map[normalized] || 'info'
}

const getStatusText = (status) => {
  const normalized = status === 'approved' ? 'confirmed' : status
  const map = { pending: '待处理', confirmed: '已确认', completed: '已完成', cancelled: '已取消' }
  return map[normalized] || status
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return d.toLocaleString()
}

let unmounted = false
onMounted(() => {
  fetchStudentDetail()
})

onUnmounted(() => {
  unmounted = true
})
</script>

<style scoped>
.detail-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}
.detail-state { display: grid; justify-items: start; gap: 12px; padding: 28px; color: var(--text-secondary); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); }
.detail-container :deep(.business-table-wrap .el-table) { min-width: 520px; }

.header-card {
  background: var(--surface);
  padding: 20px 24px;
  border-radius: 8px;
  box-shadow: 0 1px 3px color-mix(in srgb, var(--gray-900) 5%, transparent);
}

.header-title-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
}

.text-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 20px;
}

.header-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: 20px;
  flex: 1;
  min-width: 0;
}

.left-col, .right-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.info-card {
  min-width: 0;
  background: var(--surface);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px color-mix(in srgb, var(--gray-900) 5%, transparent);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 20px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--surface-warm);
}
.info-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.label {
  color: var(--text-secondary);
  font-size: 14px;
}

.value {
  color: var(--text-primary);
  font-weight: 500;
  font-size: 14px;
}

.ai-card {
  background: linear-gradient(to right, var(--danger-100), var(--danger-100));
  border: 1px solid var(--danger-100);
}
.ai-text {
  color: var(--danger-text);
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
  overflow-wrap: anywhere;
}

.risk-timeline, .intervention-list {
  max-height: 300px;
  overflow-y: auto;
  padding-right: 10px;
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timeline-title {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.timeline-score {
  font-size: 12px;
  color: var(--text-secondary);
}

.intervention-add {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.intervention-add :deep(.el-textarea),
.intervention-add :deep(.el-textarea__inner) { width: 100%; max-width: 100%; min-width: 0; box-sizing: border-box; }
.add-btn { align-self: flex-end; max-width: 100%; }

.record-content p {
  margin: 0 0 8px 0;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
}

.record-date {
  color: var(--text-secondary);
  font-size: 12px;
}

.chart-container {
  width: 100%;
  height: 250px;
}

.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.flex-col {
  display: flex;
  flex-direction: column;
}

.treehole-list {
  height: 250px;
  overflow-y: auto;
}

.treehole-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tag-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.no-tags {
  font-size: 13px;
  color: var(--text-secondary);
  font-style: italic;
}

.mr-5 {
  margin-right: 5px;
}

.mt-20 {
  margin-top: 20px;
}

.chat-sessions-list {
  max-height: 500px;
  overflow-y: auto;
}

.chat-messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 10px;
  background-color: var(--surface-subtle);
  border-radius: 8px;
}

.chat-msg {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 80%;
}

.msg-user {
  align-self: flex-end;
  align-items: flex-end;
}

.msg-ai {
  align-self: flex-start;
  align-items: flex-start;
}

.msg-header {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  gap: 8px;
}

.msg-content {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.msg-user .msg-content {
  background-color: var(--brand-600);
  color: var(--surface);
  border-bottom-right-radius: 2px;
}

.msg-ai .msg-content {
  background-color: var(--surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-bottom-left-radius: 2px;
}

.text-red {
  color: var(--danger-text) !important;
  font-weight: 500;
}
@media (max-width: 900px) {
  .content-grid, .bottom-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 600px) {
  .header-card, .info-card { padding: 16px; }
  .page-header :deep(.el-page-header__header) { align-items: stretch; flex-direction: column; gap: 12px; }
  .page-header :deep(.el-page-header__left) { align-items: flex-start; width: 100%; min-width: 0; margin-right: 0; }
  .page-header :deep(.el-page-header__back) { flex: 0 0 auto; min-width: max-content; }
  .page-header :deep(.el-page-header__title) { white-space: nowrap; }
  .page-header :deep(.el-page-header__content) { flex: 1 1 auto; min-width: 0; }
  .page-header :deep(.el-page-header__extra) { width: 100%; margin: 0; }
  .page-header :deep(.el-page-header__extra .el-button) { width: 100%; min-height: 44px; justify-content: center; white-space: normal; line-height: 1.4; }
  .header-title-wrapper { align-items: flex-start; gap: 10px; }
  .header-title-wrapper, .header-title { min-width: 0; }
  .text-avatar { flex: 0 0 40px; width: 40px; height: 40px; font-size: 17px; }
  .header-title { display: flex; flex: 1 1 auto; flex-wrap: wrap; column-gap: .3em; font-size: 17px; line-height: 1.4; }
  .header-title > span { white-space: nowrap; }
  .info-item { align-items: flex-start; gap: 12px; }
  .value { text-align: right; overflow-wrap: anywhere; }
  .chat-msg { max-width: 94%; }
  .intervention-add :deep(.el-button) { align-self: stretch; width: 100%; margin-left: 0; }
}
</style>
