﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="dashboard-container">
    <el-alert v-if="loadError" class="data-error" :title="loadError" type="error" :closable="false" show-icon><el-button link type="primary" @click="retryDashboard">重新加载</el-button></el-alert>
    <div v-if="loading" class="loading-state"><el-skeleton :rows="5" animated /></div>

    <div v-show="!loading && !loadError">
      <el-row :gutter="20">
        <el-col :xs="24" :md="16" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header trend-header">
              <div><span class="icon">📈</span> 情绪趋势曲线</div>
              <div class="trend-tools">
                <el-select v-model="trendRange" size="small" style="width: 110px" @change="handleTrendRangeChange">
                  <el-option label="近7天" value="7d" />
                  <el-option label="近30天" value="30d" />
                  <el-option label="近90天" value="90d" />
                </el-select>
                <span class="trend-meta">更新: {{ trendLastUpdatedAt || '--:--:--' }}</span>
              </div>
            </div>
            <div v-if="!emotionTrend.length" class="data-empty">暂无情绪趋势记录，完成测评后可在这里查看。</div><div v-show="emotionTrend.length" ref="trendChartRef" class="chart"></div>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="8" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header">
              <span class="icon">📊</span> 量表得分对比
              <el-popover placement="top" width="220" trigger="click" content="该常模基于全国大学生群体数据。">
                <template #reference><el-icon class="help-icon"><QuestionFilled /></el-icon></template>
              </el-popover>
            </div>
            <div v-if="showSdsCard" class="score-card">
              <div class="score-title">SDS抑郁自评量表</div>
              <div class="score-value">您的得分：{{ sdsScore }}分（{{ sdsLevel }}）</div>
              <el-progress :percentage="Math.min(100, Math.max(0, sdsScore))" :stroke-width="16" :color="sdsColor" />
              <div class="score-norm">常模平均：{{ sdsNorm }}分</div>
              <div class="score-desc">您的得分 {{ sdsScore }} 分，属于{{ sdsLevel }}抑郁倾向。{{ sdsAdvice }}</div>
            </div>
            <div v-else ref="scoreChartRef" class="chart"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :xs="24" :md="8" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header"><span class="icon">🔥</span> 红色能量积分趋势</div>
            <div ref="energyChartRef" class="chart"></div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="8" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header"><span class="icon">☁️</span> 树洞词频</div>
            <div ref="wordChartRef" class="chart"></div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="8" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header"><span class="icon">📅</span> 预约完成度</div>
            <div ref="appointmentChartRef" class="chart"></div>
            <div class="appointment-meta">
              <div>总预约：{{ appointmentStats.total || 0 }} 个</div>
              <div>已完成：{{ appointmentStats.completed || 0 }} 个</div>
              <div>待处理：{{ appointmentStats.pending || 0 }} 个</div>
              <div>已取消：{{ appointmentStats.cancelled || 0 }} 个</div>
            </div>
            <div v-if="appointmentStats.next_appointment" class="next-appointment">
              您的下一次咨询：{{ appointmentStats.next_appointment.time_slot }}
              <div class="appointment-actions">
                <el-button size="small" type="danger" plain @click="cancelNextAppointment">取消</el-button>
                <el-button size="small" type="primary" plain @click="goModifyAppointment">修改</el-button>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-dialog v-model="wordDialogVisible" :title="`包含「${currentWord}」的树洞心声`" width="500px">
      <div v-if="treeholePosts.length > 0" class="treehole-list">
        <div v-for="post in treeholePosts" :key="post.id" class="treehole-item">
          <p class="content">"{{ post.content }}"</p>
          <div class="meta text-xs text-gray-500 mt-10 text-right">{{ new Date(post.created_at).toLocaleString() }}</div>
        </div>
      </div>
      <el-empty v-else description="暂无相关帖子" />
    </el-dialog>
  </div>
</template>

<script setup>
import { businessColor } from '../../styles/business-theme.js'
import { ref, onMounted, nextTick, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(true)
const loadError = ref('')
const emotionTrend = ref([])
const latestScores = ref([])
const redEnergy = ref([])
const treeholeWords = ref([])
const appointmentStats = ref({})
const trendChartRef = ref(null)
const scoreChartRef = ref(null)
const energyChartRef = ref(null)
const wordChartRef = ref(null)
const appointmentChartRef = ref(null)
let trendChart = null
let scoreChart = null
let energyChart = null
let wordChart = null
let appointmentChart = null
const wordDialogVisible = ref(false)
const currentWord = ref('')
const treeholePosts = ref([])
const trendRange = ref('30d')
const trendLastUpdatedAt = ref('')

const sdsScoreObj = computed(() => latestScores.value.find(item => item.name === 'SDS'))
const showSdsCard = computed(() => latestScores.value.length === 1 && !!sdsScoreObj.value)
const sdsScore = computed(() => Number(sdsScoreObj.value?.score || 0))
const sdsNorm = computed(() => Number(sdsScoreObj.value?.norm || 42))
const sdsLevel = computed(() => sdsScore.value >= 73 ? '重度' : sdsScore.value >= 63 ? '中度' : sdsScore.value >= 53 ? '轻度' : '无明显')
const sdsAdvice = computed(() => sdsScore.value >= 63 ? '建议尽快预约心理咨询，并减少连续高压学习时长。' : sdsScore.value >= 53 ? '建议多进行户外活动，必要时可预约咨询。' : '建议保持规律作息并持续关注情绪波动。')
const sdsColor = computed(() => sdsScore.value >= 73 ? businessColor('data-risk-high') : sdsScore.value >= 63 ? businessColor('data-risk-mid') : sdsScore.value >= 53 ? businessColor('danger-100') : businessColor('data-risk-low'))

onMounted(async () => {
  await fetchAllData()
  loading.value = false
  nextTick(initCharts)
  window.addEventListener('resize', resizeCharts)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  trendChart && trendChart.dispose(); scoreChart && scoreChart.dispose(); energyChart && energyChart.dispose(); wordChart && wordChart.dispose(); appointmentChart && appointmentChart.dispose()
})
const resizeCharts = () => { trendChart && trendChart.resize(); scoreChart && scoreChart.resize(); energyChart && energyChart.resize(); wordChart && wordChart.resize(); appointmentChart && appointmentChart.resize() }

const fetchTrendData = async () => {
  const days = Number.parseInt(trendRange.value, 10)
  const res = await axios.get('/api/student/dashboard/emotion_trend', { params: { days, limit: days } })
  emotionTrend.value = Array.isArray(res.data) ? res.data : []
  trendLastUpdatedAt.value = new Date().toLocaleTimeString()
  updateTrendChart()
}

const refreshTrendOnly = async () => {
  try {
    await fetchTrendData()
    await nextTick()
    if (!trendChart && emotionTrend.value.length) initTrendChart()
    else trendChart?.resize()
  } catch (error) {
    ElMessage.error('情绪趋势加载失败，请稍后重试')
  }
}

const handleTrendRangeChange = async () => {
  await refreshTrendOnly()
}

const fetchAllData = async () => {
  loadError.value = ''
  try {
    const [scoresRes, energyRes, wordsRes, aptRes] = await Promise.all([
      axios.get('/api/student/dashboard/latest_scores'),
      axios.get('/api/student/dashboard/red_energy'),
      axios.get('/api/student/dashboard/treehole_words'),
      axios.get('/api/student/dashboard/appointment_stats')
    ])
    await fetchTrendData()
    latestScores.value = scoresRes.data
    redEnergy.value = energyRes.data
    treeholeWords.value = wordsRes.data
    appointmentStats.value = aptRes.data
  } catch {
    loadError.value = '数据加载失败，请重新加载。'
  }
}

const retryDashboard = async () => {
  loading.value = true
  await fetchAllData()
  loading.value = false
  await nextTick()
  initCharts()
}

const initCharts = () => { if (loadError.value) return; emotionTrend.value.length && trendChartRef.value && initTrendChart(); scoreChartRef.value && initScoreChart(); energyChartRef.value && initEnergyChart(); wordChartRef.value && initWordChart(); appointmentChartRef.value && initAppointmentChart() }
const buildTrendOption = () => {
  const values = emotionTrend.value.map(i => Number(i.index))
  const markStep = 7
  const markPoints = emotionTrend.value
    .map((item, idx) => (idx % markStep === 0 || idx === emotionTrend.value.length - 1 ? {
      coord: [item.date, Number(item.index)],
      value: Number(item.index)
    } : null))
    .filter(Boolean)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true },
    xAxis: { type: 'category', data: emotionTrend.value.map(i => i.date), boundaryGap: false },
    yAxis: { type: 'value', min: 0, max: 100, splitNumber: 4 },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'none',
      symbolSize: 0,
      itemStyle: { color: businessColor('data-primary') },
      data: values,
      markPoint: {
        symbol: 'emptyCircle',
        symbolSize: 8,
        itemStyle: {
          color: businessColor('surface'),
          borderColor: businessColor('data-primary'),
          borderWidth: 2
        },
        label: { show: false },
        data: markPoints
      }
    }]
  }
}

const initTrendChart = () => {
  trendChart?.dispose()
  trendChart = echarts.init(trendChartRef.value, 'xinyu-business')
  trendChart.setOption(buildTrendOption(), true)
  trendChart.on('click', () => router.push('/student/report'))
}
const updateTrendChart = () => {
  if (!trendChart) return
  trendChart.setOption(buildTrendOption(), true)
}
const initScoreChart = () => {
  scoreChart?.dispose()
  scoreChart = echarts.init(scoreChartRef.value, 'xinyu-business')
  scoreChart.setOption({ tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { data: ['我的得分', '常模平均'], bottom: 0 }, grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true }, xAxis: { type: 'category', data: latestScores.value.map(i => i.name) }, yAxis: { type: 'value' }, series: [{ name: '我的得分', type: 'bar', data: latestScores.value.map(i => i.score) }, { name: '常模平均', type: 'bar', data: latestScores.value.map(i => i.norm) }] })
}
const initEnergyChart = () => {
  energyChart?.dispose()
  energyChart = echarts.init(energyChartRef.value, 'xinyu-business')
  energyChart.setOption({ tooltip: { trigger: 'axis' }, grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true }, xAxis: { type: 'category', boundaryGap: false, data: redEnergy.value.map(i => i.date) }, yAxis: { type: 'value' }, series: [{ type: 'line', smooth: true, symbol: 'none', itemStyle: { color: businessColor('data-risk-high') }, data: redEnergy.value.map(i => i.score) }] })
}
const initWordChart = () => {
  wordChart?.dispose()
  wordChart = echarts.init(wordChartRef.value, 'xinyu-business')
  const words = treeholeWords.value.map(i => ({ name: i.word, value: i.count })).sort((a, b) => b.value - a.value)
  wordChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 30, top: 18, bottom: 20, containLabel: true },
    xAxis: { type: 'value', min: 0, minInterval: 1, name: '次数', nameLocation: 'middle', nameGap: 26 },
    yAxis: { type: 'category', inverse: true, data: words.map(item => item.name) },
    series: [{
      name: '出现次数', type: 'bar', barMaxWidth: 24, data: words,
      itemStyle: { color: businessColor('data-secondary'), borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: businessColor('text-secondary'), fontSize: 12 },
    }],
  })
  wordChart.on('click', async (params) => {
    currentWord.value = params.name
    try {
      const res = await axios.get(`/api/student/treehole/search_by_word?word=${encodeURIComponent(params.name)}`)
      treeholePosts.value = res.data
      wordDialogVisible.value = true
    } catch {
      ElMessage.error('获取树洞详情失败')
    }
  })
}
const initAppointmentChart = () => {
  const { completed = 0, pending = 0, cancelled = 0, total = 0 } = appointmentStats.value
  appointmentChart?.dispose()
  appointmentChart = echarts.init(appointmentChartRef.value, 'xinyu-business')
  appointmentChart.setOption({ tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['50%', '70%'], center: ['50%', '45%'], data: [{ value: completed, name: '已完成' }, { value: pending, name: '待处理' }, { value: cancelled, name: '已取消' }] }], graphic: [{ type: 'text', left: 'center', top: '44%', style: { text: `${total}`, fill: businessColor('text-primary'), fontSize: 24, fontWeight: 700 } }] })
}
const cancelNextAppointment = async () => {
  const next = appointmentStats.value?.next_appointment
  if (!next?.id) return
  try { await axios.post(`/api/student/appointments/${next.id}/cancel`); ElMessage.success('已取消下一次预约'); await fetchAllData(); nextTick(initAppointmentChart) } catch { ElMessage.error('取消预约失败') }
}
const goModifyAppointment = () => router.push('/student/appointments')
</script>
<style scoped>
.dashboard-container { background-color: var(--surface-subtle); min-height: 100%; padding-bottom: 20px; }
.page-title { font-size: 24px; color: var(--text-primary); margin-bottom: 24px; font-weight: 600; }
.mb-20 { margin-bottom: 20px; }
.chart-card { border-radius: 16px; border: none; box-shadow: 0 4px 6px -1px color-mix(in srgb, var(--gray-900) 5%, transparent), 0 2px 4px -1px color-mix(in srgb, var(--gray-900) 3%, transparent); }
.card-header { font-size: 16px; font-weight: 600; color: var(--text-primary); margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.trend-header { justify-content: space-between; align-items: center; gap: 12px; }
.trend-tools { display: inline-flex; align-items: center; gap: 8px; }
.trend-meta { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.help-icon { color: var(--text-secondary); font-size: 14px; cursor: pointer; }
.card-header .icon { font-size: 20px; }
.chart { width: 100%; height: 250px; }
.score-card { min-height: 250px; display: flex; flex-direction: column; justify-content: space-between; gap: 10px; }
.score-title { font-size: 16px; color: var(--text-primary); font-weight: 600; }
.score-value { font-size: 15px; color: var(--text-primary); }
.score-norm { color: var(--text-secondary); font-size: 13px; }
.score-desc { background: var(--surface-subtle); color: var(--text-secondary); font-size: 13px; line-height: 1.6; border-radius: 8px; padding: 8px 10px; }
.loading-state { background: var(--surface); border-radius: 16px; padding: 40px; }
.treehole-list { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.treehole-item { background: var(--surface-subtle); padding: 16px; border-radius: 8px; }
.treehole-item .content { color: var(--text-primary); line-height: 1.5; font-size: 14px; margin: 0; font-style: italic; }
.appointment-meta { color: var(--text-secondary); font-size: 13px; line-height: 1.7; margin-top: -4px; }
.next-appointment { margin-top: 8px; border-left: 3px solid var(--warning-text); background: var(--warning-100); color: var(--warning-text); border-radius: 8px; padding: 8px 10px; font-size: 13px; }
.appointment-actions { margin-top: 8px; display: flex; gap: 8px; }
</style>
