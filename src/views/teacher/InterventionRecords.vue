<template>
  <div class="intervention-container business-page">
    <div class="filter-card business-actions">
      <el-input
        v-model="searchQuery"
        placeholder="搜索学生姓名或辅导老师"
        class="search-input"
        clearable
        aria-label="搜索学生姓名、辅导老师或干预记录"
      >
        <template #prefix>
          <el-icon><LibraryIcon name="search" /></el-icon>
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
        popper-class="teacher-intervention-date-popper"
        aria-label="按干预日期范围筛选"
      />
    </div>

    <div class="table-card business-card">
      <el-alert v-if="loadError" type="error" :closable="false" title="干预记录暂时无法加载。"
        ><el-button text type="primary" @click="fetchRecords">重新加载</el-button></el-alert
      >
      <div class="business-table-wrap">
        <el-table
          :data="paginatedData"
          style="width: 100%"
          v-loading="loading"
          stripe
          empty-text="当前筛选下没有干预记录。"
        >
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import PagedFooter from '../../components/PagedFooter.vue'
import { usePagination } from '../../composables/usePagination'
import {
  ElInput,
  ElIcon,
  ElDatePicker,
  ElTable,
  ElTableColumn,
  ElAlert,
  ElButton,
  vLoading,
} from 'element-plus'

const loading = ref(false)
const loadError = ref(false)
const records = ref([])
const searchQuery = ref('')
const dateRange = ref([])

const fetchRecords = async () => {
  loading.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/teacher/interventions', {
      headers: { Authorization: `Bearer ${token}` },
    })
    records.value = res.data
    loadError.value = false
  } catch (error) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

const filteredData = computed(() => {
  return records.value.filter((r) => {
    const matchSearch =
      (r.student_name && r.student_name.includes(searchQuery.value)) ||
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

const { currentPage, pageSize, pageSizes, paginatedData } = usePagination(filteredData)

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
  background: var(--surface);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  gap: 16px;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--gray-900) 2%, transparent);
}

.search-input {
  width: 300px;
}

.filter-card :deep(.filter-date) {
  width: 350px;
}

.table-card {
  background: var(--surface);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--gray-900) 2%, transparent);
}

.notes-content {
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .filter-card {
    align-items: stretch;
    flex-direction: column;
    padding: 14px;
  }
  .search-input {
    width: 100%;
    max-width: 100%;
    min-width: 0;
  }
  .filter-card :deep(.filter-date) {
    --el-date-editor-daterange-width: 100%;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    flex: 1 1 0;
  }
  .filter-card :deep(.filter-date .el-range-input) {
    width: 0;
    min-width: 0;
    flex: 1 1 0;
  }
  .filter-card :deep(.filter-date .el-range-separator) {
    flex: 0 0 auto;
    white-space: nowrap;
    padding-inline: 4px;
  }
  :global(.teacher-intervention-date-popper) {
    box-sizing: border-box;
    width: calc(100vw - 24px);
    max-width: calc(100vw - 24px);
    max-height: min(70dvh, calc(100dvh - 24px));
    overflow-y: auto;
  }
  :global(.teacher-intervention-date-popper .el-date-range-picker) {
    box-sizing: border-box;
    width: 100%;
  }
  :global(.teacher-intervention-date-popper .el-picker-panel__body) {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
  }
  :global(.teacher-intervention-date-popper .el-date-range-picker__content) {
    box-sizing: border-box;
    display: block;
    width: 100%;
    padding: 12px;
  }
  :global(.teacher-intervention-date-popper .el-date-range-picker__content.is-left) {
    border-right: 0;
    border-bottom: 1px solid var(--el-datepicker-inner-border-color);
  }
}
</style>
