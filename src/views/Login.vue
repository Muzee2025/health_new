<template>
  <AuthShell>
    <h2>欢迎回来</h2>
    <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
      <el-form-item label="用户名"><el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" aria-label="用户名" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="form.password" type="password" placeholder="请输入密码" autocomplete="current-password" aria-label="密码" show-password /></el-form-item>
      <el-button type="primary" native-type="submit" class="auth-submit" :loading="submitting" :disabled="submitting">登录</el-button>
      <div class="auth-links"><router-link to="/register">没有账号？去注册</router-link></div>
    </el-form>
  </AuthShell>
</template>
<script setup>
import { ref } from 'vue'
import AuthShell from '../components/AuthShell.vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()
const submitting = ref(false)
const form = ref({
  username: '',
  password: ''
})

const handleLogin = async () => {
  if (submitting.value) return
  if (!form.value.username.trim() || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  submitting.value = true
  try {
    const res = await axios.post('/api/login', form.value)
    const { access_token, user } = res.data
    localStorage.setItem('token', access_token)
    localStorage.setItem('role', user.role)
    localStorage.setItem('user', JSON.stringify(user))

    ElMessage.success('登录成功')

    if (user.role === 'teacher') {
      router.push('/teacher')
    } else {
      router.push('/student')
    }
  } catch (error) {
    ElMessage.error(error.message || '登录失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>
