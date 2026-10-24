<template>
  <section class="questions-page business-page" aria-labelledby="questions-title">
    <header class="page-intro">
      <div>
        <h2 id="questions-title">向老师留言</h2>
        <p>这里的留言由负责老师查看。页面会显示当前分配状态；回复时间以老师实际安排为准。</p>
      </div>
      <el-button plain @click="fetchQuestions" :loading="loadingQuestions">刷新记录</el-button>
    </header>

    <el-alert v-if="schemaDisabled" role="status" type="info" :closable="false" title="求助服务尚未启用，请联系管理员。" />
    <el-alert v-else-if="loadError" role="alert" type="error" :closable="false" title="提问记录暂时无法加载，请检查网络后重试。" />

    <section v-else class="question-compose" aria-label="提交问题">
      <label for="student-question-text" class="question-label">想留言咨询什么？</label>
      <el-input
        id="student-question-text"
        v-model="form.question_text"
        type="textarea"
        :rows="4"
        maxlength="2000"
        show-word-limit
        placeholder="写下想和老师讨论的事情"
        :disabled="submitting || schemaDisabled"
        aria-describedby="question-service-note"
      />
      <div class="compose-footer">
        <p id="question-service-note">留言只会提供给按学校明确分配关系负责你的老师。这里不提供紧急响应，也不承诺回复时效。</p>
        <el-button type="primary" :loading="submitting" :disabled="submitting || !form.question_text.trim()" @click="submitQuestion">
          {{ submitting ? '正在提交' : '提交留言' }}
        </el-button>
      </div>
      <el-alert v-if="submitError" type="error" :closable="false" :title="submitError" show-icon />
    </section>

    <section class="question-history" aria-labelledby="history-title">
      <div class="section-heading">
        <div>
          <h3 id="history-title">我的留言</h3>
          <p>仅显示本人提交的问题和老师公开给你的回复。</p>
        </div>
      </div>
      <div v-if="loadingQuestions && !questions.length" class="history-loading" role="status" aria-live="polite">正在加载留言…</div>
      <LibraryEmpty v-else-if="!questions.length && !loadError && !schemaDisabled" description="还没有留言。你可以在上方写下想咨询老师的问题。" :image-size="100">
        <el-button type="primary" plain @click="focusComposer">写一条留言</el-button>
      </LibraryEmpty>
      <ol v-else class="question-list" aria-live="polite">
        <li v-for="question in questions" :key="question.id" class="question-entry">
          <div class="entry-meta">
            <time :datetime="question.created_at">{{ formatDate(question.created_at) }}</time>
            <el-tag :type="statusType(question)">{{ statusLabel(question) }}</el-tag>
          </div>
          <div class="message-block">
            <strong>我的问题</strong>
            <p>{{ question.question_text }}</p>
          </div>
          <p v-if="question.response_state === 'unassigned'" class="assignment-note">
            当前尚未分配可查看此留言的老师。问题已保存，学校完成分配后才会进入老师的收件箱。
          </p>
          <div v-if="question.answer_text" class="answer-block">
            <strong>老师的回复</strong>
            <p>{{ question.answer_text }}</p>
          </div>
          <div v-else-if="question.response_state !== 'unassigned'" class="pending-note">老师尚未回复；这里不会承诺具体回复时间。</div>
        </li>
      </ol>
    </section>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import axios from 'axios'
import { ElAlert, ElButton, ElInput, ElTag } from 'element-plus'
import LibraryEmpty from '../../design/LibraryEmpty.vue'

const form = ref({ question_text: '' })
const questions = ref([])
const loadingQuestions = ref(false)
const submitting = ref(false)
const loadError = ref(false)
const submitError = ref('')
const schemaDisabled = ref(false)
let active = true
let requestController = null
let submitController = null

const isSchemaDisabled = (error) => error?.response?.status === 503
  && error?.response?.data?.detail === 'Support workflow schema is not enabled'
const friendlyError = (error, fallback) => {
  if (isSchemaDisabled(error)) return '求助服务尚未启用，请联系管理员。'
  if (error?.response?.status === 422) return '内容未通过检查，请修改后重试。'
  if (error?.response?.status === 401) return '登录状态已失效，请重新登录。'
  return fallback
}

const fetchQuestions = async () => {
  requestController?.abort()
  requestController = new AbortController()
  const controller = requestController
  loadingQuestions.value = true
  loadError.value = false
  try {
    const response = await axios.get('/api/student/questions', { signal: controller.signal })
    if (!active || controller.signal.aborted) return
    const payload = response.data?.data ?? response.data
    questions.value = Array.isArray(payload) ? payload : []
    schemaDisabled.value = false
  } catch (error) {
    if (!active || axios.isCancel(error) || error?.code === 'ERR_CANCELED') return
    if (isSchemaDisabled(error)) schemaDisabled.value = true
    else loadError.value = true
  } finally {
    if (active && !controller.signal.aborted) loadingQuestions.value = false
  }
}

const submitQuestion = async () => {
  if (submitting.value) return
  const text = form.value.question_text.trim()
  if (!text) {
    submitError.value = '请先写下想咨询的问题。'
    return
  }
  submitting.value = true
  submitError.value = ''
  submitController = new AbortController()
  try {
    await axios.post('/api/student/questions', { question_text: text }, { signal: submitController.signal })
    if (!active) return
    form.value.question_text = ''
    await fetchQuestions()
  } catch (error) {
    if (!active || axios.isCancel(error) || error?.code === 'ERR_CANCELED') return
    if (isSchemaDisabled(error)) schemaDisabled.value = true
    submitError.value = friendlyError(error, '留言提交失败，请保留内容并稍后重试。')
  } finally {
    if (active) submitting.value = false
  }
}

const statusLabel = (question) => {
  if (question.response_state === 'unassigned') return '尚未分配老师'
  if (question.response_state === 'answered' || question.status === 'answered') return '已回复'
  return '等待老师查看'
}
const statusType = (question) => question.response_state === 'unassigned' ? 'warning'
  : (question.response_state === 'answered' || question.status === 'answered' ? 'success' : 'info')
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN') : '时间未知'
const focusComposer = () => document.querySelector('.question-compose textarea')?.focus()

onMounted(fetchQuestions)
onUnmounted(() => {
  active = false
  requestController?.abort()
  submitController?.abort()
})
</script>

<style scoped>
.questions-page { display: grid; gap: 24px; max-width: 920px; margin: 0 auto; }
.page-intro, .section-heading, .compose-footer, .entry-meta { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.page-intro h2, .section-heading h3 { margin: 0; color: var(--text-primary); }
.page-intro p, .section-heading p, .compose-footer p { color: var(--text-secondary); margin: 6px 0 0; line-height: 1.6; }
.question-compose, .question-history { padding: 24px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
.question-label { display: block; margin-bottom: 8px; color: var(--text-primary); font-weight: 600; }
.compose-footer { align-items: center; margin-top: 14px; }
.compose-footer p { max-width: 600px; font-size: 13px; }
.question-history { min-height: 240px; }
.question-list { list-style: none; padding: 0; margin: 18px 0 0; }
.question-entry { padding: 18px 0; border-top: 1px solid var(--border); }
.entry-meta { align-items: center; color: var(--text-secondary); font-size: 13px; }
.message-block, .answer-block { margin-top: 16px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.message-block p, .answer-block p { margin: 6px 0 0; }
.message-block strong { color: var(--text-primary); }
.answer-block { padding: 14px 16px; border-radius: var(--radius-md); background: var(--surface-warm); color: var(--text-primary); }
.answer-block strong { color: var(--brand-700); }
.assignment-note, .pending-note { margin: 14px 0 0; padding: 12px 14px; border-radius: var(--radius-md); background: var(--warning-100); color: var(--warning-text); line-height: 1.6; }
.pending-note { background: var(--surface-subtle); color: var(--text-secondary); }
.history-loading { padding: 28px; text-align: center; color: var(--text-secondary); }
@media (max-width: 600px) {
  .page-intro { align-items: stretch; flex-direction: column; }
  .page-intro > :deep(.el-button) { align-self: flex-start; }
  .question-compose, .question-history { padding: 18px; }
  .compose-footer { align-items: stretch; flex-direction: column; }
  .compose-footer > :deep(.el-button) { align-self: flex-start; }
}
</style>
