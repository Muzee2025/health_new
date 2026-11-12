<template>
  <main class="test-page business-page">
    <header class="page-heading">
      <div>
        <h1>给自己一点时间</h1>
        <p>这是一段自我观察过程。你可以随时退出；测评结果不能替代专业评估。</p>
      </div>
    </header>

    <section v-if="!currentTest" class="library-section" aria-labelledby="library-title">
      <div class="section-heading">
        <div>
          <h2 id="library-title">选择一份自我观察问卷</h2>
          <p>每份问卷的用途和说明不同，开始前请先了解。</p>
        </div>
      </div>
      <div class="test-list">
        <article v-for="test in tests" :key="test.id" class="test-entry">
          <div class="entry-icon"><LibraryIcon :name="test.icon" /></div>
          <div class="entry-copy">
            <h3>{{ test.title }}</h3>
            <p>{{ testDescription(test) }}</p>
            <span class="question-count">{{ test.questions.length }} 道题</span>
          </div>
          <el-button type="primary" @click="startTest(test)">查看说明</el-button>
        </article>
      </div>
    </section>

    <section v-else-if="!started" class="intro-panel" aria-labelledby="intro-title">
      <button type="button" class="text-button" @click="leaveToList">返回问卷列表</button>
      <div class="intro-copy">
        <div class="entry-icon large"><LibraryIcon :name="currentTest.icon" /></div>
        <h2 id="intro-title">{{ currentTest.title }}</h2>
        <p>{{ testDescription(currentTest) }}</p>
        <ul>
          <li>
            共 {{ currentTest.questions.length }} 道题。{{ answeringInstruction(currentTest) }}
          </li>
          <li>可以返回修改答案；点击提交后，服务器保存本次作答并返回结果。</li>
          <li>页面会在本次浏览器会话中保存草稿；退出登录或更换账号后会清除。</li>
          <li>结果仅用于自我观察，不是诊断或治疗建议。</li>
        </ul>
        <div class="intro-actions">
          <el-button type="primary" size="large" @click="beginAnswering">开始作答</el-button>
          <el-button size="large" @click="leaveToList">暂不作答</el-button>
        </div>
      </div>
    </section>

    <section v-else-if="!testResult" class="question-area" aria-labelledby="question-title">
      <div class="question-topline">
        <button type="button" class="text-button" :disabled="submitting" @click="leaveToList">
          保存并退出
        </button>
        <span>第 {{ currentQIndex + 1 }} / {{ currentTest.questions.length }} 题</span>
      </div>
      <div class="progress-block">
        <div class="progress-label">
          <span>已回答 {{ answeredCount }} 题</span><span>{{ progressPercent }}%</span>
        </div>
        <el-progress :percentage="progressPercent" :show-text="false" :stroke-width="8" />
      </div>
      <article class="question-card">
        <h2 id="question-title" ref="questionHeading" tabindex="-1">
          {{ currentTest.questions[currentQIndex].title }}
        </h2>
        <p class="question-help">请选择最符合你当前感受的一项。可以使用键盘方向键选择。</p>
        <div
          class="option-list"
          role="radiogroup"
          :aria-labelledby="'question-title'"
          @keydown="handleOptionKeys"
        >
          <button
            v-for="(option, index) in currentOptions"
            :key="`${currentQIndex}-${index}`"
            type="button"
            role="radio"
            class="option-item"
            :class="{ selected: isOptionSelected(option) }"
            :aria-checked="isOptionSelected(option)"
            :tabindex="isOptionSelected(option) || (!hasAnswer && index === 0) ? 0 : -1"
            @click="selectOption(option)"
          >
            <span class="option-mark" aria-hidden="true"></span>
            <span>{{ option.label }}</span>
          </button>
        </div>
        <p v-if="submitError" class="submit-error" role="alert">{{ submitError }}</p>
        <div class="question-actions">
          <el-button :disabled="currentQIndex === 0 || submitting" @click="goPrevQuestion"
            >上一题</el-button
          >
          <div class="forward-actions">
            <el-button
              v-if="currentQIndex < currentTest.questions.length - 1"
              type="primary"
              :disabled="!hasAnswer || submitting"
              @click="goNextQuestion"
              >下一题</el-button
            >
            <el-button
              v-else
              type="primary"
              :loading="submitting"
              :disabled="!allAnswered"
              @click="submitAnswers"
              >{{ submitError ? '重试保存' : '提交并查看结果' }}</el-button
            >
          </div>
        </div>
      </article>
    </section>

    <section v-else class="result-area" aria-labelledby="result-title">
      <article class="result-card">
        <div class="result-mark"><LibraryIcon name="report" /></div>
        <p class="result-kicker">本次自我观察</p>
        <h2 id="result-title">{{ testResult.result_level || resultStatusLabel }}</h2>
        <p
          v-if="testResult.assessment_status === 'pending_professional_review'"
          class="status-note"
        >
          本次结果尚待专业复核。页面展示的是问卷计算信息，不代表临床判断。
        </p>
        <dl class="result-facts">
          <div
            v-if="
              testResult.test_type !== 'MBTI' &&
              testResult.score !== null &&
              testResult.score !== undefined
            "
          >
            <dt>原始分</dt>
            <dd>{{ testResult.score }}</dd>
          </div>
          <div v-if="testResult.standard_score !== null && testResult.standard_score !== undefined">
            <dt>换算分</dt>
            <dd>{{ testResult.standard_score }}</dd>
          </div>
          <div v-if="testResult.assessment_status">
            <dt>处理状态</dt>
            <dd>{{ resultStatusLabel }}</dd>
          </div>
          <div v-if="hasRiskField">
            <dt>需关注提示</dt>
            <dd>{{ riskLevelLabel }}</dd>
          </div>
          <div v-if="testResult.scoring?.instrument_id">
            <dt>本次问卷</dt>
            <dd>{{ testResult.scoring.instrument_id }}</dd>
          </div>
        </dl>
        <p v-if="resultDescription" class="result-description">{{ resultDescription }}</p>

        <details class="basis-details">
          <summary>查看结果依据与范围</summary>
          <p v-if="testResult.scoring?.form_version">
            本次题本版本：{{ testResult.scoring.form_version }}
          </p>
          <p>分数与结果由服务器根据已提交答案计算。页面不自行重算或调整选项分值。</p>
          <p v-if="testResult.scoring?.provenance">
            依据说明：{{
              typeof testResult.scoring.provenance === 'string'
                ? testResult.scoring.provenance
                : testResult.scoring.provenance.description ||
                  testResult.scoring.provenance.source ||
                  '服务器计分记录'
            }}
          </p>
          <p>问卷结果只反映本次作答，不能用于诊断、预测或替代与专业人员的交流。</p>
        </details>

        <div class="result-actions">
          <el-button
            type="primary"
            :loading="aiAnalyzing"
            :disabled="aiAnalyzing || !testResult.test_id"
            @click="analyzeResult"
            >{{
              aiAnalyzing ? '正在整理说明…' : aiAnalysis ? '重新获取AI说明' : '查看AI辅助说明'
            }}</el-button
          >
          <el-button @click="finishTest">返回问卷列表</el-button>
        </div>

        <div v-if="aiError" class="ai-error" role="alert">
          <p>{{ aiError }}</p>
          <el-button size="small" :loading="aiAnalyzing" @click="analyzeResult"
            >重试AI说明</el-button
          >
        </div>
        <section v-if="aiAnalysis" class="ai-analysis" aria-labelledby="ai-heading">
          <h3 id="ai-heading">AI辅助说明</h3>
          <p class="ai-status">
            {{ aiStatusLabel
            }}<template v-if="aiAnalysis.model_id"> · {{ aiAnalysis.model_id }}</template>
          </p>
          <section v-if="aiAnalysis.content?.summary">
            <h4>摘要</h4>
            <p>{{ aiAnalysis.content.summary }}</p>
          </section>
          <section v-if="aiAnalysis.content?.observations?.length">
            <h4>观察到的内容</h4>
            <ul>
              <li v-for="(item, index) in aiAnalysis.content.observations" :key="`ob-${index}`">
                {{ item }}
              </li>
            </ul>
          </section>
          <section v-if="aiAnalysis.content?.next_steps?.length">
            <h4>可以考虑</h4>
            <ul>
              <li v-for="(item, index) in aiAnalysis.content.next_steps" :key="`next-${index}`">
                {{ item }}
              </li>
            </ul>
          </section>
          <section v-if="aiAnalysis.content?.limitations?.length">
            <h4>说明与局限</h4>
            <ul>
              <li v-for="(item, index) in aiAnalysis.content.limitations" :key="`limit-${index}`">
                {{ item }}
              </li>
            </ul>
          </section>
          <details class="basis-details">
            <summary>查看本次说明依据</summary>
            <ul v-if="aiAnalysis.sources?.length">
              <li v-for="(item, index) in aiAnalysis.sources" :key="`source-${index}`">
                {{ sourceLabel(item) }}
              </li>
            </ul>
            <p v-else>本次说明没有提供额外来源记录。</p>
            <p class="source-context">计分依据用于核对工具版本，不是外部文献引用。</p>
          </details>
          <p v-if="!hasAiContent" class="ai-empty">服务暂未提供可展示的说明内容。</p>
          <p class="ai-caveat">AI说明用于帮助理解本次问卷结果，不是诊断或个性化治疗建议。</p>
        </section>
      </article>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { ElButton, ElProgress, ElMessage } from 'element-plus'
import { testsData } from '@/data/tests'
import {
  ASSESSMENT_DRAFT_VERSION,
  buildAssessmentSubmission,
  createSubmissionId,
  isValidAssessmentDraft,
  matchesAssessmentResult,
} from '@/services/assessmentFlow'

const tests = testsData
const DRAFT_PREFIX = 'psych_test_draft_v2:'
const LEGACY_PREFIX = 'psych_test_progress_'
const currentTest = ref(null)
const currentQIndex = ref(0)
const answers = ref([])
const questionHeading = ref(null)
const testResult = ref(null)
const started = ref(false)
const submitting = ref(false)
const submitError = ref('')
const aiAnalyzing = ref(false)
const aiError = ref('')
const aiAnalysis = ref(null)
let requestEpoch = 0
let aiController = null
let submissionId = ''
let activeIdentity = readIdentity()

function readIdentity() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    return user?.id == null ? '' : String(user.id)
  } catch {
    return ''
  }
}
function invalidateRequests() {
  requestEpoch += 1
  aiController?.abort()
  aiController = null
  return requestEpoch
}
function draftKey(testId, identity = activeIdentity) {
  return `${DRAFT_PREFIX}${identity}:${testId}`
}
function clearLegacyDrafts() {
  for (let index = localStorage.length - 1; index >= 0; index -= 1) {
    const key = localStorage.key(index)
    if (key?.startsWith(LEGACY_PREFIX)) localStorage.removeItem(key)
  }
}
function clearCurrentDraft() {
  if (currentTest.value && activeIdentity) sessionStorage.removeItem(draftKey(currentTest.value.id))
}
const answeredCount = computed(
  () => answers.value.filter((value) => value !== undefined && value !== null).length,
)
const progressPercent = computed(() =>
  currentTest.value?.questions?.length
    ? Math.round((answeredCount.value / currentTest.value.questions.length) * 100)
    : 0,
)
const currentOptions = computed(() => {
  const question = currentTest.value?.questions?.[currentQIndex.value]
  return question?.options || currentTest.value?.options || []
})
const hasAnswer = computed(
  () =>
    answers.value[currentQIndex.value] !== undefined && answers.value[currentQIndex.value] !== null,
)
const allAnswered = computed(
  () =>
    Boolean(currentTest.value) &&
    answers.value.length === currentTest.value.questions.length &&
    answers.value.every((value) => value !== undefined && value !== null),
)
const resultStatusLabel = computed(() =>
  testResult.value?.assessment_status === 'pending_professional_review'
    ? '待专业复核'
    : testResult.value?.assessment_status === 'entertainment_only'
      ? '仅供娱乐参考'
      : '已收到本次结果',
)
const aiStatusLabel = computed(() => {
  const status =
    aiAnalysis.value?.status === 'fallback'
      ? '本地说明'
      : aiAnalysis.value?.status === 'unavailable'
        ? '服务暂不可用'
        : '辅助说明'
  const source =
    aiAnalysis.value?.source === 'local_rule'
      ? '本地规则'
      : aiAnalysis.value?.source === 'provider'
        ? '模型服务'
        : ''
  return [status, source].filter(Boolean).join(' · ')
})
const resultDescription = computed(() => {
  const value = testResult.value?.result_json
  if (value && typeof value === 'object') return value.desc || ''
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)?.desc || value
    } catch {
      return value
    }
  }
  return ''
})
const hasRiskField = computed(
  () => testResult.value?.risk_level != null && testResult.value.risk_level !== '',
)
const riskLevelLabel = computed(() => {
  const value = testResult.value?.risk_level
  return value == null || value === 'unknown' || value === 'UNKNOWN'
    ? '未提供风险结论'
    : String(value)
})
const hasAiContent = computed(() => {
  const content = aiAnalysis.value?.content || {}
  return Boolean(
    content.summary ||
    content.observations?.length ||
    content.next_steps?.length ||
    content.limitations?.length,
  )
})

function saveDraft() {
  if (!currentTest.value || !activeIdentity || testResult.value) return
  try {
    sessionStorage.setItem(
      draftKey(currentTest.value.id),
      JSON.stringify({
        version: ASSESSMENT_DRAFT_VERSION,
        identity: activeIdentity,
        testId: currentTest.value.id,
        submissionId,
        savedAt: Date.now(),
        currentQIndex: currentQIndex.value,
        answers: answers.value,
      }),
    )
  } catch {
    /* Storage can be disabled; current answers remain in memory. */
  }
}
function restoreDraft(test) {
  if (!activeIdentity) return false
  const key = draftKey(test.id)
  try {
    const parsed = JSON.parse(sessionStorage.getItem(key) || 'null')
    const valid = isValidAssessmentDraft(parsed, {
      identity: activeIdentity,
      test,
      now: Date.now(),
    })
    if (!valid) {
      sessionStorage.removeItem(key)
      return false
    }
    answers.value = parsed.answers.map((answer) => (answer == null ? undefined : answer))
    submissionId = parsed.submissionId
    currentQIndex.value = Math.max(
      0,
      Math.min(Number(parsed.currentQIndex) || 0, test.questions.length - 1),
    )
    return true
  } catch {
    sessionStorage.removeItem(key)
    return false
  }
}
function startTest(test) {
  if (activeIdentity !== readIdentity()) handleIdentityChange()
  currentTest.value = test
  submitting.value = false
  aiAnalyzing.value = false
  testResult.value = null
  aiAnalysis.value = null
  submitError.value = ''
  currentQIndex.value = 0
  answers.value = Array(test.questions.length).fill(undefined)
  submissionId = createSubmissionId()
  started.value = false
  if (restoreDraft(test)) ElMessage.info('已恢复本次浏览器会话中的答题草稿')
}
function testDescription(test) {
  if (test.id === 'SDS') return '20题，用于整理近期情绪体验；结果待专业复核。'
  if (test.id === 'SAS') return '20题，用于整理近期紧张与焦虑体验；结果待专业复核。'
  if (test.id === 'MBTI') return '28题，供个人兴趣探索；结果不用于诊断或给人定型。'
  if (test.id === 'MentalAge') return '15题趣味问答，仅作娱乐参考，不代表实际心理年龄。'
  return test.desc || '了解这份问卷的用途和说明。'
}
function answeringInstruction(test) {
  return ['SDS', 'SAS'].includes(test?.id)
    ? '请按题目和问卷要求的时间范围，选择最符合你感受的一项。'
    : '请按自己的偏好或第一感受作答，无需寻找正确答案。'
}
function beginAnswering() {
  started.value = true
  nextTick(() => questionHeading.value?.focus())
}
watch(currentQIndex, async () => {
  await nextTick()
  questionHeading.value?.focus()
})
function selectOption(option) {
  if (submitting.value || !currentTest.value) return
  const answerChanged = answers.value[currentQIndex.value] !== option.val
  invalidateRequests()
  if (answerChanged) submissionId = createSubmissionId()
  answers.value[currentQIndex.value] = option.val
  submitError.value = ''
  saveDraft()
}
function isOptionSelected(option) {
  return answers.value[currentQIndex.value] === option.val
}
function goPrevQuestion() {
  if (currentQIndex.value > 0 && !submitting.value) {
    currentQIndex.value -= 1
    saveDraft()
  }
}
function goNextQuestion() {
  if (hasAnswer.value && currentQIndex.value < currentTest.value.questions.length - 1) {
    currentQIndex.value += 1
    saveDraft()
  }
}
function handleOptionKeys(event) {
  if (!['ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft'].includes(event.key)) return
  const options = currentOptions.value
  if (!options.length) return
  event.preventDefault()
  const selected = options.findIndex((option) => isOptionSelected(option))
  const radios = [...event.currentTarget.querySelectorAll('[role="radio"]')]
  const focused = radios.indexOf(event.target.closest('[role="radio"]'))
  const anchor = selected >= 0 ? selected : Math.max(0, focused)
  const step = ['ArrowDown', 'ArrowRight'].includes(event.key) ? 1 : -1
  const next = (anchor + step + options.length) % options.length
  selectOption(options[next])
  event.currentTarget.querySelectorAll('[role="radio"]')[next]?.focus()
}
function unwrapResponse(response) {
  return response?.data?.data || response?.data || {}
}
async function submitAnswers() {
  if (submitting.value || !currentTest.value || !allAnswered.value) return
  if (activeIdentity !== readIdentity()) {
    handleIdentityChange()
    return
  }
  submitting.value = true
  submitError.value = ''
  const epoch = invalidateRequests()
  if (!submissionId) submissionId = createSubmissionId()
  saveDraft()
  const test = currentTest.value
  const payload = buildAssessmentSubmission(test.id, answers.value, submissionId)
  try {
    const response = await axios.post('/api/student/tests/submit', payload)
    const data = unwrapResponse(response)
    if (
      epoch !== requestEpoch ||
      currentTest.value?.id !== test.id ||
      activeIdentity !== readIdentity()
    )
      return
    if (!matchesAssessmentResult(data, test.id))
      throw new Error('服务器返回的结果未与本次问卷匹配，请检查网络后重试。')
    testResult.value = data
    clearCurrentDraft()
  } catch (error) {
    if (epoch !== requestEpoch || currentTest.value?.id !== test.id) return
    submitError.value =
      error.message === '服务器返回的结果未与本次问卷匹配，请检查网络后重试。'
        ? error.message
        : error?.response?.data?.detail || '结果暂未保存。请保持答案不变后重试。'
  } finally {
    if (epoch === requestEpoch) submitting.value = false
  }
}
async function analyzeResult() {
  if (!testResult.value?.test_id || aiAnalyzing.value) return
  if (activeIdentity !== readIdentity()) {
    handleIdentityChange()
    return
  }
  aiAnalyzing.value = true
  aiError.value = ''
  aiAnalysis.value = null
  const epoch = invalidateRequests()
  const testId = testResult.value.test_id
  aiController = new AbortController()
  try {
    const response = await axios.post(
      '/api/student/tests/ai-analyze',
      { test_id: testId },
      { signal: aiController.signal },
    )
    const data = unwrapResponse(response)
    if (epoch !== requestEpoch) return
    if (
      currentTest.value?.id !== testResult.value?.test_type ||
      String(data.test_id) !== String(testId)
    )
      throw new Error('返回的AI说明与本次测评不匹配，请重试。')
    aiAnalysis.value = data
    if (data.status === 'unavailable')
      aiError.value = 'AI辅助说明暂不可用；你可以稍后重试，测评结果仍可查看。'
  } catch (error) {
    if (epoch !== requestEpoch) return
    aiError.value = error?.response?.data?.detail || 'AI辅助说明获取失败，请稍后重试。'
  } finally {
    if (epoch === requestEpoch) {
      aiAnalyzing.value = false
      aiController = null
    }
  }
}
function sourceLabel(source) {
  if (typeof source === 'string') return source
  if (source?.type === 'scoring_provenance') {
    return [
      source.label || '计分规则记录',
      source.tool_id && `工具 ${source.tool_id}`,
      source.form_version && `表单版本 ${source.form_version}`,
      source.scoring_version && `计分版本 ${source.scoring_version}`,
    ]
      .filter(Boolean)
      .join(' · ')
  }
  return (
    [source?.label, source?.title, source?.description, source?.reference, source?.url]
      .filter(Boolean)
      .join(' — ') || '来源信息未提供'
  )
}
function finishTest() {
  invalidateRequests()
  clearCurrentDraft()
  currentTest.value = null
  submitting.value = false
  aiAnalyzing.value = false
  testResult.value = null
  aiAnalysis.value = null
  aiError.value = ''
  started.value = false
}
function leaveToList() {
  if (submitting.value) return
  saveDraft()
  invalidateRequests()
  currentTest.value = null
  aiAnalyzing.value = false
  started.value = false
  aiAnalysis.value = null
}
function handleIdentityChange() {
  invalidateRequests()
  clearCurrentDraft()
  for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
    const key = sessionStorage.key(index)
    if (key?.startsWith(DRAFT_PREFIX)) sessionStorage.removeItem(key)
  }
  activeIdentity = readIdentity()
  currentTest.value = null
  testResult.value = null
  aiAnalysis.value = null
  aiError.value = ''
  submitError.value = ''
  submitting.value = false
  aiAnalyzing.value = false
  started.value = false
  ElMessage.info('登录身份已变化，已清除本次答题草稿。')
}
function onStorageChange(event) {
  if (event.key === 'user' && readIdentity() !== activeIdentity) handleIdentityChange()
}
onMounted(() => {
  clearLegacyDrafts()
  window.addEventListener('storage', onStorageChange)
})
onBeforeUnmount(() => {
  invalidateRequests()
  if (!readIdentity()) handleIdentityChange()
  window.removeEventListener('storage', onStorageChange)
})
</script>

<style scoped>
.test-page {
  max-width: 1040px;
  margin: 0 auto;
  padding-bottom: var(--space-8);
  color: var(--text-primary);
}
.page-heading {
  padding: var(--space-6) 0 var(--space-5);
  border-bottom: 1px solid var(--border);
}
.page-heading h1 {
  margin: 0;
  font-size: clamp(25px, 3vw, 32px);
  line-height: 1.3;
  letter-spacing: -0.02em;
}
.page-heading p,
.section-heading p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.65;
}
.library-section {
  padding-top: var(--space-6);
}
.section-heading {
  margin-bottom: var(--space-4);
}
.section-heading h2 {
  margin: 0;
  font-size: 19px;
}
.test-list {
  display: grid;
  gap: 12px;
}
.test-entry {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}
.entry-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: 23px;
}
.entry-icon.large {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  font-size: 28px;
}
.entry-copy h3 {
  margin: 0;
  font-size: 17px;
}
.entry-copy p {
  margin: 5px 0 8px;
  color: var(--text-secondary);
  line-height: 1.55;
}
.question-count {
  color: var(--text-secondary);
  font-size: 13px;
}
.intro-panel {
  margin: var(--space-6) auto;
  max-width: 720px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}
.text-button {
  border: 0;
  padding: 8px 0;
  background: transparent;
  color: var(--brand-700);
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.text-button:focus-visible,
.text-button:disabled {
  outline: 3px solid var(--focus-ring);
  outline-offset: 3px;
}
.intro-copy {
  max-width: 560px;
  margin: 24px auto 8px;
  text-align: center;
}
.intro-copy h2 {
  margin: 0;
  font-size: 24px;
}
.intro-copy > p {
  color: var(--text-secondary);
  line-height: 1.7;
}
.intro-copy ul {
  margin: 22px 0;
  padding: 18px 22px 18px 40px;
  text-align: left;
  background: var(--surface-warm);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  line-height: 1.75;
}
.intro-copy li + li {
  margin-top: 7px;
}
.intro-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}
.question-area {
  max-width: 760px;
  margin: var(--space-6) auto;
}
.question-topline,
.progress-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 14px;
}
.progress-block {
  margin: 12px 0 22px;
  padding: 12px 14px;
  background: var(--surface-warm);
  border-radius: var(--radius-md);
}
.progress-label {
  margin-bottom: 8px;
}
.question-card {
  padding: clamp(20px, 5vw, 36px);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.question-card h2 {
  margin: 0;
  font-size: clamp(20px, 3vw, 24px);
  line-height: 1.55;
}
.question-help {
  margin: 8px 0 22px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.option-list {
  display: grid;
  gap: 10px;
}
.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 54px;
  padding: 12px 16px;
  text-align: left;
  font: inherit;
  color: var(--text-primary);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    border-color var(--motion-fast),
    background-color var(--motion-fast);
}
.option-item:hover,
.option-item.selected {
  border-color: var(--brand-600);
  background: var(--brand-50);
}
.option-item:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 2px;
}
.option-mark {
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  border: 1px solid var(--gray-400);
  border-radius: 50%;
}
.option-item.selected .option-mark {
  border: 5px solid var(--brand-600);
}
.question-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 24px;
}
.forward-actions {
  display: flex;
  gap: 8px;
}
.submit-error,
.ai-error {
  color: var(--danger-text);
  background: var(--danger-100);
  padding: 12px;
  border-radius: var(--radius-md);
  line-height: 1.5;
}
.result-area {
  max-width: 780px;
  margin: var(--space-6) auto;
}
.result-card {
  padding: clamp(20px, 5vw, 36px);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.result-mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  color: var(--brand-700);
  background: var(--brand-50);
  border-radius: var(--radius-md);
  font-size: 25px;
}
.result-kicker {
  margin: 20px 0 5px;
  color: var(--text-secondary);
  font-size: 14px;
}
.result-card h2 {
  margin: 0;
  font-size: 25px;
}
.status-note {
  margin: 12px 0;
  padding: 12px 14px;
  color: var(--warning-text);
  background: var(--warning-100);
  border-radius: var(--radius-md);
  line-height: 1.6;
}
.result-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 22px 0;
}
.result-facts div {
  min-width: 140px;
  padding: 12px 14px;
  background: var(--surface-warm);
  border-radius: var(--radius-md);
}
.result-facts dt {
  color: var(--text-secondary);
  font-size: 13px;
}
.result-facts dd {
  margin: 4px 0 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.result-description {
  line-height: 1.7;
  white-space: pre-wrap;
}
.basis-details {
  margin: 20px 0;
  padding: 14px 16px;
  background: var(--surface-warm);
  border-radius: var(--radius-md);
}
.basis-details summary {
  color: var(--brand-700);
  cursor: pointer;
  font-weight: 600;
}
.basis-details p {
  color: var(--text-secondary);
  line-height: 1.65;
}
.result-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.ai-analysis {
  margin-top: 22px;
  padding: 20px;
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radius-lg);
}
.ai-analysis h3 {
  margin: 0;
  font-size: 19px;
}
.ai-analysis h4 {
  margin: 18px 0 6px;
  font-size: 15px;
}
.ai-analysis p,
.ai-analysis li {
  line-height: 1.7;
  color: var(--text-primary);
}
.ai-analysis ul {
  padding-left: 22px;
}
.source-context {
  margin-top: 8px;
  color: var(--text-secondary) !important;
  font-size: 12px;
}
.ai-status,
.ai-caveat {
  color: var(--text-secondary) !important;
  font-size: 13px;
}
.ai-caveat {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px solid var(--brand-100);
}
.ai-error {
  margin-top: 18px;
}
.ai-error p {
  margin: 0 0 8px;
}
@media (max-width: 600px) {
  .test-page {
    padding-bottom: var(--space-5);
  }
  .test-entry {
    grid-template-columns: 40px minmax(0, 1fr);
    gap: 12px;
    padding: 15px;
  }
  .test-entry :deep(.el-button) {
    grid-column: 1 / -1;
    width: 100%;
    min-height: 44px;
  }
  .entry-icon {
    width: 40px;
    height: 40px;
  }
  .question-topline {
    align-items: flex-start;
  }
  .question-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .question-actions :deep(.el-button) {
    width: 100%;
    min-height: 44px;
    margin: 0;
  }
  .forward-actions {
    display: contents;
  }
  .intro-actions {
    flex-direction: column;
  }
  .intro-actions :deep(.el-button) {
    min-height: 44px;
    margin: 0;
  }
  .result-actions :deep(.el-button) {
    flex: 1 1 100%;
    min-height: 44px;
    margin: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .option-item {
    transition: none;
  }
}
</style>
