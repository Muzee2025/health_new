<template>
  <AuthShell>
    <h1>创建学生账号</h1>
    <p class="auth-intro">学生可自主注册，教师账号由学校开通。</p>
    <el-form
      :model="form"
      label-position="top"
      :aria-busy="submitting"
      @submit.prevent="handleRegister"
    >
      <el-form-item label="用户名"
        ><el-input
          v-model="form.username"
          placeholder="请输入用户名"
          autocomplete="username"
          aria-label="用户名"
      /></el-form-item>
      <el-form-item label="密码"
        ><el-input
          v-model="form.password"
          type="password"
          placeholder="至少8个字符，包含字母和数字"
          autocomplete="new-password"
          aria-label="密码"
          show-password
      /></el-form-item>
      <fieldset class="auth-optional">
        <legend>个人资料（选填）</legend>
        <el-form-item label="姓名（选填）"
          ><el-input
            v-model="form.name"
            placeholder="请输入姓名"
            autocomplete="name"
            aria-label="姓名"
        /></el-form-item>
        <template v-if="form.role === 'student'">
          <el-form-item label="学号（选填）"
            ><el-input v-model="form.student_id" placeholder="请输入学号" aria-label="学号"
          /></el-form-item>
          <el-form-item label="辅导员姓名（选填）"
            ><el-input
              v-model="form.advisor"
              placeholder="请输入辅导员姓名"
              aria-label="辅导员姓名"
          /></el-form-item>
        </template>
      </fieldset>
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
        >注册</el-button
      >
      <div class="auth-links"><router-link to="/login">已有账号？去登录</router-link></div>
    </el-form>
  </AuthShell>
</template>
<script setup>
import { onBeforeUnmount, ref } from 'vue'
import AuthShell from '../components/AuthShell.vue'
import { passwordPolicyError } from '../utils/passwordPolicy'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElForm, ElFormItem, ElInput, ElAlert, ElButton } from 'element-plus'

const router = useRouter()
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
  role: 'student',
  name: '',
  student_id: '',
  advisor: '',
})

const handleRegister = async () => {
  if (submitting.value) return
  errorMessage.value = ''
  form.value.username = form.value.username.trim()
  if (!form.value.username.trim() || !form.value.password) {
    errorMessage.value = '请填写用户名和密码'
    return
  }
  if (Array.from(form.value.username).length > 50) {
    errorMessage.value = '用户名最多50个字符'
    return
  }
  const passwordError = passwordPolicyError(form.value.password)
  if (passwordError) {
    errorMessage.value = passwordError
    return
  }
  submitting.value = true
  requestController = new AbortController()
  try {
    const res = await axios.post(
      '/api/register',
      { ...form.value, role: 'student' },
      { signal: requestController.signal, timeout: 15000 },
    )
    if (requestController.signal.aborted) return
    const { access_token, user } = res.data || {}
    if (
      typeof access_token !== 'string' ||
      !access_token.trim() ||
      !Number.isInteger(user?.id) ||
      user.id <= 0 ||
      user.role !== 'student'
    ) {
      errorMessage.value = '注册响应不完整，请先尝试登录；若仍失败，请联系管理员'
      return
    }
    localStorage.setItem('token', access_token.trim())
    localStorage.removeItem('access_token')
    localStorage.setItem('role', user.role)
    localStorage.setItem('user', JSON.stringify(user))
    form.value.password = ''

    ElMessage.success('注册成功，已自动登录')
    await router.replace('/student')
  } catch (error) {
    if (requestController.signal.aborted) return
    const status = error.status || error.response?.status
    if (status === 400 || status === 409)
      errorMessage.value = '暂无法注册此账号，请检查用户名或尝试登录'
    else if (status === 429) errorMessage.value = '尝试过于频繁，请稍后再注册'
    else if (status === 422) errorMessage.value = '请检查用户名和密码格式后重试'
    else if (status === 404 || status >= 500)
      errorMessage.value = '注册服务暂不可用，请稍后重试；若此前已提交，请先尝试登录'
    else if (!error.response)
      errorMessage.value = '暂时无法连接注册服务，请检查网络；若此前已提交，请先尝试登录'
    else errorMessage.value = '注册失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
