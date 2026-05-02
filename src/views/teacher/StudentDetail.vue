<template>
  <div class="detail-container" v-if="studentData">
    <div class="header-card">
      <el-page-header @back="$router.back()" title="返回" class="page-header">
        <template #content>
          <div class="header-title-wrapper">
            <div class="text-avatar" :style="{ backgroundColor: getAvatarColor(studentData.student_info.name) }">
              {{ getSurname(studentData.student_info.name) }}
            </div>
            <span class="header-title">{{ studentData.student_info.name }} 的心理档案</span>
          </div>
        </template>
        <template #extra>
          <el-button type="warning" plain @click="exportWord">
            <el-icon><Document /></el-icon> 导出个人心理报告 (Word)
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
              <span class="value">默认班级</span> <!-- Mock -->
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
          <h3 class="card-title"><el-icon><Monitor /></el-icon> 风险预警分析与建议</h3>
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
              <el-empty v-if="!riskTimelineData.length" description="暂无时间轴记录" :image-size="60" />
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
              <el-empty v-if="!studentData.intervention_records?.length" description="暂无干预记录" :image-size="60" />
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
          <el-empty v-else description="暂无对话记录" :image-size="60" />
        </div>

        <!-- Appointments & Treehole -->
        <div class="bottom-grid mt-20">
          <div class="info-card flex-col">
            <h3 class="card-title">预约记录</h3>
            <el-table :data="studentData.appointments" style="width: 100%" height="250" stripe>
              <el-table-column prop="time_slot" label="时间" width="160" />
              <el-table-column prop="teacher_name" label="咨询老师" />
              <el-table-column prop="status" label="状态">
                <template #default="scope">
                  <el-tag :type="getStatusType(scope.row.status)">
                    {{ getStatusText(scope.row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
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
                <el-empty v-if="!studentData.treehole_summary?.length" description="暂无树洞发言" :image-size="60" />
              </el-timeline>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, Flag, Document } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const route = useRoute()
const studentData = ref(null)
const chartRef = ref(null)
let chartInstance = null
const newRecordText = ref('')

const exportWord = async () => {
  try {
    const response = await axios.post(
      '/api/advanced-teacher/export/compliance-report',
      { chart_snapshots: [] },
      { responseType: 'blob' }
    )
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '个人心理报告.docx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('已导出 Word 报告')
  } catch (error) {
    ElMessage.error('导出 Word 报告失败')
  }
}

const getAvatarColor = (name) => {
  const colors = ['#BFDBFE', '#BBF7D0', '#FFEDD5', '#FED7AA', '#E9D5FF', '#A7F3D0'];
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
      let color = '#10B981'
      let type = 'success'
      let title = '心理测评 (健康)'
      if (test.risk_level === 'red' || test.score >= 60) {
        color = '#EF4444'
        type = 'danger'
        title = '心理测评 (高风险)'
      } else if (test.risk_level === 'yellow' || test.score >= 50) {
        color = '#F59E0B'
        type = 'warning'
        title = '心理测评 (亚健康)'
      }
      
      timeline.push({
        id: `test_${test.id}`,
        date: test.created_at,
        type,
        color,
        title,
        score: test.score
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
        color: '#3B82F6',
        icon: shallowRef(Flag),
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
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get(`http://127.0.0.1:8000/api/teacher/student/${id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    studentData.value = res.data
    nextTick(() => {
      initChart()
    })
  } catch (error) {
    ElMessage.error('获取学生详情失败')
  }
}

const submitIntervention = async () => {
  if (!newRecordText.value.trim()) return
  try {
    const token = localStorage.getItem('token')
    const today = new Date().toISOString().split('T')[0]
    await axios.post('http://127.0.0.1:8000/api/teacher/interventions', {
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
  const map = { pending: 'warning', approved: 'primary', completed: 'success', cancelled: 'info' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { pending: '待处理', approved: '已通过', completed: '已完成', cancelled: '已取消' }
  return map[status] || status
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return d.toLocaleString()
}

const initChart = () => {
  if (!chartRef.value || !studentData.value.test_history) return
  
  const history = studentData.value.test_history
  const dates = history.map(item => new Date(item.created_at).toLocaleDateString())
  const scores = history.map(item => item.score)
  
  chartInstance = echarts.init(chartRef.value)
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280' }
    },
    yAxis: {
      type: 'value',
      max: 100, // Assume 100 max for general tests
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#E5E7EB', type: 'dashed' } },
      axisLabel: { color: '#6B7280' }
    },
    visualMap: {
      show: false,
      pieces: [
        { gt: 0, lte: 40, color: '#10B981' }, // Green
        { gt: 40, lte: 60, color: '#F59E0B' }, // Yellow
        { gt: 60, lte: 100, color: '#EF4444' }  // Red
      ],
      outOfRange: { color: '#9CA3AF' }
    },
    series: [
      {
        name: '测评得分',
        type: 'line',
        data: scores,
        smooth: true,
        symbolSize: 8,
        markLine: {
          silent: true,
          lineStyle: { color: '#9CA3AF', type: 'dashed' },
          data: [
            { yAxis: 40, label: { formatter: '轻度分界' } },
            { yAxis: 60, label: { formatter: '重度分界' } }
          ]
        }
      }
    ]
  }
  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  fetchStudentDetail()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
.detail-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.header-card {
  background: #FFFFFF;
  padding: 20px 24px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
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
  color: #111827;
  font-size: 20px;
}

.header-title {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 20px;
  flex: 1;
}

.left-col, .right-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-card {
  background: #FFFFFF;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
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
  border-bottom: 1px solid #F3F4F6;
}
.info-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.label {
  color: #6B7280;
  font-size: 14px;
}

.value {
  color: #111827;
  font-weight: 500;
  font-size: 14px;
}

.ai-card {
  background: linear-gradient(to right, #FEF2F2, #FFF1F2);
  border: 1px solid #FCA5A5;
}
.ai-text {
  color: #991B1B;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
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
  color: #374151;
  font-weight: 500;
}

.timeline-score {
  font-size: 12px;
  color: #6B7280;
}

.intervention-add {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.add-btn {
  align-self: flex-end;
}

.record-content p {
  margin: 0 0 8px 0;
  color: #374151;
  font-size: 14px;
  line-height: 1.5;
}

.record-date {
  color: #9CA3AF;
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
  color: #6B7280;
}

.no-tags {
  font-size: 13px;
  color: #9CA3AF;
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
  background-color: #f9fafb;
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
  color: #6b7280;
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
  background-color: #3b82f6;
  color: white;
  border-bottom-right-radius: 2px;
}

.msg-ai .msg-content {
  background-color: white;
  color: #111827;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 2px;
}

.text-red {
  color: #ef4444 !important;
  font-weight: 500;
}
</style>
