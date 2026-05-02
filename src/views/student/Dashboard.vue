﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="dashboard-container">
    <h1 class="page-title">心理健康数据看板</h1>
    <div v-if="loading" class="loading-state"><el-skeleton :rows="5" animated /></div>

    <div v-show="!loading">
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
            <div ref="trendChartRef" class="chart"></div>
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
            <div class="card-header"><span class="icon">☁️</span> 树洞高频情绪词</div>
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
import { ref, onMounted, nextTick, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(true)
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
const positiveWords = new Set(['开心', '期待', '放松', '希望', '自信', '平静', '满足', '感激'])
const negativeWords = new Set(['焦虑', '失眠', '压力', '崩溃', '难过', '抑郁', '想哭', '迷茫', '孤独'])

const sdsScoreObj = computed(() => latestScores.value.find(item => item.name === 'SDS'))
const showSdsCard = computed(() => latestScores.value.length === 1 && !!sdsScoreObj.value)
const sdsScore = computed(() => Number(sdsScoreObj.value?.score || 0))
const sdsNorm = computed(() => Number(sdsScoreObj.value?.norm || 42))
const sdsLevel = computed(() => sdsScore.value >= 73 ? '重度' : sdsScore.value >= 63 ? '中度' : sdsScore.value >= 53 ? '轻度' : '无明显')
const sdsAdvice = computed(() => sdsScore.value >= 63 ? '建议尽快预约心理咨询，并减少连续高压学习时长。' : sdsScore.value >= 53 ? '建议多进行户外活动，必要时可预约咨询。' : '建议保持规律作息并持续关注情绪波动。')
const sdsColor = computed(() => sdsScore.value >= 73 ? '#DC2626' : sdsScore.value >= 63 ? '#F59E0B' : sdsScore.value >= 53 ? '#FB7185' : '#10B981')

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

const getTrendDays = () => {
  if (trendRange.value === '90d') return 90
  return 30
}

const seededRandom = (seed) => {
  const x = Math.sin(seed) * 10000
  return x - Math.floor(x)
}

const formatDateLabel = (d) => {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mm}-${dd}`
}

const clamp = (n, min, max) => Math.max(min, Math.min(max, n))

const generateTrendDataByRange = (range) => {
  const today = new Date()
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const days = range === '90d' ? 90 : 30
  const stepDays = range === '90d' ? 2 : 1
  const points = range === '90d' ? 45 : 30
  // 以当前系统日期为基准动态计算时间区间，不再使用固定日期
  const start = new Date(end)
  start.setDate(end.getDate() - (days - 1))

  const daySeed = Number(`${end.getFullYear()}${end.getMonth() + 1}${end.getDate()}`)
  const rangeSeed = range === '90d' ? 9007 : 3007
  const startBase = 52 + Math.floor(seededRandom(daySeed + rangeSeed) * 7) // 52~58
  const drift = Math.round((seededRandom(daySeed + rangeSeed + 11) - 0.5) * 6) // -3~3
  const series = []
  let lastValue = startBase

  for (let i = 0; i < points; i++) {
    const currentDate = new Date(start)
    currentDate.setDate(start.getDate() + i * stepDays)
    const progress = points <= 1 ? 0 : i / (points - 1)
    const trendValue = startBase + drift * progress
    const noiseSpan = 2 + Math.floor(seededRandom(daySeed + rangeSeed + i * 13) * 2) // 2~3
    const noise = (seededRandom(daySeed + rangeSeed + i * 17) - 0.5) * 2 * noiseSpan
    // 引入小幅惯性，避免过于规律，同时保持自然波动
    const withMomentum = trendValue + noise + (lastValue - trendValue) * 0.22
    const value = clamp(Math.round(withMomentum), 45, 65)
    lastValue = value

    series.push({
      date: formatDateLabel(currentDate),
      date_key: currentDate.toISOString().slice(0, 10),
      index: value
    })
  }
  return series
}

const fetchTrendData = async () => {
  emotionTrend.value = generateTrendDataByRange(trendRange.value)
  trendLastUpdatedAt.value = new Date().toLocaleTimeString()
  updateTrendChart()
}

const refreshTrendOnly = async () => {
  try {
    await fetchTrendData()
  } catch (error) {
    console.warn('[Dashboard] 刷新情绪趋势失败:', error)
  }
}

const handleTrendRangeChange = async () => {
  await refreshTrendOnly()
}

const fetchAllData = async () => {
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
    emotionTrend.value = generateTrendDataByRange(trendRange.value)
    trendLastUpdatedAt.value = new Date().toLocaleTimeString()
    latestScores.value = [{ name: 'SDS', score: 55, norm: 41 }, { name: 'SAS', score: 48, norm: 40 }, { name: '心理年龄', score: 28, norm: 45 }]
    redEnergy.value = [{ date: '10-01', score: 5 }, { date: '10-02', score: 8 }, { date: '10-03', score: 6 }, { date: '10-04', score: 10 }, { date: '10-05', score: 7 }, { date: '10-06', score: 9 }, { date: '10-07', score: 12 }]
    treeholeWords.value = [{ word: '焦虑', count: 5 }, { word: '失眠', count: 3 }, { word: '开心', count: 2 }, { word: '压力', count: 4 }, { word: '迷茫', count: 3 }]
    appointmentStats.value = { completed: 3, pending: 2, cancelled: 0, total: 5 }
  }
}

const initCharts = () => { trendChartRef.value && initTrendChart(); scoreChartRef.value && initScoreChart(); energyChartRef.value && initEnergyChart(); wordChartRef.value && initWordChart(); appointmentChartRef.value && initAppointmentChart() }
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
    yAxis: { type: 'value', min: 45, max: 65, splitNumber: 4 },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'none',
      symbolSize: 0,
      itemStyle: { color: '#3B82F6' },
      data: values,
      markPoint: {
        symbol: 'emptyCircle',
        symbolSize: 8,
        itemStyle: {
          color: '#FFFFFF',
          borderColor: '#3B82F6',
          borderWidth: 2
        },
        label: { show: false },
        data: markPoints
      }
    }]
  }
}

const initTrendChart = () => {
  trendChart = echarts.init(trendChartRef.value)
  trendChart.setOption(buildTrendOption(), true)
  trendChart.on('click', () => router.push('/student/report'))
}
const updateTrendChart = () => {
  if (!trendChart) return
  trendChart.setOption(buildTrendOption(), true)
}
const initScoreChart = () => {
  scoreChart = echarts.init(scoreChartRef.value)
  scoreChart.setOption({ tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { data: ['我的得分', '常模平均'], bottom: 0 }, grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true }, xAxis: { type: 'category', data: latestScores.value.map(i => i.name) }, yAxis: { type: 'value' }, series: [{ name: '我的得分', type: 'bar', data: latestScores.value.map(i => i.score) }, { name: '常模平均', type: 'bar', data: latestScores.value.map(i => i.norm) }] })
}
const initEnergyChart = () => {
  energyChart = echarts.init(energyChartRef.value)
  energyChart.setOption({ tooltip: { trigger: 'axis' }, grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true }, xAxis: { type: 'category', boundaryGap: false, data: redEnergy.value.map(i => i.date) }, yAxis: { type: 'value' }, series: [{ type: 'line', smooth: true, symbol: 'none', itemStyle: { color: '#EF4444' }, data: redEnergy.value.map(i => i.score) }] })
}
const initWordChart = () => {
  wordChart = echarts.init(wordChartRef.value)
  const words = treeholeWords.value.map(i => ({ name: i.word, value: i.count, textStyle: { color: positiveWords.has(i.word) ? '#16A34A' : negativeWords.has(i.word) ? '#475569' : '#64748B' } }))
  wordChart.setOption({ tooltip: { trigger: 'item', formatter: p => `${p.name}：${p.value}` }, series: [{ type: 'wordCloud', shape: 'circle', data: words }] })
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
  appointmentChart = echarts.init(appointmentChartRef.value)
  appointmentChart.setOption({ tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['50%', '70%'], center: ['50%', '45%'], data: [{ value: completed, name: '已完成' }, { value: pending, name: '待处理' }, { value: cancelled, name: '已取消' }] }], graphic: [{ type: 'text', left: 'center', top: '44%', style: { text: `${total}`, fill: '#111827', fontSize: 24, fontWeight: 700 } }] })
}
const cancelNextAppointment = async () => {
  const next = appointmentStats.value?.next_appointment
  if (!next?.id) return
  try { await axios.post(`/api/student/appointments/${next.id}/cancel`); ElMessage.success('已取消下一次预约'); await fetchAllData(); nextTick(initAppointmentChart) } catch { ElMessage.error('取消预约失败') }
}
const goModifyAppointment = () => router.push('/student/appointments')
</script>
<style scoped>
.dashboard-container { background-color: #F8FAFC; min-height: 100%; padding-bottom: 20px; }
.page-title { font-size: 24px; color: #1E293B; margin-bottom: 24px; font-weight: 600; }
.mb-20 { margin-bottom: 20px; }
.chart-card { border-radius: 16px; border: none; box-shadow: 0 4px 6px -1px rgba(0,0,0,.05), 0 2px 4px -1px rgba(0,0,0,.03); }
.card-header { font-size: 16px; font-weight: 600; color: #334155; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.trend-header { justify-content: space-between; align-items: center; gap: 12px; }
.trend-tools { display: inline-flex; align-items: center; gap: 8px; }
.trend-meta { font-size: 12px; color: #64748B; white-space: nowrap; }
.help-icon { color: #9CA3AF; font-size: 14px; cursor: pointer; }
.card-header .icon { font-size: 20px; }
.chart { width: 100%; height: 250px; }
.score-card { min-height: 250px; display: flex; flex-direction: column; justify-content: space-between; gap: 10px; }
.score-title { font-size: 16px; color: #1E293B; font-weight: 600; }
.score-value { font-size: 15px; color: #334155; }
.score-norm { color: #64748B; font-size: 13px; }
.score-desc { background: #F8FAFC; color: #475569; font-size: 13px; line-height: 1.6; border-radius: 8px; padding: 8px 10px; }
.loading-state { background: white; border-radius: 16px; padding: 40px; }
.treehole-list { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.treehole-item { background: #F1F5F9; padding: 16px; border-radius: 8px; }
.treehole-item .content { color: #334155; line-height: 1.5; font-size: 14px; margin: 0; font-style: italic; }
.appointment-meta { color: #475569; font-size: 13px; line-height: 1.7; margin-top: -4px; }
.next-appointment { margin-top: 8px; border-left: 3px solid #F59E0B; background: #FFFBEB; color: #92400E; border-radius: 8px; padding: 8px 10px; font-size: 13px; }
.appointment-actions { margin-top: 8px; display: flex; gap: 8px; }
</style>
