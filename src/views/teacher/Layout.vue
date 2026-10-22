<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <router-link to="/teacher" class="logo-area" aria-label="心域智链首页"><img :src="brandLogo" class="business-brand" alt="心域智链" width="152" height="52" /></router-link>

      <nav class="nav-menu" aria-label="教师导航">
        <router-link to="/teacher/advanced-dashboard" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="audit"  /></el-icon> <span class="nav-text">AI大屏与审计</span>
        </router-link>
        <router-link to="/teacher/students" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="assessment"  /></el-icon> <span class="nav-text">学生管理</span>
        </router-link>
        <router-link to="/teacher/appointments" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="appointment"  /></el-icon> <span class="nav-text">预约管理</span>

        </router-link>
        <router-link to="/teacher/content" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="knowledge"  /></el-icon> <span class="nav-text">内容管理</span>
        </router-link>
        <router-link to="/teacher/interventions" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="report"  /></el-icon> <span class="nav-text">干预记录</span>
        </router-link>

        <div class="nav-divider"></div>

        <button type="button" class="nav-item" @click="logout">
          <el-icon><LibraryIcon name="logout"  /></el-icon> <span class="nav-text">退出登录</span>
        </button>
      </nav>

      <div class="user-profile">
        <el-avatar :size="40" :src="profileAvatar" alt="教师头像" />
        <div class="user-info">
          <div class="user-name">{{ user.name || user.username }} 老师</div>
          <div class="user-email">教师工作台</div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="main-content">
      <header class="top-header">
        <h1 class="page-title">{{ pageTitle }}</h1>

        <div class="header-right">

          <button class="primary-btn" @click="openInterventionDialog()">添加干预</button>
        </div>
      </header>

      <div class="page-wrapper">
        <router-view />
      </div>
    </div>
  </div>

  <el-dialog
    v-model="interventionDialogVisible"
    title="添加干预"
    width="680px"
    :close-on-click-modal="false"
    @closed="resetInterventionForm"
  >
    <el-form
      ref="interventionFormRef"
      :model="interventionForm"
      :rules="interventionRules"
      label-width="110px"
    >
      <el-form-item label="学生" prop="student_id">
        <el-select
          v-model="interventionForm.student_id"
          placeholder="请选择学生"
          filterable
          style="width: 100%;"
          @change="handleStudentChange"
        >
          <el-option
            v-for="stu in students"
            :key="stu.id"
            :label="`${stu.name || '未命名'} / ${stu.student_id || '无学号'} / ${stu.class_name || '未分班'}`"
            :value="stu.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="学生信息">
        <div class="readonly-block">
          {{ selectedStudentInfo }}
        </div>
      </el-form-item>

      <el-form-item label="风险类型" prop="risk_type">
        <el-input v-model="interventionForm.risk_type" placeholder="如：学业压力、危机倾向等" />
      </el-form-item>

      <el-form-item label="干预级别" prop="intervention_level">
        <el-select v-model="interventionForm.intervention_level" placeholder="请选择干预级别" style="width: 100%;">
          <el-option label="紧急干预" value="紧急干预" />
          <el-option label="重点关注" value="重点关注" />
          <el-option label="持续观察" value="持续观察" />
        </el-select>
      </el-form-item>

      <el-form-item label="干预措施" prop="measures">
        <el-input
          v-model="interventionForm.measures"
          type="textarea"
          :rows="4"
          placeholder="请描述具体干预措施和执行计划"
        />
      </el-form-item>

      <el-form-item label="干预时间" prop="date_range">
        <el-date-picker
          v-model="interventionForm.date_range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 100%;"
        />
      </el-form-item>

      <el-form-item label="负责人" prop="owner">
        <el-input v-model="interventionForm.owner" placeholder="负责人姓名" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="interventionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingIntervention" @click="submitIntervention">
          提交
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { getVisualAsset } from '../../design/asset-registry'
const brandLogo = getVisualAsset('brandLogo').url
const profileAvatar = getVisualAsset('teacherAvatar').url

import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const route = useRoute()
const user = ref({})
const students = ref([])
const interventionDialogVisible = ref(false)
const submittingIntervention = ref(false)
const interventionFormRef = ref(null)
const interventionForm = ref({
  student_id: null,
  risk_type: '',
  intervention_level: '重点关注',
  measures: '',
  date_range: [],
  owner: ''
})
const interventionRules = {
  student_id: [{ required: true, message: '请选择学生', trigger: 'change' }],
  risk_type: [{ required: true, message: '请填写风险类型', trigger: 'blur' }],
  intervention_level: [{ required: true, message: '请选择干预级别', trigger: 'change' }],
  measures: [{ required: true, message: '请填写干预措施', trigger: 'blur' }],
  date_range: [{ required: true, message: '请选择干预起止时间', trigger: 'change' }],
  owner: [{ required: true, message: '请填写负责人', trigger: 'blur' }]
}
let openInterventionHandler = null

const pageTitle = computed(() => {
  const path = route.path
  if (path.includes('advanced-dashboard')) return 'AI大屏与审计'
  if (path.includes('students') || path.includes('student/')) return '学生管理'
  if (path.includes('appointments')) return '预约管理'
  if (path.includes('content')) return '内容管理'
  if (path.includes('interventions')) return '干预记录'
  return '教师后台'
})

const selectedStudent = computed(() => {
  return students.value.find(s => s.id === interventionForm.value.student_id) || null
})

const selectedStudentInfo = computed(() => {
  const stu = selectedStudent.value
  if (!stu) return '未选择学生'
  return `${stu.name || '未命名'} / ${stu.student_id || '无学号'} / ${stu.class_name || '未分班'}`
})

const inferredRiskType = (student) => {
  if (!student) return ''
  if (student.risk_level === 'red') return '高风险预警'
  if (student.risk_level === 'yellow') return '中风险关注'
  if (student.risk_level === 'green') return '低风险观察'
  return ''
}

const inferredInterventionLevel = (student) => {
  if (!student) return '重点关注'
  if (student.risk_level === 'red') return '紧急干预'
  if (student.risk_level === 'yellow') return '重点关注'
  return '持续观察'
}

const openInterventionDialog = async (payload = null) => {
  if (!students.value.length) {
    await fetchStudents()
  }
  if (!students.value.length) {
    ElMessage.warning('请先完成风险评估或检查学生数据后再添加干预')
    return
  }
  const today = new Date().toISOString().split('T')[0]
  const targetStudentId = payload?.student_id || null
  const targetStudentNo = payload?.student_no || ''
  const targetStudent = students.value.find(
    s => s.id === targetStudentId || (targetStudentNo && s.student_id === targetStudentNo)
  ) || null

  interventionForm.value = {
    student_id: targetStudent?.id || null,
    risk_type: payload?.risk_type || inferredRiskType(targetStudent),
    intervention_level: payload?.intervention_level || inferredInterventionLevel(targetStudent),
    measures: payload?.measures || '',
    date_range: [today, today],
    owner: user.value.name || user.value.username || ''
  }
  interventionDialogVisible.value = true
}

const handleStudentChange = (studentId) => {
  const stu = students.value.find(s => s.id === studentId)
  if (!stu) return
  if (!interventionForm.value.risk_type) {
    interventionForm.value.risk_type = inferredRiskType(stu)
  }
  if (!interventionForm.value.intervention_level) {
    interventionForm.value.intervention_level = inferredInterventionLevel(stu)
  }
}

const fetchStudents = async () => {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/teacher/students', {
      headers: { Authorization: `Bearer ${token}` }
    })
    students.value = Array.isArray(res.data) ? res.data : []
  } catch (error) {
    ElMessage.error('获取学生数据失败')
  }
}

const resetInterventionForm = () => {
  interventionFormRef.value?.clearValidate?.()
}

const submitIntervention = async () => {
  await interventionFormRef.value?.validate()
  const stu = selectedStudent.value
  if (!stu) {
    ElMessage.warning('请先完成风险评估')
    return
  }

  submittingIntervention.value = true
  try {
    const [startDate, endDate] = interventionForm.value.date_range || []
    const notes = [
      `风险类型：${interventionForm.value.risk_type}`,
      `干预级别：${interventionForm.value.intervention_level}`,
      `干预时间：${startDate || '-'} 至 ${endDate || '-'}`,
      `负责人：${interventionForm.value.owner}`,
      `干预措施：${interventionForm.value.measures}`
    ].join('\n')

    const token = localStorage.getItem('token')
    await axios.post('/api/teacher/interventions', {
      student_id: stu.id,
      record_date: startDate || new Date().toISOString().split('T')[0],
      notes
    }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('干预记录保存成功')
    interventionDialogVisible.value = false
    window.dispatchEvent(new CustomEvent('intervention-created'))
  } catch (error) {
    ElMessage.error('提交干预失败，请稍后重试')
  } finally {
    submittingIntervention.value = false
  }
}

onMounted(() => {
  const userInfo = localStorage.getItem('user')
  if (userInfo) {
    try { user.value = JSON.parse(userInfo) || {} } catch { user.value = {} }
  }
  fetchStudents()
  openInterventionHandler = (event) => {
    openInterventionDialog(event.detail || null)
  }
  window.addEventListener('open-intervention-dialog', openInterventionHandler)
})

onUnmounted(() => {
  if (openInterventionHandler) {
    window.removeEventListener('open-intervention-dialog', openInterventionHandler)
  }
})

const logout = () => {
  for (const key of ['token', 'access_token', 'role', 'user']) localStorage.removeItem(key)
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  --ui-primary: var(--brand-600);
  --ui-primary-hover: var(--brand-600);
  --ui-bg: var(--surface-warm);
  --ui-card: var(--surface);
  --ui-text: var(--text-primary);
  --ui-muted: var(--text-secondary);
  --ui-border: var(--border);
  --ui-radius: 12px;
  --ui-shadow: 0 2px 8px color-mix(in srgb, var(--gray-900) 6%, transparent);
  display: flex;
  min-height: 100vh;
  background-color: var(--ui-bg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background-color: var(--ui-bg);
  display: flex;
  flex-direction: column;
  padding: 30px 0;
  border-right: 1px solid var(--ui-border);
}

.logo-area {
  display: flex;
  align-items: center;
  padding: 0 30px;
  margin-bottom: 40px;
  font-size: 18px;
  font-weight: bold;
  color: var(--text-primary);
}

.logo-icon {
  font-size: 24px;
  margin-right: 10px;
}

.nav-menu {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  margin: 0 10px;
  border-radius: var(--ui-radius);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
  cursor: pointer;
  position: relative;
}

.nav-item .el-icon {
  font-size: 18px;
  margin-right: 15px;
  color: var(--text-secondary);
}

.nav-item:hover, .nav-item.active {
  color: var(--ui-primary);
  font-weight: 500;
}

.nav-item.active {
  background-color: color-mix(in srgb, var(--brand-500) 14%, transparent);
  color: var(--ui-primary);
}

.nav-item.active .el-icon {
  color: var(--ui-primary);
}

.badge {
  background-color: var(--success-text);
  color: var(--surface);
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  margin-left: auto;
  text-transform: uppercase;
  font-weight: bold;
}

.nav-divider {
  height: 1px;
  background-color: color-mix(in srgb, var(--gray-900) 5%, transparent);
  margin: 20px 30px;
}

/* User Profile */
.user-profile {
  display: flex;
  align-items: center;
  padding: 0 30px;
  margin-top: auto;
}

.user-info {
  margin-left: 12px;
}

.teacher-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: var(--ui-primary);
  color: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: var(--ui-shadow);
}

.user-name {
  font-size: 14px;
  font-weight: bold;
  color: var(--text-primary);
}

.user-email {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* Main Content */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 30px 40px;
}

.page-title {
  font-size: 24px;
  font-weight: bold;
  color: var(--text-primary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.search-box {
  display: flex;
  align-items: center;
  background-color: var(--ui-card);
  padding: 10px 16px;
  border-radius: var(--ui-radius);
  width: 300px;
  box-shadow: var(--ui-shadow);
  margin-left: auto;
}

.search-icon {
  color: var(--text-secondary);
  margin-right: 10px;
  font-size: 18px;
}

.search-box input {
  border: none;
  outline: none;
  background: transparent;
  width: 100%;
  font-size: 14px;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: var(--ui-radius);
  border: 1px solid var(--ui-border);
  background: var(--ui-card);
  padding: 8px;
  font-size: 18px;
  color: var(--ui-text);
  cursor: pointer;
  transition: all .2s ease;
}

.icon-btn:hover {
  color: var(--ui-primary);
  border-color: var(--ui-primary);
}

.avatar-group {
  display: flex;
  align-items: center;
  background-color: var(--ui-card);
  padding: 4px 12px 4px 4px;
  border-radius: var(--ui-radius);
  box-shadow: var(--ui-shadow);
}

.overlap-avatar {
  border: 2px solid var(--surface);
}

.avatar-count {
  font-size: 13px;
  font-weight: bold;
  margin-left: 8px;
  color: var(--text-primary);
}

.primary-btn {
  background-color: var(--ui-primary);
  color: var(--surface);
  border: none;
  padding: 10px 20px;
  border-radius: var(--ui-radius);
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
  box-shadow: var(--ui-shadow);
}

.primary-btn:hover {
  background-color: var(--ui-primary-hover);
}

.readonly-block {
  width: 100%;
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius);
  padding: 8px 12px;
  background: var(--surface-subtle);
  color: var(--text-primary);
}

/* Page Wrapper */
.page-wrapper {
  flex: 1;
  padding: 0 40px 40px 40px;
  overflow-y: auto;
}

.page-wrapper :deep(.el-card) {
  border-radius: var(--ui-radius);
  border: 1px solid var(--ui-border);
  box-shadow: var(--ui-shadow);
}

.page-wrapper :deep(.el-button--primary) {
  background: var(--ui-primary);
  border-color: var(--ui-primary);
  border-radius: var(--ui-radius);
}

.page-wrapper :deep(.el-button--primary:hover) {
  background: var(--ui-primary-hover);
  border-color: var(--ui-primary-hover);
}

.page-wrapper :deep(.el-table) {
  border-radius: var(--ui-radius);
  overflow: hidden;
}

.page-wrapper :deep(.el-table th.el-table__cell) {
  background: var(--surface-subtle);
}

.page-wrapper :deep(.el-input__wrapper),
.page-wrapper :deep(.el-textarea__inner),
.page-wrapper :deep(.el-select__wrapper),
.page-wrapper :deep(.el-date-editor.el-input__wrapper) {
  border-radius: var(--ui-radius);
}

@media (max-width: 1024px) {
  .sidebar {
    width: 212px;
  }
  .top-header {
    padding: 20px 24px;
    flex-wrap: wrap;
  }
  .page-wrapper {
    padding: 0 24px 24px 24px;
  }
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    padding: 16px 0;
  }
  .top-header {
    padding: 16px;
  }
  .search-box {
    width: 100%;
    order: 3;
  }
  .page-wrapper {
    padding: 0 16px 16px;
  }
}
</style>
