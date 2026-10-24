﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="dashboard-container business-page">
    <el-alert v-if="loadError" class="data-error" :title="loadError" type="error" :closable="false" show-icon><el-button link type="primary" @click="retryDashboard">重新加载</el-button></el-alert>
    <div v-if="loading" class="loading-state"><el-skeleton :rows="5" animated /></div>

    <section v-show="!loading && !loadError" class="dashboard-content" aria-labelledby="dashboard-next-title">
      <header class="dashboard-intro">
        <div>
          <h2 id="dashboard-next-title">从这里开始</h2>
          <p>按你现在的需要选择下一步。测评、预约和对话记录分别展示，不合并成单一分数。</p>
        </div>
        <div class="action-links" aria-label="常用行动">
          <el-button type="primary" @click="router.push('/student/test')"><LibraryIcon name="assessment" /> 开始测评</el-button>
          <el-button plain @click="router.push('/student/appointments')"><LibraryIcon name="appointment" /> 预约咨询</el-button>
          <el-button plain @click="router.push('/student/questions')"><LibraryIcon name="support" /> 向老师留言</el-button>
          <el-button plain @click="router.push('/student/advanced-chat')"><LibraryIcon name="chat" /> 和助手聊聊</el-button>
        </div>
      </header>

      <el-card v-if="appointmentStats.next_appointment" class="next-appointment-card" shadow="never">
        <div class="next-appointment-copy">
          <strong>下一次预约</strong>
          <span>{{ appointmentStats.next_appointment.time_slot }}</span>
        </div>
        <div class="appointment-actions">
          <el-button size="small" plain @click="goModifyAppointment">查看预约</el-button>
          <el-button size="small" type="danger" plain @click="cancelNextAppointment">取消预约</el-button>
        </div>
      </el-card>

      <section class="insights-section" aria-labelledby="insights-title">
        <div class="section-heading">
          <div>
            <h2 id="insights-title">近期洞察</h2>
            <p>以下内容来自你的记录。图表帮助回看变化，不代替专业评估。</p>
          </div>
        </div>
      <el-row :gutter="20">
        <el-col :xs="24" :md="16" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header trend-header">
              <div><LibraryIcon name="report" class="icon" /> 情绪趋势曲线</div>
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
              <LibraryIcon name="assessment" class="icon" /> 量表得分对比
              <el-popover placement="top" width="240" trigger="click" content="常模来源与适用范围待核实，请以量表原始说明为准。">
                <template #reference><el-icon class="help-icon"><LibraryIcon name="help"  /></el-icon></template>
              </el-popover>
            </div>
            <div v-if="showSdsCard" class="score-card">
              <div class="score-title">SDS抑郁自评量表</div>
              <div class="score-value">本次得分：{{ sdsScoreObj.score ?? '暂无记录' }}<span v-if="sdsScoreObj.score != null">分</span></div>
              <div v-if="sdsScoreObj.norm != null" class="score-norm">参考值：{{ sdsScoreObj.norm }}分（来源与适用范围待核实）</div>
              <div class="score-desc">此处展示量表记录值，不作诊断或临床解释。请结合量表原始说明理解结果。</div>
            </div>
            <div v-else ref="scoreChartRef" class="chart"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :xs="24" :md="8" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header"><LibraryIcon name="support" class="icon" /> 红色能量积分趋势</div>
            <div ref="energyChartRef" class="chart"></div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="8" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header"><LibraryIcon name="treehole" class="icon" /> 树洞词频</div>
            <div ref="wordChartRef" class="chart"></div>
          </el-card>
        </el-col>

        <el-col :xs="24" :md="8" class="mb-20">
          <el-card class="chart-card" shadow="hover">
            <div class="card-header"><LibraryIcon name="appointment" class="icon" /> 预约完成度</div>
            <div ref="appointmentChartRef" class="chart"></div>
            <div class="appointment-meta">
              <div>总预约：{{ appointmentStats.total || 0 }} 个</div>
              <div>已完成：{{ appointmentStats.completed || 0 }} 个</div>
              <div>待处理：{{ appointmentStats.pending || 0 }} 个</div>
              <div>已取消：{{ appointmentStats.cancelled || 0 }} 个</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      </section>
    </section>

    <el-dialog v-model="wordDialogVisible" :title="`包含「${currentWord}」的树洞心声`" width="500px">
      <div v-if="treeholePosts.length > 0" class="treehole-list">
        <div v-for="post in treeholePosts" :key="post.id" class="treehole-item">
          <p class="content">"{{ post.content }}"</p>
          <div class="meta text-xs text-gray-500 mt-10 text-right">{{ new Date(post.created_at).toLocaleString() }}</div>
        </div>
      </div>
      <LibraryEmpty v-else description="暂无相关帖子" />
    </el-dialog>
  </div>
</template>

<script setup>
import { setLibraryChartOption } from '../../design/chart-registry'
import { businessColor } from '../../styles/business-theme.js'
import { ref, onMounted, nextTick, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import * as echarts from '../../design/charts/basic'
import { ElMessage, ElAlert, ElButton, ElSkeleton, ElRow, ElCol, ElCard, ElSelect, ElOption, ElPopover, ElIcon, ElProgress, ElDialog } from 'element-plus'

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

let unmounted = false
onMounted(async () => {
  await fetchAllData()
  if (unmounted) return
  loading.value = false
  await nextTick()
  if (unmounted) return
  initCharts()
  window.addEventListener('resize', resizeCharts)
})
onBeforeUnmount(() => {
  unmounted = true
  window.removeEventListener('resize', resizeCharts)
  trendChart && trendChart.dispose(); scoreChart && scoreChart.dispose(); energyChart && energyChart.dispose(); wordChart && wordChart.dispose(); appointmentChart && appointmentChart.dispose()
  trendChart = scoreChart = energyChart = wordChart = appointmentChart = null
})
const resizeCharts = () => { trendChart && trendChart.resize(); scoreChart && scoreChart.resize(); energyChart && energyChart.resize(); wordChart && wordChart.resize(); appointmentChart && appointmentChart.resize() }

const fetchTrendData = async () => {
  const days = Number.parseInt(trendRange.value, 10)
  const res = await axios.get('/api/student/dashboard/emotion_trend', { params: { days, limit: days } })
  if (unmounted) return
  emotionTrend.value = Array.isArray(res.data) ? res.data : []
  trendLastUpdatedAt.value = new Date().toLocaleTimeString()
  updateTrendChart()
}

const refreshTrendOnly = async () => {
  try {
    await fetchTrendData()
    await nextTick()
    if (unmounted) return
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
    if (unmounted) return
    latestScores.value = scoresRes.data
    redEnergy.value = energyRes.data
    treeholeWords.value = wordsRes.data
    appointmentStats.value = aptRes.data
  } catch {
    if (unmounted) return
    loadError.value = '数据加载失败，请重新加载。'
  }
}

const retryDashboard = async () => {
  loading.value = true
  await fetchAllData()
  if (unmounted) return
  loading.value = false
  await nextTick()
  initCharts()
}

const initCharts = () => { if (unmounted || loadError.value) return; emotionTrend.value.length && trendChartRef.value && initTrendChart(); scoreChartRef.value && initScoreChart(); energyChartRef.value && initEnergyChart(); wordChartRef.value && initWordChart(); appointmentChartRef.value && initAppointmentChart() }
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
  setLibraryChartOption(trendChart, buildTrendOption(), true)
  trendChart.on('click', () => router.push('/student/report'))
}
const updateTrendChart = () => {
  if (!trendChart) return
  setLibraryChartOption(trendChart, buildTrendOption(), true)
}
const initScoreChart = () => {
  scoreChart?.dispose()
  scoreChart = echarts.init(scoreChartRef.value, 'xinyu-business')
  setLibraryChartOption(scoreChart, { tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { data: ['我的得分', '常模平均'], bottom: 0 }, grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true }, xAxis: { type: 'category', data: latestScores.value.map(i => i.name) }, yAxis: { type: 'value' }, series: [{ name: '我的得分', type: 'bar', data: latestScores.value.map(i => i.score) }, { name: '常模平均', type: 'bar', data: latestScores.value.map(i => i.norm) }] })
}
const initEnergyChart = () => {
  energyChart?.dispose()
  energyChart = echarts.init(energyChartRef.value, 'xinyu-business')
  setLibraryChartOption(energyChart, { tooltip: { trigger: 'axis' }, grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true }, xAxis: { type: 'category', boundaryGap: false, data: redEnergy.value.map(i => i.date) }, yAxis: { type: 'value' }, series: [{ type: 'line', smooth: true, symbol: 'none', itemStyle: { color: businessColor('data-risk-high') }, data: redEnergy.value.map(i => i.score) }] })
}
const initWordChart = () => {
  wordChart?.dispose()
  wordChart = echarts.init(wordChartRef.value, 'xinyu-business')
  const words = treeholeWords.value.map(i => ({ name: i.word, value: i.count })).sort((a, b) => b.value - a.value)
  setLibraryChartOption(wordChart, {
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
  setLibraryChartOption(appointmentChart, { tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['50%', '70%'], center: ['50%', '45%'], data: [{ value: completed, name: '已完成' }, { value: pending, name: '待处理' }, { value: cancelled, name: '已取消' }] }], graphic: [{ type: 'text', left: 'center', top: '44%', style: { text: `${total}`, fill: businessColor('text-primary'), fontSize: 24, fontWeight: 700 } }] })
}
const cancelNextAppointment = async () => {
  const next = appointmentStats.value?.next_appointment
  if (!next?.id) return
  try { await axios.post(`/api/student/appointments/${next.id}/cancel`); ElMessage.success('已取消下一次预约'); await fetchAllData(); nextTick(initAppointmentChart) } catch { ElMessage.error('取消预约失败') }
}
const goModifyAppointment = () => router.push('/student/appointments')
</script>
<style scoped>
.dashboard-container { min-height: 100%; padding-bottom: 20px; }
.dashboard-content { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; min-width: 0; }
.dashboard-intro { display: grid; grid-template-columns: minmax(220px, .75fr) minmax(0, 1.25fr); align-items: center; gap: 24px; padding: 24px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); }
.dashboard-intro > *, .section-heading > * { min-width: 0; }
.dashboard-intro h2, .section-heading h2 { margin: 0; color: var(--text-primary); font-size: 20px; }
.dashboard-intro p, .section-heading p { margin: 8px 0 0; color: var(--text-secondary); line-height: 1.6; }
.action-links { display: flex; flex-wrap: wrap; gap: 10px; }
.next-appointment-card { border-left: 3px solid var(--accent-sage); }
.next-appointment-copy { display: flex; flex-wrap: wrap; gap: 10px 20px; color: var(--text-primary); }
.insights-section { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; min-width: 0; }
.section-heading { display: flex; justify-content: space-between; gap: 16px; }
.page-title { font-size: 24px; color: var(--text-primary); margin-bottom: 24px; font-weight: 600; }
.mb-20 { margin-bottom: 20px; }
.chart-card { border-radius: 16px; border: none; box-shadow: 0 4px 6px -1px color-mix(in srgb, var(--gray-900) 5%, transparent), 0 2px 4px -1px color-mix(in srgb, var(--gray-900) 3%, transparent); }
.card-header { font-size: 16px; font-weight: 600; color: var(--text-primary); margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.trend-header { justify-content: space-between; align-items: center; gap: 12px; }
.trend-tools { display: inline-flex; align-items: center; gap: 8px; }
.trend-meta { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.help-icon { color: var(--text-secondary); font-size: 14px; cursor: pointer; }
.card-header .icon { font-size: 20px; }
.chart { width: 100%; min-width: 0; height: 250px; }
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
.next-appointment-card :deep(.el-card__body) { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.appointment-actions { display: flex; flex-wrap: wrap; gap: 8px; }
@media (max-width: 600px) {
  .dashboard-intro { grid-template-columns: minmax(0, 1fr); padding: 18px; min-width: 0; }
  .action-links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); min-width: 0; }
  .action-links :deep(.el-button) { width: 100%; min-width: 0; min-height: 44px; margin: 0; padding-inline: 8px; white-space: normal; }
  .trend-header { align-items: flex-start; flex-direction: column; }
  .trend-header > *, .trend-tools { min-width: 0; max-width: 100%; }
  .trend-tools { width: 100%; flex-wrap: wrap; }
  .insights-section > .el-row { min-width: 0; max-width: 100%; }
  .next-appointment-card :deep(.el-card__body) { display: grid; gap: 12px; }
  .appointment-actions { flex-wrap: wrap; }
  .next-appointment-copy, .appointment-actions { min-width: 0; }
}
</style>
