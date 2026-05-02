<template>
  <div class="login-container">
    <el-card class="login-box">
      <h2>心域智链 - 登录</h2>
      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" class="w-full">登录</el-button>
        </el-form-item>
        <div class="text-right">
          <el-link type="primary" @click="$router.push('/register')">没有账号？去注册</el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const form = ref({
  username: '',
  password: ''
})

const handleLogin = async () => {
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
    ElMessage.error(error.response?.data?.detail || '登录失败')
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f3f4f6;
}
.login-box {
  width: 400px;
  text-align: center;
}
.w-full {
  width: 100%;
}
.text-right {
  text-align: right;
  margin-top: 10px;
}
</style>
