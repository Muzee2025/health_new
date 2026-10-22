<template>
  <div class="management-container">
    <div class="filter-card">
      <el-select v-model="filterStatus" placeholder="全部状态" clearable class="filter-select">
        <el-option label="待处理" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已完成" value="completed" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
    </div>

    <div class="table-card">
      <el-table :data="paginatedData" style="width: 100%" v-loading="loading" stripe>
        <el-table-column label="头像" width="92" align="center">
          <template #default="scope">
            <img
              class="teacher-avatar-img"
              :src="resolveTeacherAvatar(scope.row)"
              :alt="PSYCH_TEACHER_AVATAR_ALT"
              loading="lazy"
              decoding="async"
              @error="handleTeacherAvatarError"
            />
          </template>
        </el-table-column>
        <el-table-column prop="student_name" label="学生姓名" width="150" />
        <el-table-column prop="teacher_name" label="预约老师" width="150" />
        <el-table-column prop="time_slot" label="预约时间段" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="right">
          <template #default="scope">
            <el-dropdown trigger="click" @command="handleStatusChange(scope.row.id, $event)">
              <el-button type="primary" size="small" :disabled="scope.row.status === 'completed' || scope.row.status === 'cancelled'">
                修改状态<el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="approved" :disabled="scope.row.status !== 'pending'">通过</el-dropdown-item>
                  <el-dropdown-item command="completed" :disabled="scope.row.status !== 'approved'">完成</el-dropdown-item>
                  <el-dropdown-item command="cancelled" :disabled="scope.row.status === 'completed'">取消</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="filteredData.length"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  PSYCH_TEACHER_AVATAR_ALT,
  getPsychTeacherAvatar,
} from '../../utils/psychTeacherAvatar'

const loading = ref(false)
const appointments = ref([])
const filterStatus = ref('')

const currentPage = ref(1)
const pageSize = ref(10)

const resolveTeacherAvatar = (row) => {
  const seed = row?.teacher_id ?? row?.teacher_name ?? row?.id ?? ''
  return getPsychTeacherAvatar(seed, row?.teacher_name ?? '')
}

const handleTeacherAvatarError = (event) => {
  const target = event?.target
  if (!target || target.dataset.fallbackApplied === 'true') return
  target.dataset.fallbackApplied = 'true'
  target.src = getPsychTeacherAvatar('fallback')
}

const fetchAppointments = async () => {
  loading.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/teacher/appointments', {
      headers: { Authorization: `Bearer ${token}` }
    })
    appointments.value = res.data
  } catch (error) {
    console.error('Failed to fetch appointments', error)
  } finally {
    loading.value = false
  }
}

const handleStatusChange = async (id, status) => {
  try {
    const token = localStorage.getItem('token')
    await axios.post(`/api/teacher/appointments/${id}/status?status=${status}`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('状态修改成功')
    fetchAppointments()
  } catch (error) {
    ElMessage.error('状态修改失败')
  }
}

const filteredData = computed(() => {
  return appointments.value.filter(a => {
    return filterStatus.value ? a.status === filterStatus.value : true
  })
})

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

const getStatusType = (status) => {
  const map = { pending: 'warning', approved: 'primary', completed: 'success', cancelled: 'info' }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = { pending: '待处理', approved: '已通过', completed: '已完成', cancelled: '已取消' }
  return map[status] || status
}

onMounted(() => {
  fetchAppointments()
})
</script>

<style scoped>
.management-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.filter-card {
  background: var(--surface);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  gap: 16px;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--gray-900) 2%, transparent);
}

.filter-select {
  width: 200px;
}

.table-card {
  background: var(--surface);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--gray-900) 2%, transparent);
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.teacher-avatar-img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--brand-100);
  object-fit: cover;
}
</style>
