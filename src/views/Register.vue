<template>
  <div class="login-container">
    <el-card class="login-box">
      <h2>心域智链 - 注册</h2>
      <el-form :model="form" @submit.prevent="handleRegister">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-form-item>
          <el-select v-model="form.role" placeholder="选择角色" class="w-full">
            <el-option label="学生" value="student" />
            <el-option label="教师" value="teacher" />
          </el-select>
        </el-form-item>
        <template v-if="form.role === 'student'">
          <el-form-item>
            <el-input v-model="form.name" placeholder="姓名" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.student_id" placeholder="学号" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.advisor" placeholder="辅导员姓名" />
          </el-form-item>
        </template>
        <template v-if="form.role === 'teacher'">
          <el-form-item>
            <el-input v-model="form.name" placeholder="姓名" />
          </el-form-item>
        </template>
        <el-form-item>
          <el-button type="primary" native-type="submit" class="w-full">注册</el-button>
        </el-form-item>
        <div class="text-right">
          <el-link type="primary" @click="$router.push('/login')">已有账号？去登录</el-link>
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

const router = useRouter()
const form = ref({
  username: '',
  password: '',
  role: 'student',
  name: '',
  student_id: '',
  advisor: ''
})

const handleRegister = async () => {
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
    ElMessage.error(error.response?.data?.detail || '注册失败')
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
