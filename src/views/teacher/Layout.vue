<template>
  <div class="app-layout xy-business">
    <!-- Sidebar -->
    <button
      class="nav-scrim"
      type="button"
      aria-hidden="true"
      tabindex="-1"
      @click="closeMobileNav"
      v-if="mobileNavOpen"
    ></button>
    <aside
      ref="sidebarRef"
      id="teacher-navigation-panel"
      class="sidebar"
      :class="{ 'mobile-open': mobileNavOpen }"
      :aria-hidden="isMobile && !mobileNavOpen ? 'true' : 'false'"
      @keydown.tab="handleNavTab"
      @click="handleNavClick"
    >
      <div class="sidebar-head">
        <router-link to="/teacher" class="logo-area" aria-label="心域智链首页"
          ><img :src="brandLogo" class="business-brand" alt="心域智链" width="152" height="52"
        /></router-link>
        <button
          class="mobile-nav-close"
          type="button"
          aria-label="关闭导航"
          @click="closeMobileNav"
        >
          <el-icon><LibraryIcon name="arrow-left" /></el-icon><span>关闭</span>
        </button>
      </div>

      <nav class="nav-menu" aria-label="教师导航" @keydown.esc="closeMobileNav">
        <div
          class="nav-group"
          :class="{
            'group-active':
              route.path.startsWith('/teacher/advanced-dashboard') ||
              route.path.startsWith('/teacher/support'),
          }"
        >
          <button
            type="button"
            class="nav-item nav-group-toggle"
            :aria-expanded="workbenchOpen"
            aria-controls="workbench-submenu"
            @click="workbenchOpen = !workbenchOpen"
          >
            <el-icon><LibraryIcon name="audit" /></el-icon><span class="nav-text">工作台</span
            ><el-icon class="nav-caret" :class="{ expanded: workbenchOpen }"
              ><LibraryIcon name="arrow-down"
            /></el-icon>
          </button>
          <div v-if="workbenchOpen" id="workbench-submenu" class="nav-submenu">
            <router-link
              to="/teacher/advanced-dashboard"
              class="nav-item nav-subitem"
              active-class="active"
              >风险工作台</router-link
            >
            <router-link to="/teacher/support" class="nav-item nav-subitem" active-class="active"
              >求助与跟进</router-link
            >
          </div>
        </div>
        <router-link
          to="/teacher/students"
          class="nav-item"
          :class="{
            active:
              route.path === '/teacher/students' || route.path.startsWith('/teacher/student/'),
          }"
          :aria-current="
            route.path === '/teacher/students' || route.path.startsWith('/teacher/student/')
              ? 'page'
              : undefined
          "
          active-class="active"
          exact-active-class="active"
        >
          <el-icon><LibraryIcon name="assessment" /></el-icon>
          <span class="nav-text">我的学生</span>
        </router-link>
        <router-link to="/teacher/appointments" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="appointment" /></el-icon>
          <span class="nav-text">预约管理</span>
        </router-link>
        <router-link to="/teacher/interventions" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="report" /></el-icon> <span class="nav-text">干预记录</span>
        </router-link>
        <router-link to="/teacher/content" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="knowledge" /></el-icon>
          <span class="nav-text">内容与档案</span>
        </router-link>

        <div class="nav-divider"></div>

        <button type="button" class="nav-item" @click="logout">
          <el-icon><LibraryIcon name="logout" /></el-icon> <span class="nav-text">退出登录</span>
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
    <div class="main-content" :inert="mobileNavOpen">
      <header class="top-header">
        <button
          ref="mobileNavTrigger"
          class="mobile-nav-trigger"
          type="button"
          aria-controls="teacher-navigation-panel"
          :aria-expanded="mobileNavOpen"
          @click="toggleMobileNav"
        >
          <el-icon><LibraryIcon name="collection" /></el-icon><span>导航</span>
        </button>
        <h1 class="page-title">{{ pageTitle }}</h1>

        <div class="header-right">
          <button
            v-if="route.path !== '/teacher/support'"
            class="primary-btn"
            @click="openInterventionDialog()"
          >
            添加干预
          </button>
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
          style="width: 100%"
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

      <el-alert
        type="info"
        :closable="false"
        title="风险类型和干预级别由教师结合已核验记录与专业判断手工填写；系统不会根据情绪标签自动预填。"
        class="mb-16"
      />
      <el-form-item label="风险类型" prop="risk_type">
        <el-input v-model="interventionForm.risk_type" placeholder="请填写已核验记录中的关注事项" />
      </el-form-item>

      <el-form-item label="干预级别" prop="intervention_level">
        <el-select
          v-model="interventionForm.intervention_level"
          placeholder="请选择干预级别"
          style="width: 100%"
        >
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
          style="width: 100%"
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

import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  ElMessage,
  ElIcon,
  ElAvatar,
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElInput,
  ElDatePicker,
  ElButton,
} from 'element-plus'
import axios from 'axios'

const router = useRouter()
const route = useRoute()
/** @type {import('vue').Ref<{ name?: string, username?: string }>} */
const user = ref({})
const mobileNavOpen = ref(false)
const mobileNavTrigger = ref(null)
const sidebarRef = ref(null)
const isMobile = ref(false)
const workbenchOpen = ref(['/teacher/advanced-dashboard', '/teacher/support'].includes(route.path))
let mediaQuery
let navFocusRequest = 0
const focusableNavItems = () =>
  [
    ...(sidebarRef.value?.querySelectorAll(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ) || []),
  ].filter((element) => element.getClientRects().length > 0)
const nextFrame = () => new Promise((resolve) => window.requestAnimationFrame(resolve))
const openMobileNav = async () => {
  const request = ++navFocusRequest
  mobileNavOpen.value = true
  await nextTick()
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await nextFrame()
    if (
      request !== navFocusRequest ||
      !mobileNavOpen.value ||
      !isMobile.value ||
      !sidebarRef.value?.isConnected
    )
      return
    const target = focusableNavItems().find((element) => {
      const style = window.getComputedStyle(element)
      return (
        style.display !== 'none' &&
        style.visibility === 'visible' &&
        !element.hasAttribute('disabled')
      )
    })
    target?.focus?.({ preventScroll: true })
    if (target && sidebarRef.value.contains(document.activeElement)) return
  }
}
const closeMobileNav = async () => {
  if (!mobileNavOpen.value) return
  navFocusRequest += 1
  mobileNavOpen.value = false
  await nextTick()
  mobileNavTrigger.value?.focus?.()
}
const toggleMobileNav = () => {
  if (mobileNavOpen.value) closeMobileNav()
  else openMobileNav()
}
const handleNavClick = (event) => {
  if (event.target.closest?.('a[href]')) closeMobileNav()
}
const handleEscape = (event) => {
  if (event.key === 'Escape') closeMobileNav()
}
const handleNavTab = (event) => {
  if (!mobileNavOpen.value || !isMobile.value || event.key !== 'Tab') return
  const items = focusableNavItems()
  if (!items.length) return
  const first = items[0]
  const last = items[items.length - 1]
  if (
    event.shiftKey &&
    (document.activeElement === first || !sidebarRef.value?.contains(document.activeElement))
  ) {
    event.preventDefault()
    last.focus()
  } else if (
    !event.shiftKey &&
    (document.activeElement === last || !sidebarRef.value?.contains(document.activeElement))
  ) {
    event.preventDefault()
    first.focus()
  }
}
const syncViewport = async (event) => {
  isMobile.value = event.matches
  if (!event.matches && mobileNavOpen.value) {
    navFocusRequest += 1
    mobileNavOpen.value = false
    await nextTick()
    sidebarRef.value?.querySelector('[aria-current="page"], .nav-item')?.focus?.()
  }
}
const students = ref([])
const interventionDialogVisible = ref(false)
const submittingIntervention = ref(false)
const interventionFormRef = ref(null)
const interventionForm = ref({
  student_id: null,
  risk_type: '',
  intervention_level: '',
  measures: '',
  date_range: [],
  owner: '',
})
const interventionRules = {
  student_id: [{ required: true, message: '请选择学生', trigger: 'change' }],
  risk_type: [{ required: true, message: '请填写风险类型', trigger: 'blur' }],
  intervention_level: [{ required: true, message: '请选择干预级别', trigger: 'change' }],
  measures: [{ required: true, message: '请填写干预措施', trigger: 'blur' }],
  date_range: [{ required: true, message: '请选择干预起止时间', trigger: 'change' }],
  owner: [{ required: true, message: '请填写负责人', trigger: 'blur' }],
}
let openInterventionHandler = null

const pageTitle = computed(() => {
  const path = route.path
  if (path.includes('advanced-dashboard')) return '工作台'
  if (path.includes('/support')) return '求助与跟进'
  if (path.startsWith('/teacher/student/')) return '学生档案'
  if (path.includes('students') || path.includes('student/')) return '学生管理'
  if (path.includes('appointments')) return '预约管理'
  if (path.includes('content')) return '内容管理'
  if (path.includes('interventions')) return '干预记录'
  return '教师后台'
})

const selectedStudent = computed(() => {
  return students.value.find((s) => s.id === interventionForm.value.student_id) || null
})

const selectedStudentInfo = computed(() => {
  const stu = selectedStudent.value
  if (!stu) return '未选择学生'
  return `${stu.name || '未命名'} / ${stu.student_id || '无学号'} / ${stu.class_name || '未分班'}`
})

const openInterventionDialog = async (payload = null) => {
  if (!students.value.length) {
    await fetchStudents()
  }
  if (!students.value.length) {
    ElMessage.warning('暂无已分配学生，暂不能添加干预记录')
    return
  }
  const today = new Date().toISOString().split('T')[0]
  const targetStudentId = payload?.student_id || null
  const targetStudentNo = payload?.student_no || ''
  const targetStudent =
    students.value.find(
      (s) => s.id === targetStudentId || (targetStudentNo && s.student_id === targetStudentNo),
    ) || null

  interventionForm.value = {
    student_id: targetStudent?.id || null,
    risk_type: payload?.risk_type || '',
    intervention_level: payload?.intervention_level || '',
    measures: payload?.measures || '',
    date_range: [today, today],
    owner: user.value.name || user.value.username || '',
  }
  interventionDialogVisible.value = true
}

const fetchStudents = async () => {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/teacher/students', {
      headers: { Authorization: `Bearer ${token}` },
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
      `干预措施：${interventionForm.value.measures}`,
    ].join('\n')

    const token = localStorage.getItem('token')
    await axios.post(
      '/api/teacher/interventions',
      {
        student_id: stu.id,
        record_date: startDate || new Date().toISOString().split('T')[0],
        notes,
      },
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )
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
  mediaQuery = window.matchMedia('(max-width: 760px)')
  isMobile.value = mediaQuery.matches
  mediaQuery.addEventListener?.('change', syncViewport)
  window.addEventListener('keydown', handleEscape)
  const userInfo = localStorage.getItem('user')
  if (userInfo) {
    try {
      user.value = JSON.parse(userInfo) || {}
    } catch {
      user.value = {}
    }
  }
  fetchStudents()
  openInterventionHandler = (event) => {
    openInterventionDialog(event.detail || null)
  }
  window.addEventListener('open-intervention-dialog', openInterventionHandler)
})
watch(
  () => route.path,
  (path) => {
    if (mobileNavOpen.value) closeMobileNav()
    if (path.startsWith('/teacher/advanced-dashboard') || path.startsWith('/teacher/support'))
      workbenchOpen.value = true
  },
)

onUnmounted(() => {
  navFocusRequest += 1
  mediaQuery?.removeEventListener?.('change', syncViewport)
  window.removeEventListener('keydown', handleEscape)
  if (openInterventionHandler) {
    window.removeEventListener('open-intervention-dialog', openInterventionHandler)
  }
})

const logout = () => {
  for (const key of ['token', 'access_token', 'role', 'user']) localStorage.removeItem(key)
  router.push('/login')
}
</script>
