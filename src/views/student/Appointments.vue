<template>
  <div class="appointments">
    <h2 class="page-title">预约心理老师</h2>
    <p class="page-desc">专业的心理老师为您提供倾听与支持，请选择合适的时间段进行预约。</p>

    <el-row :gutter="20" class="mt-30">
      <el-col :xs="24" :md="12" :lg="8" v-for="teacher in teachers" :key="teacher.id">
        <el-card shadow="hover" class="teacher-card">
          <div class="teacher-header">
            <div class="teacher-avatar">
              <img
                class="teacher-avatar-img"
                :src="teacher.avatar"
                :alt="PSYCH_TEACHER_AVATAR_ALT"
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
              <div class="location"><el-icon><Location /></el-icon> {{ teacher.location }}</div>
            </div>
          </div>
          <div class="teacher-intro">{{ teacher.intro }}</div>
          
          <el-divider border-style="dashed" />
          <div class="slots-header">可预约时间段</div>
          <div class="time-slots">
            <el-button 
              v-for="(slot, index) in teacher.time_slots" 
              :key="index"
              :type="teacher.booked_slots.includes(slot) ? 'info' : 'primary'"
              :plain="!teacher.booked_slots.includes(slot)"
              :disabled="teacher.booked_slots.includes(slot)"
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
    
    <el-card class="mt-30 table-card">
      <h3>📅 我的预约记录</h3>
      <el-table :data="appointments" style="width: 100%" stripe>
        <el-table-column prop="time_slot" label="预约时间" width="180" />
        <el-table-column prop="teacher_name" label="咨询老师" width="120" />
        <el-table-column prop="location" label="地点" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'pending' ? 'warning' : (scope.row.status === 'cancelled' ? 'info' : 'success')" round>
              {{ scope.row.status === 'pending' ? '待确认' : (scope.row.status === 'cancelled' ? '已取消' : '已确认') }}
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
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Location } from '@element-plus/icons-vue'
import {
  PSYCH_TEACHER_AVATAR_ALT,
  getPsychTeacherAvatar,
} from '../../utils/psychTeacherAvatar'

const teachers = ref([])
const appointments = ref([])

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
  try {
    const res = await axios.get('/api/student/teachers')
    const rows = Array.isArray(res.data) ? res.data : []
    teachers.value = rows.map((teacher) => ({
      ...teacher,
      avatar: resolveTeacherAvatar(teacher),
    }))
  } catch (error) {
    ElMessage.error('获取老师列表失败')
  }
}

const fetchAppointments = async () => {
  try {
    const res = await axios.get('/api/student/appointments')
    appointments.value = res.data
  } catch (error) {
    console.error(error)
  }
}

const confirmAppointment = (teacher, slot) => {
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
  color: #1F2937;
  margin-bottom: 8px;
}
.page-desc {
  color: #6B7280;
  font-size: 14px;
}
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
  border: 2px solid #E5E7EB;
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
  color: #1F2937;
  margin-bottom: 4px;
}
.title {
  font-size: 13px;
  color: #3B82F6;
  background-color: #EFF6FF;
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
  color: #9CA3AF;
  display: flex;
  align-items: center;
  gap: 4px;
}
.teacher-intro {
  font-size: 13px;
  color: #4B5563;
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
  color: #4B5563;
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
  color: #9CA3AF;
  font-style: italic;
}

.table-card {
  border-radius: 16px;
  border: none;
}
.table-card h3 {
  font-size: 16px;
  color: #374151;
  margin-bottom: 20px;
}
</style>
