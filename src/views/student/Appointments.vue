<template>
  <div class="appointments business-page">
    <header class="business-page__header">
      <h2 class="page-title">预约咨询</h2>
      <p class="page-desc">查看可预约的老师和时间。可预约范围由学校分配关系决定。</p>
    </header>
    <p class="support-entry">想先把问题写下来？<router-link to="/student/questions">向老师留言</router-link>，你可以在留言记录中查看回复。</p>

    <el-alert v-if="teacherError" type="error" :closable="false" show-icon :title="teacherError">
      <el-button link type="primary" @click="fetchTeachers">重新加载老师</el-button>
    </el-alert>
    <LibraryEmpty v-if="!teacherLoading && !teacherError && teachers.length === 0" description="当前没有可展示的老师信息。" />
    <el-row v-loading="teacherLoading" :gutter="20" class="mt-30" aria-label="可预约老师">
      <el-col :xs="24" :md="12" :lg="8" v-for="teacher in teachers" :key="teacher.id">
        <el-card shadow="hover" class="teacher-card">
          <div class="teacher-header">
            <div class="teacher-avatar">
              <img
                class="teacher-avatar-img"
                :src="teacher.avatar"
                :alt="PSYCH_TEACHER_AVATAR_ALT"
                width="64"
                height="64"
                loading="lazy"
                decoding="async"
                @error="handleTeacherAvatarError"
              />
            </div>
            <div class="teacher-info">
              <div class="name">{{ teacher.name }}</div>
              <div class="title">{{ teacher.title }}</div>
              <div class="direction" v-if="teacher.consultation_direction">
                <el-tag size="small" type="success" effect="plain">{{ teacher.consultation_direction }}</el-tag>
              </div>
              <div class="location"><el-icon><LibraryIcon name="location"  /></el-icon> {{ teacher.location }}</div>
            </div>
          </div>
          <div class="teacher-intro">{{ teacher.intro }}</div>
          
          <el-divider border-style="dashed" />
          <div class="slots-header">可预约时间段</div>
          <p v-if="!teacher.can_book" class="booking-note" :id="`booking-note-${teacher.id}`">需先由学校分配咨询老师</p>
          <div class="time-slots">
            <el-button 
              v-for="(slot, index) in teacher.time_slots" 
              :key="index"
              :type="teacher.booked_slots.includes(slot) ? 'info' : 'primary'"
              :plain="!teacher.booked_slots.includes(slot)"
              :disabled="!teacher.can_book || teacher.booked_slots.includes(slot)"
              :aria-describedby="!teacher.can_book ? `booking-note-${teacher.id}` : undefined"
              size="small"
              class="slot-btn"
              @click="confirmAppointment(teacher, slot)"
            >
              {{ slot }} {{ teacher.booked_slots.includes(slot) ? '(已满)' : '' }}
            </el-button>
            <div v-if="!teacher.time_slots || teacher.time_slots.length === 0" class="no-slots">
              暂无可用时间
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-alert v-if="appointmentError" class="mt-30" type="error" :closable="false" show-icon :title="appointmentError">
      <el-button link type="primary" @click="fetchAppointments">重新加载预约记录</el-button>
    </el-alert>
    <el-card class="mt-30 table-card">
      <h3 class="business-card__header"><LibraryIcon name="appointment" /> 我的预约记录</h3>
      <div class="business-table-wrap" v-loading="appointmentLoading">
      <el-table :data="appointments" style="width: 100%" stripe>
        <template #empty><LibraryEmpty description="还没有预约记录。" /></template>
        <el-table-column prop="time_slot" label="预约时间" width="180" />
        <el-table-column prop="teacher_name" label="咨询老师" width="120" />
        <el-table-column prop="location" label="地点" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="appointmentStatusType(scope.row.status)" round>
              {{ appointmentStatusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button v-if="scope.row.status !== 'cancelled'" type="danger" link size="small" @click="cancelAppointment(scope.row)">
              取消预约
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import LibraryEmpty from '../../design/LibraryEmpty.vue'
import { ElMessage, ElMessageBox, ElRow, ElCol, ElCard, ElTag, ElIcon, ElDivider, ElButton, ElTable, ElTableColumn, ElAlert } from 'element-plus'
import {
  PSYCH_TEACHER_AVATAR_ALT,
  getPsychTeacherAvatar,
} from '../../utils/psychTeacherAvatar'

const teachers = ref([])
const appointments = ref([])
const teacherLoading = ref(false)
const appointmentLoading = ref(false)
const teacherError = ref('')
const appointmentError = ref('')
const appointmentStatusLabel = (status) => ({ pending: '待确认', confirmed: '已确认', approved: '已确认', completed: '已完成', cancelled: '已取消' }[status] || status)
const appointmentStatusType = (status) => ({ pending: 'warning', confirmed: 'primary', approved: 'primary', completed: 'success', cancelled: 'info' }[status] || 'info')

const resolveTeacherAvatar = (teacher) => {
  const seed = teacher?.id ?? teacher?.user_id ?? teacher?.name ?? ''
  return getPsychTeacherAvatar(seed, teacher?.name ?? '')
}

const handleTeacherAvatarError = (event) => {
  const target = event?.target
  if (!target || target.dataset.fallbackApplied === 'true') return
  target.dataset.fallbackApplied = 'true'
  target.src = getPsychTeacherAvatar('fallback')
}

onMounted(() => {
  fetchTeachers()
  fetchAppointments()
})

const fetchTeachers = async () => {
  teacherLoading.value = true
  teacherError.value = ''
  try {
    const res = await axios.get('/api/student/teachers')
    const rows = Array.isArray(res.data) ? res.data : []
    teachers.value = rows.map((teacher) => ({
      ...teacher,
      avatar: resolveTeacherAvatar(teacher),
      can_book: teacher.can_book === true,
      time_slots: Array.isArray(teacher.time_slots) ? teacher.time_slots : [],
      booked_slots: Array.isArray(teacher.booked_slots) ? teacher.booked_slots : [],
    }))
  } catch (error) {
    teacherError.value = '老师列表暂时无法加载，请检查网络后重试。'
  } finally {
    teacherLoading.value = false
  }
}

const fetchAppointments = async () => {
  appointmentLoading.value = true
  appointmentError.value = ''
  try {
    const res = await axios.get('/api/student/appointments')
    appointments.value = Array.isArray(res.data) ? res.data : []
  } catch (error) {
    appointmentError.value = '预约记录暂时无法加载，请稍后重试。'
  } finally {
    appointmentLoading.value = false
  }
}

const confirmAppointment = (teacher, slot) => {
  if (!teacher.can_book) { ElMessage.warning('需先由学校分配咨询老师'); return }
  ElMessageBox.confirm(
    `确定要预约 ${teacher.name} 老师的 [${slot}] 吗？`,
    '确认预约',
    {
      confirmButtonText: '确定预约',
      cancelButtonText: '取消',
      type: 'info',
    }
  ).then(async () => {
    try {
      await axios.post('/api/student/appointments', {
        teacher_id: teacher.id,
        time_slot: slot
      })
      ElMessage.success('预约成功！')
      fetchTeachers() // 刷新列表状态
      fetchAppointments()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '预约失败')
    }
  }).catch(() => {
    // cancelled
  })
}

const cancelAppointment = (appointment) => {
  ElMessageBox.confirm(
    `确定要取消 [${appointment.time_slot}] 与 ${appointment.teacher_name} 老师的预约吗？`,
    '取消预约',
    {
      confirmButtonText: '确定取消',
      cancelButtonText: '暂不取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      await axios.post(`/api/student/appointments/${appointment.id}/cancel`)
      ElMessage.success('已取消预约')
      fetchTeachers()
      fetchAppointments()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '取消失败')
    }
  }).catch(() => {})
}
</script>

<style scoped>
.page-title {
  font-size: 24px;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.page-desc {
  color: var(--text-secondary);
  font-size: 14px;
}
.support-entry { margin: 14px 0 0; color: var(--text-secondary); font-size: 14px; }
.support-entry a { color: var(--brand-700); text-underline-offset: 3px; }
.mt-30 {
  margin-top: 30px;
}

.teacher-card {
  border-radius: 12px;
  border: none;
  margin-bottom: 20px;
  height: 100%;
}
.teacher-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
.teacher-avatar {
  width: 64px;
  height: 64px;
  border: 2px solid var(--border);
  border-radius: 50%;
  overflow: hidden;
  margin-right: 16px;
  flex: 0 0 auto;
}
.teacher-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.teacher-info {
  flex: 1;
}
.name {
  font-size: 18px;
  font-weight: bold;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.title {
  font-size: 13px;
  color: var(--brand-600);
  background-color: var(--brand-50);
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  margin-bottom: 4px;
}
.direction {
  margin-bottom: 4px;
}
.location {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}
.teacher-intro {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  height: 40px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.slots-header {
  font-size: 14px;
  font-weight: bold;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.time-slots {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.slot-btn {
  border-radius: 20px;
  margin: 0 !important;
}
.no-slots {
  font-size: 13px;
  color: var(--text-secondary);
  font-style: italic;
}
.booking-note { color: var(--warning-text); background: var(--warning-100); border-radius: var(--radius-md); padding: 8px 10px; margin: 0 0 12px; font-size: 13px; }

.table-card {
  border-radius: 16px;
  border: none;
}
.table-card h3 {
  font-size: 16px;
  color: var(--text-primary);
  margin-bottom: 20px;
}
.business-page__header { margin-bottom: 20px; }
.business-page__header .page-title { margin-bottom: 8px; }
.table-card :deep(.el-card__body) { min-width: 0; }
.table-card :deep(.el-table) { min-width: 620px; }
@media (max-width: 600px) {
  .mt-30 { margin-top: 20px; }
  .teacher-avatar { margin-right: 12px; }
  .table-card :deep(.el-card__body) { padding: 16px; }
}
</style>
