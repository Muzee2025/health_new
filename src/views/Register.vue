<template>
  <AuthShell>
    <h2>创建学生账号</h2>
    <el-form :model="form" label-position="top" @submit.prevent="handleRegister">
      <el-form-item label="用户名"><el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" aria-label="用户名" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="form.password" type="password" placeholder="至少8个字符，包含字母和数字" autocomplete="new-password" aria-label="密码" show-password /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="form.name" placeholder="请输入姓名" autocomplete="name" aria-label="姓名" /></el-form-item>
      <template v-if="form.role === 'student'">
        <el-form-item label="学号"><el-input v-model="form.student_id" placeholder="请输入学号" aria-label="学号" /></el-form-item>
        <el-form-item label="辅导员姓名"><el-input v-model="form.advisor" placeholder="请输入辅导员姓名" aria-label="辅导员姓名" /></el-form-item>
      </template>
      <el-button type="primary" native-type="submit" class="auth-submit" :loading="submitting" :disabled="submitting">注册</el-button>
      <div class="auth-links"><router-link to="/login">已有账号？去登录</router-link></div>
    </el-form>
  </AuthShell>
</template>
<script setup>
import { ref } from 'vue'
import AuthShell from '../components/AuthShell.vue'
import { passwordPolicyError } from '../utils/passwordPolicy'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()
const submitting = ref(false)
const form = ref({
  username: '',
  password: '',
  role: 'student',
  name: '',
  student_id: '',
  advisor: ''
})

const handleRegister = async () => {
  if (submitting.value) return
  if (!form.value.username.trim() || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  const passwordError = passwordPolicyError(form.value.password)
  if (passwordError) { ElMessage.warning(passwordError); return }
  submitting.value = true
  try {
    const res = await axios.post('/api/register', form.value)
    const { access_token, user } = res.data
    localStorage.setItem('token', access_token)
    localStorage.setItem('role', user.role)
    localStorage.setItem('user', JSON.stringify(user))

    ElMessage.success('注册成功')

    if (user.role === 'teacher') {
      router.push('/teacher')
    } else {
      router.push('/student')
    }
  } catch (error) {
    ElMessage.error(error.message || '注册失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>
