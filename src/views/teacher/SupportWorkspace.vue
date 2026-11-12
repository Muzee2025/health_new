<template>
  <section class="support-workspace business-page" aria-label="求助与跟进工作区">
    <header class="workspace-heading">
      <div>
        <p>只显示明确分配给你的学生。学生可见答复与内部跟进备注分别保存。</p>
      </div>
      <el-button plain @click="refreshAll" :loading="refreshing">刷新工作区</el-button>
    </header>
    <nav class="workspace-nav" aria-label="求助与跟进区域">
      <a href="#questions-heading">学生提问</a><a href="#warnings-heading">预警与审核记录</a
      ><a href="#followups-heading">跟进任务</a>
    </nav>

    <el-alert
      v-if="schemaDisabled"
      type="info"
      :closable="false"
      title="求助与跟进服务尚未启用，请联系管理员。刷新对应区域可重新检查服务状态。"
    />
    <section
      id="questions"
      class="workspace-section business-card"
      aria-labelledby="questions-heading"
    >
      <div class="section-title">
        <div>
          <h3 id="questions-heading">学生提问</h3>
          <p>答复会直接显示在学生自己的留言记录中。</p>
        </div>
        <el-button plain @click="loadQuestions" :loading="loadingQuestions">刷新提问</el-button>
      </div>
      <el-tabs v-model="questionStatus" @tab-change="loadQuestions">
        <el-tab-pane label="待答复" name="pending" />
        <el-tab-pane label="已答复" name="answered" />
      </el-tabs>
      <el-alert
        v-if="sectionErrors.questions"
        type="error"
        :closable="false"
        :title="sectionErrors.questions"
      />
      <div v-if="loadingQuestions && !questions.length" class="status-line" role="status">
        正在加载提问…
      </div>
      <LibraryEmpty
        v-else-if="!questions.length && !schemaDisabled && !sectionErrors.questions"
        :description="
          questionStatus === 'pending' ? '当前没有待答复的学生留言。' : '还没有已答复的留言。'
        "
        :image-size="88"
      />
      <ol v-else-if="questions.length" class="record-list">
        <li v-for="question in questions" :key="question.id" class="record-row">
          <div class="record-meta">
            <span>{{ question.student_name || '学生' }}</span><time>{{
              formatDate(question.created_at)
            }}</time>
          </div>
          <div class="record-copy">
            <strong>学生留言</strong>
            <p>{{ question.question_text }}</p>
          </div>
          <div
            v-if="question.status === 'answered' || question.answer_text"
            class="record-copy visible-answer"
          >
            <strong>学生可见答复</strong>
            <p>{{ question.answer_text }}</p>
            <small v-if="question.answered_at"
              >回复时间：{{ formatDate(question.answered_at) }}</small
            >
            <div class="row-actions">
              <el-button
                type="primary"
                plain
                @click="openTaskDialog('question', question.id, question.student_id)"
                >创建内部跟进</el-button
              >
            </div>
          </div>
          <div v-else class="answer-editor">
            <label :for="`answer-${question.id}`">学生可见答复</label>
            <el-input
              :id="`answer-${question.id}`"
              v-model="answerDrafts[question.id]"
              type="textarea"
              :rows="3"
              maxlength="3000"
              show-word-limit
              placeholder="写给学生的答复"
              :disabled="answeringId === question.id"
            />
            <div class="row-actions">
              <el-button
                type="primary"
                :loading="answeringId === question.id"
                :disabled="answeringId !== null || !answerDrafts[question.id]?.trim()"
                @click="submitAnswer(question)"
                >发送答复</el-button
              >
              <el-button
                plain
                :disabled="answeringId !== null"
                @click="openTaskDialog('question', question.id, question.student_id)"
                >创建内部跟进</el-button
              >
            </div>
          </div>
        </li>
      </ol>
    </section>

    <section
      id="warnings"
      class="workspace-section business-card"
      aria-labelledby="warnings-heading"
    >
      <div class="section-title">
        <div>
          <h3 id="warnings-heading">预警与审核记录</h3>
          <p>只列出分配范围内的预警。审核原因来自服务端历史，可从这里创建内部跟进。</p>
        </div>
        <el-button plain @click="loadWarnings" :loading="loadingWarnings">刷新预警</el-button>
      </div>
      <el-alert
        v-if="sectionErrors.warnings"
        type="error"
        :closable="false"
        :title="sectionErrors.warnings"
      />
      <div v-if="loadingWarnings && !warnings.length" class="status-line" role="status">
        正在加载预警记录…
      </div>
      <LibraryEmpty
        v-else-if="!warnings.length && !schemaDisabled && !sectionErrors.warnings"
        description="当前分配范围内没有预警记录。"
        :image-size="88"
      />
      <ol v-else-if="warnings.length" class="record-list">
        <li v-for="warning in warnings" :key="warning.id" class="record-row">
          <div class="record-meta">
            <span>{{ warning.student_name || '学生' }} · {{ formatDate(warning.created_at) }}</span
            ><el-tag :type="warning.status === 'pending' ? 'warning' : 'success'">{{
              warning.status === 'pending' ? '待审核' : '已审核'
            }}</el-tag>
          </div>
          <div class="record-copy">
            <strong>预警记录</strong>
            <p>{{ warning.trigger_msg || '记录未提供描述' }}</p>
          </div>
          <div
            v-if="warning.reviewsState === 'loaded' && warning.reviews?.length"
            class="internal-note"
          >
            <strong>持久审核历史</strong>
            <div
              v-for="(review, index) in warning.reviews"
              :key="`${warning.id}-${index}`"
              class="review-entry"
            >
              <span
                >{{ reviewActionLabel(review.action) }} · {{ formatDate(review.reviewed_at) }}</span
              >
              <p>{{ review.reason }}</p>
            </div>
          </div>
          <div v-else-if="warning.status !== 'pending'" class="review-history-state">
            <p v-if="warning.reviewsState === 'loading'" class="pending-note" role="status">
              正在加载审核历史…
            </p>
            <p v-else-if="warning.reviewsState === 'failed'" class="history-error" role="alert">
              审核历史暂时无法读取；不能据此判断是否存在审核原因。
            </p>
            <p v-else-if="warning.reviewsState === 'loaded'" class="pending-note">
              这是已有审核记录，服务端未提供可追溯的审核原因。
            </p>
            <el-button
              v-if="warning.reviewsState !== 'loading' && warning.reviewsState !== 'loaded'"
              plain
              size="small"
              @click="loadWarningReviews(warning)"
              >{{
                warning.reviewsState === 'failed' ? '重试读取审核历史' : '查看审核历史'
              }}</el-button
            >
          </div>
          <div class="row-actions">
            <el-button
              type="primary"
              @click="openTaskDialog('crisis_warning', warning.id, warning.student_id)"
              >创建内部跟进</el-button
            >
          </div>
        </li>
      </ol>
    </section>

    <section
      id="followups"
      class="workspace-section business-card"
      aria-labelledby="followups-heading"
    >
      <div class="section-title">
        <div>
          <h3 id="followups-heading">跟进任务</h3>
          <p>任务摘要与处理结果仅供教师工作使用，不会显示给学生。</p>
        </div>
        <el-button plain @click="loadFollowUps" :loading="loadingFollowUps">刷新任务</el-button>
      </div>
      <el-tabs v-model="followUpStatus" @tab-change="loadFollowUps">
        <el-tab-pane label="进行中" name="open" />
        <el-tab-pane label="已完成" name="completed" />
        <el-tab-pane label="已取消" name="cancelled" />
      </el-tabs>
      <el-alert
        v-if="sectionErrors.followUps"
        type="error"
        :closable="false"
        :title="sectionErrors.followUps"
      />
      <div v-if="loadingFollowUps && !followUps.length" class="status-line" role="status">
        正在加载跟进任务…
      </div>
      <LibraryEmpty
        v-else-if="!followUps.length && !schemaDisabled && !sectionErrors.followUps"
        description="当前筛选下没有跟进任务。可从学生留言或预警记录创建任务。"
        :image-size="88"
      />
      <ol v-else-if="followUps.length" class="record-list">
        <li v-for="task in followUps" :key="task.id" class="record-row">
          <div class="record-meta">
            <span>学生 #{{ task.student_id }} · {{ sourceLabel(task.source_type) }}</span
            ><el-tag
              :type="
                task.status === 'completed'
                  ? 'success'
                  : task.status === 'cancelled'
                    ? 'info'
                    : 'warning'
              "
              >{{ followUpLabel(task.status) }}</el-tag
            >
          </div>
          <div class="record-copy">
            <strong>内部跟进摘要</strong>
            <p>{{ task.summary }}</p>
            <small>截止：{{ formatDate(task.due_at) }}</small>
          </div>
          <div v-if="task.outcome" class="record-copy internal-note">
            <strong>内部结果</strong>
            <p>{{ task.outcome }}</p>
          </div>
          <div class="row-actions" v-if="task.status === 'open'">
            <el-button type="primary" plain @click="openTaskAction(task, 'complete')"
              >完成并记录结果</el-button
            >
            <el-button type="danger" plain @click="openTaskAction(task, 'cancel')"
              >取消任务</el-button
            >
          </div>
        </li>
      </ol>
    </section>

    <el-dialog
      v-model="taskDialogVisible"
      title="创建内部跟进任务"
      width="560px"
      :close-on-click-modal="false"
      @closed="resetTaskForm"
    >
      <p class="dialog-note">此任务只供教师内部使用，不会作为学生可见答复。</p>
      <el-form label-position="top">
        <el-form-item label="跟进摘要" required>
          <el-input
            v-model="taskForm.summary"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            placeholder="记录需要完成的后续事项"
          />
        </el-form-item>
        <el-form-item label="计划完成时间" required>
          <el-input v-model="taskForm.dueAt" type="datetime-local" />
        </el-form-item>
      </el-form>
      <p v-if="dialogError" class="inline-error" role="alert">{{ dialogError }}</p>
      <template #footer
        ><el-button @click="taskDialogVisible = false">返回</el-button
        ><el-button type="primary" :loading="savingTask" :disabled="savingTask" @click="createTask"
          >创建任务</el-button
        ></template
      >
    </el-dialog>

    <el-dialog
      v-model="taskActionVisible"
      :title="taskAction === 'complete' ? '完成跟进并记录结果' : '取消跟进任务'"
      width="520px"
      :close-on-click-modal="false"
      @closed="resetTaskAction"
    >
      <p class="dialog-note">
        {{
          taskAction === 'complete'
            ? '处理结果仅供教师内部查看。'
            : '请记录取消原因，作为内部备注保存。'
        }}
      </p>
      <el-input
        v-model="taskActionText"
        type="textarea"
        :rows="4"
        :maxlength="1500"
        show-word-limit
        :placeholder="taskAction === 'complete' ? '填写实际跟进结果' : '填写取消原因'"
      />
      <p v-if="dialogError" class="inline-error" role="alert">{{ dialogError }}</p>
      <template #footer
        ><el-button @click="taskActionVisible = false">返回</el-button
        ><el-button
          :type="taskAction === 'complete' ? 'primary' : 'danger'"
          :loading="savingTask"
          :disabled="savingTask"
          @click="submitTaskAction"
          >确认</el-button
        ></template
      >
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import axios from 'axios'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElTag,
  ElTabs,
  ElTabPane,
  ElMessage,
} from 'element-plus'
import LibraryEmpty from '../../design/LibraryEmpty.vue'

const questionStatus = ref('pending')
const followUpStatus = ref('open')
const questions = ref([])
const followUps = ref([])
const warnings = ref([])
const reviewSchemaStates = reactive({})
const answerDrafts = reactive({})
const loadingQuestions = ref(false)
const loadingFollowUps = ref(false)
const loadingWarnings = ref(false)
const answeringId = ref(null)
const savingTask = ref(false)
const refreshing = ref(false)
const sectionSchemaState = reactive({
  questions: 'unknown',
  followUps: 'unknown',
  warnings: 'unknown',
})
const schemaDisabled = computed(
  () =>
    Object.values(sectionSchemaState).some((state) => state === 'disabled') ||
    Object.values(reviewSchemaStates).some((state) => state === 'disabled'),
)
const sectionErrors = reactive({ questions: '', followUps: '', warnings: '' })
const dialogError = ref('')
const taskDialogVisible = ref(false)
const taskActionVisible = ref(false)
const taskForm = reactive({
  sourceType: '',
  sourceId: null,
  studentId: null,
  summary: '',
  dueAt: '',
})
const taskAction = ref('complete')
const taskActionText = ref('')
const activeTaskId = ref(null)
let active = true
let questionRequestVersion = 0
let followUpRequestVersion = 0
let warningRequestVersion = 0
const controllers = new Set()

const request = async (config) => {
  const controller = new AbortController()
  controllers.add(controller)
  try {
    return await axios({ ...config, signal: controller.signal })
  } finally {
    controllers.delete(controller)
  }
}
const isSchemaDisabled = (error) =>
  error?.response?.status === 503 &&
  error?.response?.data?.detail === 'Support workflow schema is not enabled'
const handleLoadError = (section, error, fallback) => {
  if (!active || axios.isCancel(error) || error?.code === 'ERR_CANCELED') return
  if (isSchemaDisabled(error)) return
  if (error?.response?.status === 401) sectionErrors[section] = '登录状态已失效，请重新登录。'
  else if (error?.response?.status === 403) sectionErrors[section] = '当前账号无权查看这些记录。'
  else sectionErrors[section] = fallback
}
const setSectionState = (section, error = null) => {
  if (!error) sectionSchemaState[section] = 'ready'
  else if (isSchemaDisabled(error)) sectionSchemaState[section] = 'disabled'
  else sectionSchemaState[section] = 'error'
}
const payloadRows = (response) => {
  const rows = response.data?.data ?? response.data
  return Array.isArray(rows) ? rows : []
}
const loadQuestions = async () => {
  const version = ++questionRequestVersion
  loadingQuestions.value = true
  sectionSchemaState.questions = 'loading'
  sectionErrors.questions = ''
  try {
    const response = await request({
      method: 'get',
      url: '/api/teacher/questions',
      params: { status: questionStatus.value },
    })
    if (active && version === questionRequestVersion) {
      questions.value = payloadRows(response)
      setSectionState('questions')
    }
  } catch (error) {
    if (active && version === questionRequestVersion) {
      setSectionState('questions', error)
      handleLoadError('questions', error, '学生留言暂时无法加载，请稍后刷新。')
    }
  } finally {
    if (active && version === questionRequestVersion) loadingQuestions.value = false
  }
}
const loadFollowUps = async () => {
  const version = ++followUpRequestVersion
  loadingFollowUps.value = true
  sectionSchemaState.followUps = 'loading'
  sectionErrors.followUps = ''
  try {
    const response = await request({
      method: 'get',
      url: '/api/teacher/follow-ups',
      params: { status: followUpStatus.value },
    })
    if (active && version === followUpRequestVersion) {
      followUps.value = payloadRows(response)
      setSectionState('followUps')
    }
  } catch (error) {
    if (active && version === followUpRequestVersion) {
      setSectionState('followUps', error)
      handleLoadError('followUps', error, '跟进任务暂时无法加载，请稍后刷新。')
    }
  } finally {
    if (active && version === followUpRequestVersion) loadingFollowUps.value = false
  }
}
const loadWarnings = async () => {
  const version = ++warningRequestVersion
  loadingWarnings.value = true
  sectionSchemaState.warnings = 'loading'
  sectionErrors.warnings = ''
  try {
    const response = await request({ method: 'get', url: '/api/advanced-teacher/warnings' })
    const rows = payloadRows(response)
    if (!active || version !== warningRequestVersion) return
    const visibleIds = new Set(
      rows.filter((row) => row.status !== 'pending').map((row) => String(row.id)),
    )
    for (const warningId of Object.keys(reviewSchemaStates))
      if (!visibleIds.has(String(warningId))) delete reviewSchemaStates[warningId]
    warnings.value = rows.map((row) => ({
      ...row,
      reviews: [],
      reviewsState: row.status === 'pending' ? 'not_applicable' : 'not_loaded',
    }))
    setSectionState('warnings')
  } catch (error) {
    if (active && version === warningRequestVersion) {
      setSectionState('warnings', error)
      handleLoadError('warnings', error, '预警记录暂时无法加载，请稍后刷新。')
    }
  } finally {
    if (active && version === warningRequestVersion) loadingWarnings.value = false
  }
}
const loadWarningReviews = async (warning) => {
  warning.reviewsState = 'loading'
  reviewSchemaStates[warning.id] = 'loading'
  try {
    const result = await request({
      method: 'get',
      url: `/api/teacher/crisis/${encodeURIComponent(warning.id)}/reviews`,
    })
    if (!active) return
    warning.reviews = payloadRows(result)
    warning.reviewsState = 'loaded'
    reviewSchemaStates[warning.id] = 'ready'
    sectionErrors.warnings = ''
  } catch (error) {
    if (!active || axios.isCancel(error) || error?.code === 'ERR_CANCELED') return
    warning.reviewsState = 'failed'
    reviewSchemaStates[warning.id] = isSchemaDisabled(error) ? 'disabled' : 'error'
    handleLoadError('warnings', error, '审核历史暂时无法读取，请稍后重试。')
  }
}
const refreshAll = async () => {
  refreshing.value = true
  await Promise.all([loadQuestions(), loadFollowUps(), loadWarnings()])
  if (active) refreshing.value = false
}
const submitAnswer = async (question) => {
  if (answeringId.value !== null) return
  const answerText = String(answerDrafts[question.id] || '').trim()
  if (!answerText) {
    sectionErrors.questions = '请先填写给学生的答复。'
    return
  }
  answeringId.value = question.id
  sectionErrors.questions = ''
  try {
    await request({
      method: 'post',
      url: `/api/teacher/questions/${question.id}/answer`,
      data: { answer_text: answerText },
    })
    if (!active) return
    ElMessage.success('答复已发送至学生留言记录。')
    delete answerDrafts[question.id]
    questionStatus.value = 'answered'
    await loadQuestions()
  } catch (error) {
    if (error?.response?.status === 409) sectionErrors.questions = '该留言已被处理，请刷新收件箱。'
    else if (error?.response?.status === 404)
      sectionErrors.questions = '该学生或留言已不在你的分配范围内。'
    else if (isSchemaDisabled(error)) sectionSchemaState.questions = 'disabled'
    else if (error?.response?.status === 422)
      sectionErrors.questions = '答复内容未通过检查，请修改后重试。'
    else sectionErrors.questions = '答复暂未发送，请稍后重试。'
  } finally {
    if (active) answeringId.value = null
  }
}
const openTaskDialog = (sourceType, sourceId, studentId) => {
  Object.assign(taskForm, {
    sourceType,
    sourceId: Number(sourceId),
    studentId: Number(studentId),
    summary: '',
    dueAt: '',
  })
  dialogError.value = ''
  taskDialogVisible.value = true
}
const createTask = async () => {
  if (savingTask.value) return
  if (!taskForm.summary.trim() || !taskForm.dueAt || !taskForm.studentId || !taskForm.sourceId) {
    dialogError.value = '请填写摘要和计划完成时间。'
    return
  }
  savingTask.value = true
  dialogError.value = ''
  try {
    await request({
      method: 'post',
      url: '/api/teacher/follow-ups',
      data: {
        source_type: taskForm.sourceType,
        source_id: taskForm.sourceId,
        student_id: taskForm.studentId,
        due_at: new Date(taskForm.dueAt).toISOString(),
        summary: taskForm.summary.trim(),
      },
    })
    if (!active) return
    ElMessage.success('内部跟进任务已创建。')
    taskDialogVisible.value = false
    followUpStatus.value = 'open'
    await loadFollowUps()
  } catch (error) {
    if (error?.response?.status === 404)
      dialogError.value = '该学生或来源记录已不在你的分配范围内。'
    else if (error?.response?.status === 422)
      dialogError.value = '任务信息未通过检查，请核对内容和时间。'
    else if (isSchemaDisabled(error)) {
      sectionSchemaState.followUps = 'disabled'
      dialogError.value = '求助与跟进服务尚未启用，请联系管理员。'
    } else dialogError.value = '任务创建失败，请稍后重试。'
  } finally {
    if (active) savingTask.value = false
  }
}
const openTaskAction = (task, action) => {
  activeTaskId.value = task.id
  taskAction.value = action
  taskActionText.value = ''
  dialogError.value = ''
  taskActionVisible.value = true
}
const submitTaskAction = async () => {
  if (savingTask.value) return
  const text = taskActionText.value.trim()
  if (!text) {
    dialogError.value =
      taskAction.value === 'complete' ? '请填写实际跟进结果。' : '请填写取消原因。'
    return
  }
  savingTask.value = true
  dialogError.value = ''
  const action = taskAction.value
  try {
    await request({
      method: 'post',
      url: `/api/teacher/follow-ups/${activeTaskId.value}/${action === 'complete' ? 'complete' : 'cancel'}`,
      data: action === 'complete' ? { outcome: text } : { reason: text },
    })
    if (!active) return
    ElMessage.success(action === 'complete' ? '跟进结果已保存。' : '取消原因已保存。')
    taskActionVisible.value = false
    await Promise.all([
      loadFollowUps(),
      action === 'complete' ? reloadCompletedFollowUps() : reloadCancelledFollowUps(),
    ])
  } catch (error) {
    if (error?.response?.status === 409) dialogError.value = '任务状态已变化，请刷新后查看。'
    else if (error?.response?.status === 404) dialogError.value = '任务已不在你的分配范围内。'
    else if (error?.response?.status === 422)
      dialogError.value = '记录内容未通过检查，请修改后重试。'
    else if (isSchemaDisabled(error)) {
      sectionSchemaState.followUps = 'disabled'
      dialogError.value = '求助与跟进服务尚未启用，请联系管理员。'
    } else dialogError.value = '保存失败，请稍后重试。'
  } finally {
    if (active) savingTask.value = false
  }
}
const reloadCompletedFollowUps = async () => {
  try {
    const r = await request({
      method: 'get',
      url: '/api/teacher/follow-ups',
      params: { status: 'completed' },
    })
    if (active && followUpStatus.value === 'completed') followUps.value = payloadRows(r)
  } catch (error) {
    handleLoadError('followUps', error, '完成记录已保存，但历史暂时无法加载。')
  }
}
const reloadCancelledFollowUps = async () => {
  try {
    const r = await request({
      method: 'get',
      url: '/api/teacher/follow-ups',
      params: { status: 'cancelled' },
    })
    if (active && followUpStatus.value === 'cancelled') followUps.value = payloadRows(r)
  } catch (error) {
    handleLoadError('followUps', error, '取消记录已保存，但历史暂时无法加载。')
  }
}
const sourceLabel = (value) => (value === 'crisis_warning' ? '预警' : '学生提问')
const reviewActionLabel = (value) =>
  ({ pass: '通过', reject: '驳回校正', escalate: '升级处理' })[value] || '已审核'
const followUpLabel = (value) =>
  ({ open: '进行中', completed: '已完成', cancelled: '已取消' })[value] || '状态未知'
const formatDate = (value) => (value ? new Date(value).toLocaleString('zh-CN') : '时间未记录')
const resetTaskForm = () => {
  Object.assign(taskForm, {
    sourceType: '',
    sourceId: null,
    studentId: null,
    summary: '',
    dueAt: '',
  })
  dialogError.value = ''
}
const resetTaskAction = () => {
  taskActionText.value = ''
  activeTaskId.value = null
  dialogError.value = ''
}

onMounted(refreshAll)
onUnmounted(() => {
  active = false
  controllers.forEach((controller) => controller.abort())
  controllers.clear()
})
</script>

<style scoped>
.support-workspace {
  display: grid;
  gap: 18px;
}
.workspace-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.workspace-nav a {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 7px 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  background: var(--surface);
  text-decoration: none;
}
.workspace-nav a:hover {
  border-color: var(--brand-600);
  color: var(--brand-700);
}
.workspace-nav a:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 2px;
}
.workspace-heading,
.section-title,
.record-meta,
.row-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.workspace-heading h2,
.section-title h3 {
  margin: 0;
  color: var(--text-primary);
}
.workspace-heading p,
.section-title p,
.dialog-note {
  margin: 6px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.workspace-section {
  padding: 24px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.section-title {
  align-items: center;
}
.record-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.record-row {
  padding: 20px 0;
  border-top: 1px solid var(--border);
}
.record-meta {
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
}
.record-copy {
  margin-top: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.record-copy p {
  margin: 5px 0;
  color: var(--text-primary);
}
.record-copy small {
  color: var(--text-secondary);
}
.visible-answer {
  padding: 14px 16px;
  background: var(--surface-warm);
  border-radius: var(--radius-md);
}
.internal-note {
  margin-top: 14px;
  padding: 14px 16px;
  background: var(--surface-subtle);
  border-radius: var(--radius-md);
}
.review-entry {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}
.review-entry p {
  margin: 5px 0 0;
  color: var(--text-primary);
  white-space: pre-wrap;
}
.pending-note {
  padding: 10px 12px;
  color: var(--text-secondary);
  background: var(--surface-subtle);
  border-radius: var(--radius-md);
}
.review-history-state {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}
.review-history-state .pending-note {
  margin: 0;
}
.history-error {
  margin: 0;
  color: var(--danger-text);
}
.answer-editor {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}
.answer-editor label {
  font-weight: 600;
}
.row-actions {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-top: 14px;
}
.status-line {
  padding: 24px 8px;
  color: var(--text-secondary);
  text-align: center;
}
.inline-error {
  color: var(--danger-text);
}
.dialog-note {
  margin: 0 0 16px;
}
@media (max-width: 600px) {
  .workspace-heading,
  .section-title {
    align-items: stretch;
    flex-direction: column;
  }
  .workspace-section {
    padding: 18px;
  }
  .workspace-nav {
    padding: 6px 0;
    overflow-x: auto;
    flex-wrap: nowrap;
  }
  .workspace-nav a {
    flex: 0 0 auto;
  }
  .record-meta {
    align-items: flex-start;
    flex-direction: column;
  }
  .row-actions > :deep(.el-button) {
    margin-left: 0;
  }
}
</style>
