<template>
  <div class="management-container">
    <div class="filter-card">
      <el-input
        v-model="searchQuery"
        placeholder="搜索姓名或学号"
        class="search-input"
        clearable
      >
        <template #prefix>
          <el-icon><LibraryIcon name="search"  /></el-icon>
        </template>
      </el-input>
      
      <el-select v-model="filterRisk" placeholder="风险等级" clearable class="filter-select">
        <el-option label="高风险 (红)" value="red" />
        <el-option label="中风险 (黄)" value="yellow" />
        <el-option label="低风险 (绿)" value="green" />
      </el-select>

      <el-select v-model="filterClass" placeholder="辅导员" clearable class="filter-select">
        <el-option v-for="adv in uniqueAdvisors" :key="adv" :label="adv" :value="adv" />
      </el-select>

      <el-button type="primary" class="add-student-btn" @click="openAddStudentDialog">
        <LibraryIcon name="add" /> 添加学生
      </el-button>
    </div>

    <div class="table-card">
      <el-table :data="paginatedData" style="width: 100%" v-loading="loading" stripe>
        <el-table-column prop="student_id" label="学号" width="120" />
        <el-table-column label="姓名" width="150">
          <template #default="scope">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="text-avatar" :style="{ backgroundColor: getAvatarColor(scope.row.name) }">
                {{ getSurname(scope.row.name) }}
              </div>
              <span>{{ scope.row.name }}</span>
              <span
                v-if="scope.row.has_pending_crisis"
                class="crisis-mark"
                :title="`存在 ${scope.row.pending_crisis_count} 条未处理危机预警`"
              >
                <LibraryIcon name="alert" />
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="class_name" label="班级" width="120" />
        <el-table-column prop="advisor" label="辅导员" width="120" />
        <el-table-column label="风险等级" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.risk_level === 'red'" type="danger" effect="dark">高风险</el-tag>
            <el-tag v-else-if="scope.row.risk_level === 'yellow'" type="warning" effect="dark">中风险</el-tag>
            <el-tag v-else-if="scope.row.risk_level === 'green'" type="success" effect="dark">低风险</el-tag>
            <el-tag v-else type="info" effect="dark">未测评</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近测评时间" width="200">
          <template #default="scope">
            {{ formatDate(scope.row.latest_test_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="latest_test_score" label="最近得分" width="100" />
        <el-table-column label="操作" align="right">
          <template #default="scope">
            <el-button type="warning" size="small" plain @click="openIntervention(scope.row)">添加干预</el-button>
            <el-button type="primary" size="small" @click="$router.push(`/teacher/student/${scope.row.id}`)">查看详情</el-button>
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

    <el-dialog
      v-model="addDialogVisible"
      title="添加学生"
      width="620px"
      :close-on-click-modal="false"
      @closed="resetStudentForm"
    >
      <el-form ref="addStudentFormRef" :model="addStudentForm" :rules="addStudentRules" label-width="110px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="addStudentForm.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="学号/工号" prop="student_id">
          <el-input v-model="addStudentForm.student_id" placeholder="请输入学号/工号" />
        </el-form-item>
        <el-form-item label="初始密码" prop="initial_password">
          <el-input v-model="addStudentForm.initial_password" type="password" show-password autocomplete="new-password" placeholder="至少8个字符，包含字母和数字" aria-label="初始密码" />
        </el-form-item>
        <el-form-item label="班级/年级" prop="class_name">
          <el-input v-model="addStudentForm.class_name" placeholder="请输入班级或年级" />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-radio-group v-model="addStudentForm.gender">
            <el-radio label="男">男</el-radio>
            <el-radio label="女">女</el-radio>
            <el-radio label="其他">其他</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="家长联系方式" prop="parent_phone">
          <el-input v-model="addStudentForm.parent_phone" placeholder="选填：家长手机号" />
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="addStudentForm.remarks" type="textarea" :rows="3" placeholder="选填：备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="addDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitAddStudent">提交</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { passwordPolicyError } from '../../utils/passwordPolicy'
import { businessColor } from '../../styles/business-theme.js'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElInput, ElIcon, ElSelect, ElOption, ElButton, ElTable, ElTableColumn, ElTag, ElPagination, ElDialog, ElForm, ElFormItem, ElRadioGroup, ElRadio, vLoading } from 'element-plus'

const loading = ref(false)
const students = ref([])
const searchQuery = ref('')
const filterRisk = ref('')
const filterClass = ref('')

const currentPage = ref(1)
const pageSize = ref(10)
const addDialogVisible = ref(false)
const submitting = ref(false)
const addStudentFormRef = ref(null)
const addStudentForm = ref({
  name: '',
  student_id: '',
  initial_password: '',
  class_name: '',
  gender: '',
  parent_phone: '',
  remarks: ''
})
const addStudentRules = {
  name: [{ required: true, message: '姓名不能为空', trigger: 'blur' }],
  student_id: [{ required: true, message: '学号不能为空', trigger: 'blur' }],
  initial_password: [{ validator: (_rule, value, callback) => { const error = passwordPolicyError(value); callback(error ? new Error(error) : undefined) }, trigger: 'blur' }]
}
let pollTimer = null

const fetchStudents = async () => {
  loading.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/teacher/students', {
      headers: { Authorization: `Bearer ${token}` }
    })
    students.value = res.data
  } catch (error) {
    console.error('Failed to fetch students', error)
  } finally {
    loading.value = false
  }
}

const uniqueAdvisors = computed(() => {
  const advisors = students.value.map(s => s.advisor).filter(Boolean)
  return [...new Set(advisors)]
})

const filteredData = computed(() => {
  return students.value.filter(s => {
    const matchSearch = (s.name && s.name.includes(searchQuery.value)) || 
                        (s.student_id && s.student_id.includes(searchQuery.value))
    const matchRisk = filterRisk.value ? s.risk_level === filterRisk.value : true
    const matchClass = filterClass.value ? s.advisor === filterClass.value : true
    
    return matchSearch && matchRisk && matchClass
  })
})

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

const formatDate = (dateString) => {
  if (!dateString) return '无'
  const d = new Date(dateString)
  return d.toLocaleString()
}

const getAvatarColor = (name) => {
  const colors = [businessColor('brand-100'), businessColor('accent-sage-soft'), businessColor('warning-100'), businessColor('warning-100'), businessColor('brand-100'), businessColor('accent-sage-soft')];
  const charCode = name ? name.charCodeAt(0) : 0;
  return colors[charCode % colors.length];
}

const getSurname = (name) => {
  return name ? name.charAt(0) : '未';
}

const openIntervention = (row) => {
  if (!row?.id) {
    ElMessage.warning('请先完成风险评估')
    return
  }
  const level = row.risk_level === 'red' ? '紧急干预' : (row.risk_level === 'yellow' ? '重点关注' : '持续观察')
  window.dispatchEvent(new CustomEvent('open-intervention-dialog', {
    detail: {
      student_id: row.id,
      risk_type: row.risk_level === 'red' ? '高风险预警' : (row.risk_level === 'yellow' ? '中风险预警' : '低风险观察'),
      intervention_level: level
    }
  }))
}

const openAddStudentDialog = () => {
  const role = localStorage.getItem('role')
  if (role !== 'teacher') {
    ElMessage.error('仅教师/管理员可添加学生')
    return
  }
  addDialogVisible.value = true
}

const resetStudentForm = () => {
  addStudentFormRef.value?.clearValidate?.()
  addStudentForm.value = {
    name: '',
    student_id: '',
  initial_password: '',
    class_name: '',
    gender: '',
    parent_phone: '',
    remarks: ''
  }
}

const submitAddStudent = async () => {
  if (submitting.value) return
  const valid = await addStudentFormRef.value?.validate().catch(() => false)
  if (!valid) { addStudentForm.value.initial_password = ''; return }
  submitting.value = true
  try {
    const token = localStorage.getItem('token')
    await axios.post('/api/teacher/students', addStudentForm.value, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('学生添加成功')
    addDialogVisible.value = false
    await fetchStudents()
  } catch (error) {
    const detail = error?.response?.data?.detail || ''
    if (detail.includes('学号已存在')) {
      ElMessage.error('学号已存在')
    } else if (detail.includes('姓名不能为空')) {
      ElMessage.error('姓名不能为空')
    } else if (detail.includes('学号不能为空')) {
      ElMessage.error('学号不能为空')
    } else if (error?.response?.status === 403) {
      ElMessage.error('仅教师/管理员可添加学生')
    } else {
      ElMessage.error('添加学生失败')
    }
  } finally {
    addStudentForm.value.initial_password = ''
    submitting.value = false
  }
}

onMounted(() => {
  fetchStudents()
  pollTimer = setInterval(fetchStudents, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
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
  align-items: center;
}

.search-input {
  width: 300px;
}

.filter-select {
  width: 150px;
}

.add-student-btn {
  margin-left: auto;
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

.text-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.crisis-mark {
  color: var(--danger-text);
  font-size: 16px;
  font-weight: bold;
  line-height: 1;
}
</style>
