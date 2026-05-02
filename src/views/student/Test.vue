<template>
  <div class="test-container">
    <h2 class="page-title">专业心理测评</h2>
    <p class="page-desc">了解自己，从这里开始。请选择适合您的专业量表进行测试。</p>

    <!-- 测评列表 -->
    <el-row :gutter="20" class="mt-30" v-if="!currentTest">
      <el-col :xs="24" :sm="12" :md="6" v-for="test in tests" :key="test.id">
        <el-card shadow="hover" class="test-card">
          <div class="test-icon">{{ test.icon }}</div>
          <h3 class="test-title">{{ test.title }}</h3>
          <p class="test-desc">{{ test.desc }}</p>
          <div class="test-meta">共 {{ test.questions.length }} 题</div>
          <el-button type="primary" class="w-full mt-10" round @click="startTest(test)">开始测试</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 答题区域 -->
    <div v-else-if="!testResult" class="question-area mt-30">
      <el-card class="question-card">
        <div class="flex-between mb-20">
          <el-button link @click="leaveToList"><el-icon><ArrowLeft /></el-icon> 返回列表</el-button>
          <div class="progress">进度: {{ currentQIndex + 1 }} / {{ currentTest.questions.length }}</div>
        </div>

        <div class="progress-wrap mb-20">
          <div class="progress-meta">
            <span>已完成 {{ answeredCount }} 题</span>
            <span>{{ progressPercent }}%</span>
          </div>
          <el-progress :percentage="progressPercent" :stroke-width="10" :show-text="false" />
        </div>
        
        <h3 class="q-title">{{ currentTest.questions[currentQIndex].title }}</h3>
        <p class="q-tip">请选择最符合你当前状态的选项；支持返回上一题并修改答案。</p>
        
        <div class="options">
          <div 
            v-for="(opt, idx) in getCurrentOptions()" 
            :key="idx"
            :class="['option-item', { 'is-selected': isOptionSelected(opt) }]"
            @click="selectOption(opt)"
          >
            {{ opt.label }}
          </div>
        </div>

        <div class="question-actions">
          <el-button :disabled="currentQIndex === 0 || submitting" @click="goPrevQuestion">返回上一题</el-button>
          <span class="question-hint" v-if="currentQIndex === 0">第一题不可返回</span>
          <span class="question-hint" v-else>可返回查看并修改上一题</span>
        </div>
      </el-card>
    </div>

    <!-- 结果区域 -->
    <div v-else class="result-area mt-30">
      <el-card class="result-card text-center">
        <div class="result-icon">✨</div>
        <h2>测试结果</h2>
        
        <div class="score-result">
          <div class="score-display">
            <span class="label">得分为：</span>
            <span class="value text-blue">{{ testResult.score }}</span>
            <template v-if="testResult.standard_score">
              <span class="label ml-10">标准分：</span>
              <span class="value text-purple">{{ testResult.standard_score }}</span>
            </template>
          </div>
          
          <div class="level-display mt-10">
            <span class="label">结果评级：</span>
            <span class="value big-type" :class="getRiskColor(testResult.risk_level)">{{ testResult.result_level }}</span>
          </div>
          
          <div class="desc-display mt-20 text-gray-600 text-left">
            <p v-html="testResult.desc"></p>
          </div>
        </div>

        <div class="result-actions mt-20">
          <el-button type="success" round :loading="aiAnalyzing" @click="analyzeResult">
            {{ aiAnalyzing ? 'AI 分析中...' : '✨ AI 深度解析' }}
          </el-button>
          <el-button type="primary" round @click="finishTest">返回测评大厅</el-button>
        </div>
        <div v-if="aiAnalysisText" class="ai-analysis-box mt-20 text-left">
          <div class="ai-analysis-head">
            <div class="ai-head-left">
              <span class="ai-badge">AI</span>
              <h4>深度解析结果</h4>
            </div>
            <span class="ai-model-tag">qwen3.6-plus</span>
          </div>
          <div class="ai-analysis-content">
            <p v-for="(line, idx) in aiAnalysisParagraphs" :key="`ai-line-${idx}`">{{ line }}</p>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { testsData } from '@/data/tests'
const tests = testsData

const currentTest = ref(null)
const currentQIndex = ref(0)
const userAnswers = ref([]) // 存储每题得分或选项值
const userAnswersDict = ref({}) // 存储键值对，用于记录具体答案
const testResult = ref(null)
const submitting = ref(false)
const aiAnalyzing = ref(false)
const aiAnalysisText = ref('')
const aiAnalysisParagraphs = computed(() => {
  const text = String(aiAnalysisText.value || '').trim()
  if (!text) return []
  return text
    .split(/\n+/)
    .map((x) => x.trim())
    .filter(Boolean)
})

const getProgressKey = (testId) => {
  const user = localStorage.getItem('user') || 'anonymous'
  return `psych_test_progress_${user}_${testId}`
}

const answeredCount = computed(() => userAnswers.value.filter(v => v !== undefined && v !== null).length)
const progressPercent = computed(() => {
  const total = currentTest.value?.questions?.length || 0
  if (!total) return 0
  return Math.round((answeredCount.value / total) * 100)
})

const saveProgress = () => {
  if (!currentTest.value || testResult.value) return
  const payload = {
    currentQIndex: currentQIndex.value,
    userAnswers: userAnswers.value,
    userAnswersDict: userAnswersDict.value,
    savedAt: Date.now(),
  }
  localStorage.setItem(getProgressKey(currentTest.value.id), JSON.stringify(payload))
}

const clearProgress = (testId) => {
  if (!testId) return
  localStorage.removeItem(getProgressKey(testId))
}

const createEmptyAnswers = (total) => Array(total).fill(undefined)

const restoreProgress = (test) => {
  const raw = localStorage.getItem(getProgressKey(test.id))
  if (!raw) return false
  try {
    const parsed = JSON.parse(raw)
    const total = test.questions.length
    if (!Array.isArray(parsed.userAnswers)) return false
    if (!parsed.userAnswersDict || typeof parsed.userAnswersDict !== 'object') return false
    const restoredAnswers = createEmptyAnswers(total)
    parsed.userAnswers.forEach((val, idx) => {
      if (idx < total) restoredAnswers[idx] = val
    })
    userAnswers.value = restoredAnswers
    userAnswersDict.value = parsed.userAnswersDict
    currentQIndex.value = Math.max(0, Math.min(Number(parsed.currentQIndex) || 0, total - 1))
    return true
  } catch {
    return false
  }
}

const startTest = (test) => {
  currentTest.value = test
  testResult.value = null
  submitting.value = false
  aiAnalysisText.value = ''
  const restored = restoreProgress(test)
  if (!restored) {
    currentQIndex.value = 0
    userAnswers.value = createEmptyAnswers(test.questions.length)
    userAnswersDict.value = {}
  } else {
    ElMessage.success('已恢复上次答题进度')
  }
}

const getCurrentOptions = () => {
  const q = currentTest.value.questions[currentQIndex.value]
  if (q.options) return q.options
  return currentTest.value.options
}

const selectOption = async (opt) => {
  if (submitting.value) return
  const q = currentTest.value.questions[currentQIndex.value]
  let val = opt.val
  
  if (currentTest.value.type === 'score' && q.reverse) {
    // 反向计分 (1->4, 2->3, 3->2, 4->1)
    val = 5 - val
  }
  
  userAnswers.value[currentQIndex.value] = val
  userAnswersDict.value[currentQIndex.value + 1] = opt.val // 记录原始选项值
  saveProgress()
  
  if (currentQIndex.value < currentTest.value.questions.length - 1) {
    currentQIndex.value++
    saveProgress()
  } else {
    await calculateAndSubmit()
  }
}

const isOptionSelected = (opt) => {
  return userAnswersDict.value[currentQIndex.value + 1] === opt.val
}

const goPrevQuestion = () => {
  if (currentQIndex.value === 0) {
    ElMessage.info('当前已是第一题')
    return
  }
  currentQIndex.value--
  saveProgress()
}

const calculateAndSubmit = async () => {
  if (submitting.value || !currentTest.value) return
  const unansweredIdx = userAnswers.value.findIndex((v) => v === undefined || v === null)
  if (unansweredIdx >= 0) {
    currentQIndex.value = unansweredIdx
    ElMessage.warning(`请先完成第 ${unansweredIdx + 1} 题`)
    saveProgress()
    return
  }
  submitting.value = true
  const type = currentTest.value.id
  let score = 0
  let standard_score = null
  let result_level = ''
  let risk_level = 'green'
  let desc = ''
  
  if (type === 'SDS') {
    score = userAnswers.value.reduce((a, b) => a + b, 0)
    standard_score = Math.floor(score * 1.25)
    if (standard_score < 53) {
      result_level = '正常'
      risk_level = 'green'
      desc = '您的抑郁自评标准分为正常范围，请继续保持良好的心态。'
    } else if (standard_score <= 62) {
      result_level = '轻度抑郁'
      risk_level = 'yellow'
      desc = '您的测试结果显示可能有轻度抑郁倾向。建议多参加户外活动，与亲友交流。'
    } else if (standard_score <= 72) {
      result_level = '中度抑郁'
      risk_level = 'red'
      desc = '您的测试结果显示可能有中度抑郁倾向。请重视自己的情绪变化，建议预约心理老师进行咨询。'
    } else {
      result_level = '重度抑郁'
      risk_level = 'red'
      desc = '您的测试结果显示可能有重度抑郁倾向。强烈建议您尽快寻求专业的心理医疗帮助。'
    }
  } else if (type === 'SAS') {
    score = userAnswers.value.reduce((a, b) => a + b, 0)
    standard_score = Math.floor(score * 1.25)
    if (standard_score < 50) {
      result_level = '正常'
      risk_level = 'green'
      desc = '您的焦虑自评标准分为正常范围。'
    } else if (standard_score <= 59) {
      result_level = '轻度焦虑'
      risk_level = 'yellow'
      desc = '您的测试结果显示可能有轻度焦虑倾向。可以通过深呼吸、冥想等方式放松。'
    } else if (standard_score <= 69) {
      result_level = '中度焦虑'
      risk_level = 'red'
      desc = '您的测试结果显示可能有中度焦虑倾向。建议寻找压力源并尝试缓解，必要时预约咨询。'
    } else {
      result_level = '重度焦虑'
      risk_level = 'red'
      desc = '您的测试结果显示可能有重度焦虑倾向。请及时寻求专业心理支持。'
    }
  } else if (type === 'MBTI') {
    const e = userAnswers.value.filter(v => v === 'E').length
    const i = userAnswers.value.filter(v => v === 'I').length
    const s = userAnswers.value.filter(v => v === 'S').length
    const n = userAnswers.value.filter(v => v === 'N').length
    const t = userAnswers.value.filter(v => v === 'T').length
    const f = userAnswers.value.filter(v => v === 'F').length
    const j = userAnswers.value.filter(v => v === 'J').length
    const p = userAnswers.value.filter(v => v === 'P').length
    
    const typeStr = `${e>i?'E':'I'}${s>n?'S':'N'}${t>f?'T':'F'}${j>p?'J':'P'}`
    score = 100 // dummy score
    result_level = typeStr
    risk_level = 'green'
    desc = `您的性格倾向是 <strong>${typeStr}</strong>。<br>MBTI仅作为自我了解的参考工具，帮助您发现自己的优势与潜在的职业倾向。`
  } else if (type === 'MentalAge') {
    score = userAnswers.value.reduce((a, b) => a + b, 0)
    if (score <= 25) {
      result_level = '纯真孩童'
      desc = '您的心理年龄偏小，保持着一颗纯真的童心。'
    } else if (score <= 50) {
      result_level = '青春少年'
      desc = '您的心理年龄处于青春期，充满活力与探索欲。'
    } else if (score <= 65) {
      result_level = '成熟青年'
      desc = '您的心理年龄适中，既有热情又不失理性。'
    } else {
      result_level = '稳重长者'
      desc = '您的心理年龄较为成熟，看待事物深沉而稳重。'
    }
    risk_level = 'green'
  }

  const result_json = { desc }
  
  testResult.value = { 
    type, 
    score, 
    standard_score, 
    result_level, 
    risk_level, 
    desc 
  }

  try {
    await axios.post('/api/student/tests/submit', {
      test_type: type,
      score: score,
      standard_score: standard_score,
      result_level: result_level,
      answers: JSON.stringify(userAnswersDict.value),
      result_json: JSON.stringify(result_json),
      risk_level: risk_level
    })
    clearProgress(type)
  } catch (error) {
    ElMessage.error('结果保存失败')
  } finally {
    submitting.value = false
  }
}

const getRiskColor = (risk) => {
  if (risk === 'red') return 'text-red'
  if (risk === 'yellow') return 'text-yellow'
  return 'text-green'
}

const analyzeResult = () => {
  if (!testResult.value || aiAnalyzing.value) return
  aiAnalyzing.value = true
  axios.post('/api/student/tests/ai-analyze', {})
    .then((res) => {
      const text = String(res?.data?.analysis || '').trim()
      aiAnalysisText.value = text || 'AI 暂未返回有效解析，请稍后重试。'
    })
    .catch((error) => {
      const detail = error?.response?.data?.detail
      ElMessage.error(typeof detail === 'string' ? detail : 'AI 解析失败，请稍后重试')
    })
    .finally(() => {
      aiAnalyzing.value = false
    })
}

const finishTest = () => {
  clearProgress(currentTest.value?.id)
  currentTest.value = null
  testResult.value = null
  aiAnalysisText.value = ''
}

const leaveToList = () => {
  saveProgress()
  currentTest.value = null
}

onBeforeUnmount(() => {
  saveProgress()
})
</script>

<style scoped>
.page-title {
  font-size: 24px;
  color: #1F2937;
  margin-bottom: 8px;
}
.page-desc {
  color: #6B7280;
  font-size: 14px;
}
.mt-30 { margin-top: 30px; }
.mt-20 { margin-top: 20px; }
.mt-10 { margin-top: 10px; }
.mb-20 { margin-bottom: 20px; }
.ml-10 { margin-left: 10px; }
.w-full { width: 100%; }
.text-center { text-align: center; }
.text-left { text-align: left; }
.text-blue { color: #3B82F6; }
.text-purple { color: #8B5CF6; }
.text-green { color: #10B981; }
.text-yellow { color: #F59E0B; }
.text-red { color: #EF4444; }

.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.test-card {
  border-radius: 16px;
  border: none;
  text-align: center;
  padding: 10px;
  transition: transform 0.3s ease;
  margin-bottom: 20px;
  height: 280px;
  display: flex;
  flex-direction: column;
}
.test-card:hover {
  transform: translateY(-8px);
}
.test-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
.test-title {
  font-size: 18px;
  color: #1F2937;
  margin-bottom: 8px;
}
.test-desc {
  font-size: 13px;
  color: #6B7280;
  margin-bottom: auto;
  height: 60px;
}
.test-meta {
  font-size: 12px;
  color: #9CA3AF;
  background-color: #F3F4F6;
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  margin-top: 10px;
}

/* Question Area */
.question-card {
  max-width: 600px;
  margin: 0 auto;
  border-radius: 16px;
  padding: 20px;
}
.progress {
  font-size: 14px;
  color: #9CA3AF;
}
.progress-wrap {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
}
.progress-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #4b5563;
  font-size: 13px;
  margin-bottom: 8px;
}
.q-title {
  font-size: 20px;
  color: #1F2937;
  margin-bottom: 10px;
  line-height: 1.4;
}
.q-tip {
  color: #6b7280;
  font-size: 13px;
  margin: 0 0 22px;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.option-item {
  padding: 16px 20px;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 16px;
  color: #4B5563;
}
.option-item:hover {
  background-color: #EFF6FF;
  border-color: #3B82F6;
  color: #1D4ED8;
}
.option-item.is-selected {
  background-color: #dbeafe;
  border-color: #2563eb;
  color: #1d4ed8;
  font-weight: 600;
}
.question-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 18px;
}
.question-hint {
  font-size: 12px;
  color: #6b7280;
}

/* Result Area */
.result-card {
  max-width: 500px;
  margin: 0 auto;
  border-radius: 16px;
  padding: 40px 20px;
}
.result-icon {
  font-size: 64px;
  margin-bottom: 20px;
  animation: float 2s ease-in-out infinite;
}
.big-type {
  font-size: 36px;
  font-weight: bold;
  margin: 10px 0;
  display: block;
}
.score-display {
  font-size: 18px;
  background: #F9FAFB;
  padding: 15px;
  border-radius: 8px;
}
.score-display .value {
  font-size: 24px;
  font-weight: bold;
}
.desc-display {
  line-height: 1.6;
  background: #F3F4F6;
  padding: 15px;
  border-radius: 8px;
}
.result-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.ai-analysis-box {
  background: linear-gradient(180deg, #f8fbff 0%, #f2f7ff 100%);
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.12);
}
.ai-analysis-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.ai-head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: #2563eb;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}
.ai-analysis-box h4 {
  margin: 0;
  font-size: 15px;
  color: #1f2937;
}
.ai-model-tag {
  font-size: 12px;
  color: #1d4ed8;
  background: #dbeafe;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 2px 10px;
  white-space: nowrap;
}
.ai-analysis-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-analysis-box p {
  margin: 0;
  font-size: 13.5px;
  color: #334155;
  line-height: 1.75;
  background: rgba(255, 255, 255, 0.65);
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid #e5edff;
}

@keyframes float {
  0% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
  100% { transform: translateY(0px); }
}
</style>
