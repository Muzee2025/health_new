<template>
  <div class="questions">
    <el-card>
      <h2>提问心理老师</h2>
      <p class="desc">有问题想要咨询？请在这里留言，老师会尽快回复你。</p>
      
      <el-form :model="form" class="mt-20">
        <el-form-item>
          <el-input
            v-model="form.question_text"
            type="textarea"
            :rows="3"
            placeholder="请输入您的问题..."
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitQuestion" :loading="loading">提交问题</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mt-20">
      <h3>我的提问记录</h3>
      <div v-for="q in questions" :key="q.id" class="q-item">
        <div class="q-header">
          <span class="time">{{ new Date(q.created_at).toLocaleString() }}</span>
          <el-tag :type="q.status === 'answered' ? 'success' : 'info'">
            {{ q.status === 'answered' ? '已回复' : '待回复' }}
          </el-tag>
        </div>
        <p class="q-text"><strong>Q:</strong> {{ q.question_text }}</p>
        <div v-if="q.answer_text" class="a-text">
          <strong>A:</strong> {{ q.answer_text }}
        </div>
        <el-divider />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const form = ref({
  question_text: ''
})

const loading = ref(false)
const questions = ref([])

onMounted(() => {
  fetchQuestions()
})

const fetchQuestions = async () => {
  try {
    const res = await axios.get('/api/student/questions')
    questions.value = res.data
  } catch (error) {
    ElMessage.error('获取提问记录失败')
  }
}

const submitQuestion = async () => {
  if (!form.value.question_text.trim()) {
    ElMessage.warning('问题内容不能为空')
    return
  }
  
  loading.value = true
  try {
    await axios.post('/api/student/questions/ask', { question_text: form.value.question_text })
    ElMessage.success('提问成功，请耐心等待老师回复')
    form.value.question_text = ''
    fetchQuestions()
  } catch (error) {
    ElMessage.error('提问失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.desc {
  color: var(--text-secondary);
}
.mt-20 {
  margin-top: 20px;
}
.q-item {
  margin-bottom: 20px;
}
.q-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}
.time {
  color: var(--text-secondary);
  font-size: 14px;
}
.q-text {
  font-size: 16px;
  line-height: 1.5;
}
.a-text {
  background-color: var(--surface-warm);
  padding: 10px;
  border-radius: 4px;
  margin-top: 10px;
  color: var(--success-text);
}
</style>
