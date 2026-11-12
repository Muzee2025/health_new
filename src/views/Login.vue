<template>
  <AuthShell>
    <h1>欢迎回来</h1>
    <p class="auth-intro">使用账号、姓名或学号登录。</p>
    <el-form
      :model="form"
      label-position="top"
      :aria-busy="submitting"
      @submit.prevent="handleLogin"
    >
      <el-form-item label="账号"
        ><el-input
          v-model="form.username"
          placeholder="用户名、姓名或学号"
          autocomplete="username"
          aria-label="账号"
      /></el-form-item>
      <el-form-item label="密码"
        ><el-input
          v-model="form.password"
          type="password"
          placeholder="请输入密码"
          autocomplete="current-password"
          aria-label="密码"
          show-password
      /></el-form-item>
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
        role="alert"
      />
      <el-button
        type="primary"
        native-type="submit"
        class="auth-submit"
        :loading="submitting"
        :disabled="submitting"
        >登录</el-button
      >
      <div class="auth-links"><router-link to="/register">没有账号？去注册</router-link></div>
    </el-form>
  </AuthShell>
</template>
<script setup>
import { onBeforeUnmount, ref } from 'vue'
import AuthShell from '../components/AuthShell.vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElForm, ElFormItem, ElInput, ElAlert, ElButton } from 'element-plus'

const router = useRouter()
const route = useRoute()
const submitting = ref(false)
const errorMessage = ref('')
let requestController
onBeforeUnmount(() => requestController?.abort())
onBeforeRouteLeave(() => {
  requestController?.abort()
})
const form = ref({
  username: '',
  password: '',
})

const handleLogin = async () => {
  if (submitting.value) return
  errorMessage.value = ''
  form.value.username = form.value.username.trim()
  if (!form.value.username.trim() || !form.value.password) {
    errorMessage.value = '请填写账号和密码'
    return
  }
  submitting.value = true
  requestController = new AbortController()
  try {
    const res = await axios.post(
      '/api/login',
      { ...form.value },
      { signal: requestController.signal, timeout: 15000 },
    )
    if (requestController.signal.aborted) return
    const { access_token, user } = res.data || {}
    if (
      typeof access_token !== 'string' ||
      !access_token.trim() ||
      !Number.isInteger(user?.id) ||
      user.id <= 0 ||
      !['student', 'teacher'].includes(user.role)
    ) {
      errorMessage.value = '登录响应不完整，请稍后重试'
      return
    }
    localStorage.setItem('token', access_token.trim())
    localStorage.removeItem('access_token')
    localStorage.setItem('role', user.role)
    localStorage.setItem('user', JSON.stringify(user))
    form.value.password = ''

    ElMessage.success('登录成功')

    let destination = user.role === 'teacher' ? '/teacher' : '/student'
    const redirect = route.query.redirect
    if (
      typeof redirect === 'string' &&
      redirect.startsWith('/') &&
      !redirect.startsWith('//') &&
      !redirect.includes('\\') &&
      !/[\u0000-\u0020]/.test(redirect)
    ) {
      const target = router.resolve(redirect)
      if (target.meta.requiresAuth && (!target.meta.role || target.meta.role === user.role))
        destination = target.fullPath
    }
    await router.replace(destination)
  } catch (error) {
    if (requestController.signal.aborted) return
    const status = error.status || error.response?.status
    if (status === 401) errorMessage.value = '账号或密码不正确，请检查后重试'
    else if (status === 429) errorMessage.value = '尝试过于频繁，请稍后再登录'
    else if (status === 422) errorMessage.value = '账号或密码格式不正确，请检查后重试'
    else if (status === 404 || status >= 500) errorMessage.value = '登录服务暂不可用，请稍后重试'
    else if (!error.response) errorMessage.value = '暂时无法连接登录服务，请检查网络后重试'
    else errorMessage.value = '登录失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
