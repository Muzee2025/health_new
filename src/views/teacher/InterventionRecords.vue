<template>
  <div class="intervention-container">
    <div class="filter-card">
      <el-input
        v-model="searchQuery"
        placeholder="搜索学生姓名或辅导老师"
        class="search-input"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        class="filter-date"
      />
    </div>

    <div class="table-card">
      <el-table :data="paginatedData" style="width: 100%" v-loading="loading" stripe>
        <el-table-column prop="student_name" label="学生姓名" width="150" />
        <el-table-column prop="teacher_name" label="干预教师" width="150" />
        <el-table-column prop="record_date" label="干预日期" width="150" />
        <el-table-column prop="notes" label="干预记录内容" min-width="300">
          <template #default="scope">
            <div class="notes-content">{{ scope.row.notes }}</div>
          </template>
        </el-table-column>
        <el-table-column label="系统记录时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const records = ref([])
const searchQuery = ref('')
const dateRange = ref([])

const currentPage = ref(1)
const pageSize = ref(10)

const fetchRecords = async () => {
  loading.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('http://127.0.0.1:8000/api/teacher/interventions', {
      headers: { Authorization: `Bearer ${token}` }
    })
    records.value = res.data
  } catch (error) {
    ElMessage.error('获取干预记录失败')
  } finally {
    loading.value = false
  }
}

const filteredData = computed(() => {
  return records.value.filter(r => {
    const matchSearch = (r.student_name && r.student_name.includes(searchQuery.value)) || 
                        (r.teacher_name && r.teacher_name.includes(searchQuery.value)) ||
                        (r.notes && r.notes.includes(searchQuery.value))
    
    let matchDate = true
    if (dateRange.value && dateRange.value.length === 2) {
      const start = dateRange.value[0]
      const end = dateRange.value[1]
      matchDate = r.record_date >= start && r.record_date <= end
    }
    
    return matchSearch && matchDate
  })
})

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return d.toLocaleString()
}

onMounted(() => {
  fetchRecords()
  window.addEventListener('intervention-created', fetchRecords)
})

onUnmounted(() => {
  window.removeEventListener('intervention-created', fetchRecords)
})
</script>

<style scoped>
.intervention-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.filter-card {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  gap: 16px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
}

.search-input {
  width: 300px;
}

.filter-date {
  width: 350px;
}

.table-card {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
}

.notes-content {
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
