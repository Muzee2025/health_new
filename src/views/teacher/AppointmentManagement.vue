<template>
  <div class="management-container business-page">
    <div class="filter-card business-actions">
      <el-select
        v-model="filterStatus"
        placeholder="全部状态"
        aria-label="按预约状态筛选"
        clearable
        class="filter-select"
      >
        <el-option label="待处理" value="pending" />
        <el-option label="已确认" value="confirmed" />
        <el-option label="已完成" value="completed" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
    </div>

    <div class="table-card business-card">
      <el-alert v-if="loadError" type="error" :closable="false" title="预约列表暂时无法加载。"
        ><el-button text type="primary" @click="fetchAppointments">重新加载</el-button></el-alert
      >
      <div class="business-table-wrap">
        <el-table
          :data="paginatedData"
          style="width: 100%"
          v-loading="loading"
          stripe
          empty-text="当前筛选下没有预约记录。"
        >
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
                <el-button
                  type="primary"
                  size="small"
                  :disabled="scope.row.status === 'completed' || scope.row.status === 'cancelled'"
                >
                  修改状态<el-icon class="el-icon--right"
                    ><LibraryIcon name="arrow-down"
                  /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="confirmed" :disabled="scope.row.status !== 'pending'"
                      >确认预约</el-dropdown-item
                    >
                    <el-dropdown-item command="completed" :disabled="!isConfirmed(scope.row.status)"
                      >完成</el-dropdown-item
                    >
                    <el-dropdown-item
                      command="cancelled"
                      :disabled="scope.row.status === 'completed'"
                      >取消</el-dropdown-item
                    >
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <PagedFooter
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="pageSizes"
        :total="filteredData.length"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import PagedFooter from '../../components/PagedFooter.vue'
import { usePagination } from '../../composables/usePagination'
import {
  ElMessage,
  ElSelect,
  ElOption,
  ElTable,
  ElTableColumn,
  ElTag,
  ElDropdown,
  ElButton,
  ElIcon,
  ElDropdownMenu,
  ElDropdownItem,
  ElAlert,
  vLoading,
} from 'element-plus'
import { PSYCH_TEACHER_AVATAR_ALT, getPsychTeacherAvatar } from '../../utils/psychTeacherAvatar'

const loading = ref(false)
const loadError = ref(false)
const appointments = ref([])
const filterStatus = ref('')

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
      headers: { Authorization: `Bearer ${token}` },
    })
    appointments.value = res.data
    loadError.value = false
  } catch (error) {
    console.error('Failed to fetch appointments', error)
    loadError.value = true
  } finally {
    loading.value = false
  }
}

const handleStatusChange = async (id, status) => {
  try {
    const token = localStorage.getItem('token')
    await axios.post(
      `/api/teacher/appointments/${id}/status?status=${status}`,
      {},
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )
    ElMessage.success('状态修改成功')
    fetchAppointments()
  } catch (error) {
    ElMessage.error('状态修改失败')
  }
}

const filteredData = computed(() => {
  return appointments.value.filter((a) => {
    return filterStatus.value ? normalizeStatus(a.status) === filterStatus.value : true
  })
})

const { currentPage, pageSize, pageSizes, paginatedData } = usePagination(filteredData)
const normalizeStatus = (status) => (status === 'approved' ? 'confirmed' : status)
const isConfirmed = (status) => normalizeStatus(status) === 'confirmed'

const getStatusText = (status) => {
  const normalized = normalizeStatus(status)
  const map = { pending: '待处理', confirmed: '已确认', completed: '已完成', cancelled: '已取消' }
  return map[normalized] || status
}

const getStatusType = (status) => {
  const map = { pending: 'warning', confirmed: 'primary', completed: 'success', cancelled: 'info' }
  return map[normalizeStatus(status)] || 'info'
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

@media (max-width: 760px) {
  .filter-card {
    padding: 14px;
  }
  .filter-select {
    width: 100%;
  }
}

.teacher-avatar-img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--brand-100);
  object-fit: cover;
}
</style>
