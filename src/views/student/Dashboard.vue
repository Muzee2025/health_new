<template>
  <div class="dashboard-container business-page">
    <el-alert v-if="loadError" class="data-error" :title="loadError" type="error" :closable="false" show-icon><el-button link type="primary" @click="retryDashboard">重新加载</el-button></el-alert>
    <section class="dashboard-content" aria-labelledby="dashboard-next-title">
      <header class="dashboard-intro">
        <div>
          <h2 id="dashboard-next-title">从这里开始</h2>
          <p>按你现在的需要选择下一步。测评、预约和对话记录分别展示，不合并成单一分数。</p>
        </div>
        <div class="action-links" aria-label="常用行动">
          <el-button class="dashboard-action" type="primary" @click="router.push('/student/test')"><LibraryIcon name="assessment" /> 开始测评</el-button>
          <el-button class="dashboard-action" plain @click="router.push('/student/appointments')"><LibraryIcon name="appointment" /> 预约咨询</el-button>
          <el-button class="dashboard-action" plain @click="router.push('/student/questions')"><LibraryIcon name="support" /> 向老师留言</el-button>
          <el-button class="dashboard-action" plain @click="router.push('/student/advanced-chat')"><LibraryIcon name="chat" /> 和助手聊聊</el-button>
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
      <div class="insight-grid">
        <el-card class="chart-card trend-card" shadow="hover">
          <div class="card-heading trend-header">
            <div class="card-title">
              <div class="card-title-main"><LibraryIcon name="report" class="icon" /> 测评记录趋势</div>
              <p>{{ trendSummary.instrument ? `当前来源：${trendSummary.instrument}（最近一次工具），不同工具分别统计。` : '仅展示服务器返回的记录值。' }}同日取最后一条，缺测日期留空。</p>
            </div>
            <div class="trend-tools">
              <el-select v-model="trendRange" size="small" style="width: 110px" @change="handleTrendRangeChange">
                <el-option label="近7天" value="7d" />
                <el-option label="近30天" value="30d" />
                <el-option label="近90天" value="90d" />
              </el-select>
              <span class="trend-meta">更新 {{ trendLastUpdatedAt || '—' }}</span>
            </div>
          </div>
            <div v-if="trendSummary.sampleCount" class="trend-summary" aria-label="趋势记录摘要">
            <div><strong>{{ trendSummary.sampleCount }}</strong><span>有记录天数</span></div>
            <div><strong>{{ trendSummary.mean }}</strong><span>记录均值</span></div>
            <div><strong>{{ trendSummary.min }}–{{ trendSummary.max }}</strong><span>记录范围</span></div>
            <div><strong>{{ trendSummary.first.value }} → {{ trendSummary.last.value }}</strong><span>{{ formatObservationDate(trendSummary.first.date) }} 至 {{ formatObservationDate(trendSummary.last.date) }}（{{ formatChange(trendSummary.change) }}）</span></div>
          </div>
          <div v-if="resourceStates.trend === 'loading'" class="data-state">正在加载趋势记录…</div>
          <div v-else-if="resourceStates.trend === 'error'" class="data-state is-error">趋势记录暂不可用，请重新加载。</div>
          <div v-else-if="!trendSummary.sampleCount" class="data-empty">暂无所选时间范围内的记录。</div>
          <div v-else ref="trendChartRef" class="chart trend-chart"></div>
        </el-card>

        <el-card class="chart-card" shadow="hover">
          <div class="card-heading">
            <div class="card-title">
              <div class="card-title-main"><LibraryIcon name="assessment" class="icon" /> 量表记录分数</div>
              <p>仅展示已保存的原始记录值，不作常模比较。</p>
            </div>
          </div>
          <div v-if="resourceStates.scores === 'loading'" class="data-state">正在加载量表记录…</div>
          <div v-else-if="resourceStates.scores === 'error'" class="data-state is-error">量表记录暂不可用。</div>
          <div v-else-if="showSdsCard" class="score-card">
            <div class="score-title">SDS抑郁自评量表</div>
            <div class="score-value">本次得分：{{ sdsScoreObj.score ?? '暂无记录' }}<span v-if="sdsScoreObj.score != null">分</span></div>
            <div class="score-desc">此处展示服务器返回的原始记录值，不作诊断、常模比较或临床解释。</div>
          </div>
          <div v-else-if="latestScores.length" ref="scoreChartRef" class="chart"></div>
          <div v-else class="data-empty">暂无量表记录。</div>
        </el-card>

        <el-card class="chart-card" shadow="hover">
          <div class="card-heading">
            <div class="card-title"><div class="card-title-main"><LibraryIcon name="support" class="icon" /> 红色能量积分趋势</div><p>按现有积分记录展示。</p></div>
          </div>
          <div v-if="resourceStates.energy === 'loading'" class="data-state">正在加载积分记录…</div>
          <div v-else-if="resourceStates.energy === 'error'" class="data-state is-error">积分记录暂不可用。</div>
          <div v-else-if="!redEnergy.length" class="data-empty">暂无积分记录。</div>
          <div v-else ref="energyChartRef" class="chart"></div>
        </el-card>

        <el-card class="chart-card" shadow="hover">
          <div class="card-heading">
            <div class="card-title"><div class="card-title-main"><LibraryIcon name="treehole" class="icon" /> 树洞词频</div><p>按词语出现次数排序，点击柱条查看相关内容。</p></div>
          </div>
          <div v-if="resourceStates.words === 'loading'" class="data-state">正在加载词频…</div>
          <div v-else-if="resourceStates.words === 'error'" class="data-state is-error">词频记录暂不可用。</div>
          <div v-else-if="!treeholeWords.length" class="data-empty">暂无词频记录。</div>
          <div v-else ref="wordChartRef" class="chart"></div>
        </el-card>

        <el-card class="chart-card" shadow="hover">
          <div class="card-heading">
            <div class="card-title"><div class="card-title-main"><LibraryIcon name="appointment" class="icon" /> 预约完成度</div><p>预约状态按服务端汇总结果展示。</p></div>
          </div>
          <div v-if="resourceStates.appointments === 'loading'" class="data-state">正在加载预约情况…</div>
          <div v-else-if="resourceStates.appointments === 'error'" class="data-state is-error">预约情况暂不可用。</div>
          <template v-else-if="Number(appointmentStats.total) > 0">
            <div ref="appointmentChartRef" class="chart"></div>
            <div class="appointment-meta">
              <div>总预约：{{ appointmentStats.total ?? 0 }} 个</div>
              <div>已完成：{{ appointmentStats.completed ?? 0 }} 个</div>
              <div>待处理：{{ appointmentStats.pending ?? 0 }} 个</div>
              <div>已取消：{{ appointmentStats.cancelled ?? 0 }} 个</div>
            </div>
          </template>
          <div v-else class="data-empty">暂无预约记录。</div>
        </el-card>
      </div>
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
import { ElMessage, ElAlert, ElButton, ElCard, ElSelect, ElOption, ElDialog } from 'element-plus'
import { summarizeTrend } from '../../services/trendSummary'

const router = useRouter()
const loadError = ref('')
const resourceStates = ref({ trend: 'loading', scores: 'loading', energy: 'loading', words: 'loading', appointments: 'loading' })
const trendSummary = ref(summarizeTrend([], 7))
const latestScores = ref([])
const redEnergy = ref([])
const treeholeWords = ref([])
const appointmentStats = ref({})
const trendChartRef = ref(null)
const scoreChartRef = ref(null)
const energyChartRef = ref(null)
const wordChartRef = ref(null)
const appointmentChartRef = ref(null)
let echarts = null
let chartLibraryPromise = null
let trendChart = null
let scoreChart = null
let energyChart = null
let wordChart = null
let appointmentChart = null
const wordDialogVisible = ref(false)
const currentWord = ref('')
const treeholePosts = ref([])
const trendRange = ref('7d')
const trendLastUpdatedAt = ref('')
const resourceControllers = new Map()

const loadCharts = () => {
  if (!chartLibraryPromise) {
    chartLibraryPromise = import('../../design/charts/basic').then(module => {
      echarts = module
      return module
    }).catch(error => {
      chartLibraryPromise = null
      throw error
    })
  }
  return chartLibraryPromise
}

const sdsScoreObj = computed(() => latestScores.value.find(item => item.name === 'SDS'))
const showSdsCard = computed(() => latestScores.value.length === 1 && !!sdsScoreObj.value)

let unmounted = false
onMounted(() => {
  window.addEventListener('resize', resizeCharts)
  fetchAllData()
})
onBeforeUnmount(() => {
  unmounted = true
  window.removeEventListener('resize', resizeCharts)
  resourceControllers.forEach(controller => controller.abort())
  resourceControllers.clear()
  trendChart && trendChart.dispose(); scoreChart && scoreChart.dispose(); energyChart && energyChart.dispose(); wordChart && wordChart.dispose(); appointmentChart && appointmentChart.dispose()
  trendChart = scoreChart = energyChart = wordChart = appointmentChart = null
})
const resizeCharts = () => { trendChart && trendChart.resize(); scoreChart && scoreChart.resize(); energyChart && energyChart.resize(); wordChart && wordChart.resize(); appointmentChart && appointmentChart.resize() }

const requestResource = async (key, request, apply, initializeChart) => {
  resourceControllers.get(key)?.abort()
  const chartByKey = { trend: trendChart, scores: scoreChart, energy: energyChart, words: wordChart, appointments: appointmentChart }
  chartByKey[key]?.dispose()
  if (key === 'trend') trendChart = null
  if (key === 'scores') scoreChart = null
  if (key === 'energy') energyChart = null
  if (key === 'words') wordChart = null
  if (key === 'appointments') appointmentChart = null
  const controller = new AbortController()
  resourceControllers.set(key, controller)
  resourceStates.value[key] = 'loading'
  try {
    const response = await request(controller.signal)
    if (unmounted || resourceControllers.get(key) !== controller) return
    apply(response.data)
    resourceStates.value[key] = 'ready'
    await nextTick()
    if (!unmounted && resourceControllers.get(key) === controller) await initializeChart()
  } catch {
    if (unmounted || controller.signal.aborted || resourceControllers.get(key) !== controller) return
    resourceStates.value[key] = 'error'
    loadError.value = '部分数据暂不可用；其他内容仍可查看。'
  } finally {
    if (resourceControllers.get(key) === controller) resourceControllers.delete(key)
  }
}

const fetchTrendData = () => {
  const days = Number.parseInt(trendRange.value, 10)
  trendSummary.value = summarizeTrend([], days)
  return requestResource('trend', signal => axios.get('/api/student/dashboard/emotion_trend', { params: { days, limit: days }, signal, timeout: 10000 }), data => {
    trendSummary.value = summarizeTrend(data, days)
    trendLastUpdatedAt.value = new Date().toLocaleTimeString()
  }, async () => {
    if (trendSummary.value.sampleCount) await initTrendChart()
    else { trendChart?.dispose(); trendChart = null }
  })
}

const handleTrendRangeChange = () => { fetchTrendData() }

const fetchAllData = () => {
  loadError.value = ''
  return Promise.all([
    fetchTrendData(),
    requestResource('scores', signal => axios.get('/api/student/dashboard/latest_scores', { signal, timeout: 10000 }), data => { latestScores.value = Array.isArray(data) ? data : [] }, async () => {
      if (latestScores.value.length && !showSdsCard.value) await initScoreChart()
    }),
    requestResource('energy', signal => axios.get('/api/student/dashboard/red_energy', { signal, timeout: 10000 }), data => { redEnergy.value = Array.isArray(data) ? data : [] }, async () => { if (redEnergy.value.length) await initEnergyChart() }),
    requestResource('words', signal => axios.get('/api/student/dashboard/treehole_words', { signal, timeout: 10000 }), data => { treeholeWords.value = Array.isArray(data) ? data : [] }, async () => { if (treeholeWords.value.length) await initWordChart() }),
    requestResource('appointments', signal => axios.get('/api/student/dashboard/appointment_stats', { signal, timeout: 10000 }), data => { appointmentStats.value = data || {} }, async () => { if (Number(appointmentStats.value.total) > 0) await initAppointmentChart() }),
  ])
}

const retryDashboard = () => { fetchAllData() }
const formatChange = value => value === null ? '—' : `${value > 0 ? '+' : ''}${value}`
const formatObservationDate = value => value.slice(5).replace('-', '/')
const buildTrendOption = () => {
  const points = trendSummary.value.points
  const labelInterval = Math.max(0, Math.ceil(points.length / 8) - 1)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', snap: true },
      formatter: items => {
        const item = Array.isArray(items) ? items[0] : null
        return item?.value === null || item?.value === undefined
          ? `${item?.axisValue ?? ''}<br/>暂无记录`
          : `${item.axisValue}<br/>记录值：${item.value}`
      },
    },
    grid: { left: 44, right: 20, bottom: 34, top: 18, containLabel: true },
    xAxis: {
      type: 'category', data: points.map(point => point.date), boundaryGap: false,
      axisLabel: { interval: labelInterval, hideOverlap: true, formatter: value => value.slice(5).replace('-', '/') },
      axisTick: { alignWithLabel: true },
    },
    yAxis: { type: 'value', name: '记录值', nameGap: 12, min: 0, max: 100, interval: 20, splitLine: { show: true } },
    series: [{
      type: 'line',
      smooth: false,
      connectNulls: false,
      showSymbol: true,
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: { color: businessColor('data-primary') },
      data: points.map(point => point.value),
    }]
  }
}

const initTrendChart = async () => {
  await loadCharts()
  if (unmounted || !trendChartRef.value) return
  trendChart?.dispose()
  trendChart = echarts.init(trendChartRef.value, 'xinyu-business')
  setLibraryChartOption(trendChart, buildTrendOption(), true)
  trendChart.on('click', () => router.push('/student/report'))
}
const initScoreChart = async () => {
  await loadCharts()
  if (unmounted || !scoreChartRef.value) return
  scoreChart?.dispose()
  scoreChart = echarts.init(scoreChartRef.value, 'xinyu-business')
  setLibraryChartOption(scoreChart, {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: latestScores.value.map(item => item.name) },
    yAxis: { type: 'value' },
    series: [{ name: '已保存分数', type: 'bar', data: latestScores.value.map(item => item.score) }],
  })
}
const initEnergyChart = async () => {
  await loadCharts()
  if (unmounted || !energyChartRef.value) return
  energyChart?.dispose()
  energyChart = echarts.init(energyChartRef.value, 'xinyu-business')
  setLibraryChartOption(energyChart, { tooltip: { trigger: 'axis' }, grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true }, xAxis: { type: 'category', boundaryGap: false, data: redEnergy.value.map(i => i.date) }, yAxis: { type: 'value' }, series: [{ type: 'line', smooth: false, symbol: 'none', itemStyle: { color: businessColor('data-risk-high') }, data: redEnergy.value.map(i => i.score) }] })
}
const initWordChart = async () => {
  await loadCharts()
  if (unmounted || !wordChartRef.value) return
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
const initAppointmentChart = async () => {
  await loadCharts()
  if (unmounted || !appointmentChartRef.value) return
  const { completed = 0, pending = 0, cancelled = 0, total = 0 } = appointmentStats.value
  appointmentChart?.dispose()
  appointmentChart = echarts.init(appointmentChartRef.value, 'xinyu-business')
  setLibraryChartOption(appointmentChart, { tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['50%', '70%'], center: ['50%', '45%'], data: [{ value: completed, name: '已完成' }, { value: pending, name: '待处理' }, { value: cancelled, name: '已取消' }] }], graphic: [{ type: 'text', left: 'center', top: '44%', style: { text: `${total}`, fill: businessColor('text-primary'), fontSize: 24, fontWeight: 700 } }] })
}
const cancelNextAppointment = async () => {
  const next = appointmentStats.value?.next_appointment
  if (!next?.id) return
  try { await axios.post(`/api/student/appointments/${next.id}/cancel`); ElMessage.success('已取消下一次预约'); await fetchAllData() } catch { ElMessage.error('取消预约失败') }
}
const goModifyAppointment = () => router.push('/student/appointments')
</script>
<style scoped>
.dashboard-container { min-height: 100%; padding-bottom: 20px; }
.dashboard-content { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; min-width: 0; }
.dashboard-intro { display: grid; grid-template-columns: minmax(200px, .75fr) minmax(320px, 1.25fr); align-items: center; gap: 24px; padding: 24px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); }
.dashboard-intro > *, .section-heading > * { min-width: 0; }
.dashboard-intro h2, .section-heading h2 { margin: 0; color: var(--text-primary); font-size: 20px; }
.dashboard-intro p, .section-heading p { margin: 8px 0 0; color: var(--text-secondary); line-height: 1.6; }
.action-links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; min-width: 0; }
.action-links :deep(.dashboard-action) { width: 100%; min-width: 0; min-height: 44px; margin: 0; padding-inline: 10px; justify-content: center; white-space: normal; }
.action-links :deep(.dashboard-action + .dashboard-action) { margin-left: 0; }
.action-links :deep(.dashboard-action .library-icon) { flex: 0 0 auto; }
.next-appointment-card { border-left: 3px solid var(--accent-sage); }
.next-appointment-copy { display: flex; flex-wrap: wrap; gap: 10px 20px; color: var(--text-primary); }
.insights-section { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; min-width: 0; }
.section-heading { display: flex; justify-content: space-between; gap: 16px; }
.page-title { font-size: 24px; color: var(--text-primary); margin-bottom: 24px; font-weight: 600; }
.insight-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-auto-rows: minmax(330px, auto); gap: 16px; min-width: 0; }
.chart-card { height: 100%; min-width: 0; border-radius: var(--radius-lg); border: 1px solid var(--border); box-shadow: 0 4px 6px -1px color-mix(in srgb, var(--gray-900) 5%, transparent), 0 2px 4px -1px color-mix(in srgb, var(--gray-900) 3%, transparent); }
.chart-card :deep(.el-card__body) { display: flex; flex-direction: column; height: 100%; min-height: 0; padding: 20px; }
.trend-card { grid-column: 1 / -1; }
.card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.card-title { min-width: 0; }
.card-title-main { display: flex; align-items: center; gap: 8px; color: var(--text-primary); font-size: 16px; font-weight: 600; line-height: 1.35; }
.card-title p { margin: 5px 0 0 28px; color: var(--text-secondary); font-size: 13px; line-height: 1.45; }
.trend-header { align-items: flex-start; gap: 12px; }
.trend-tools { display: inline-flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.trend-meta { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.card-title-main .icon { flex: 0 0 auto; font-size: 20px; }
.trend-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 0 0 6px; }
.trend-summary > div { display: grid; gap: 3px; min-width: 0; padding: 8px 10px; background: var(--surface-subtle); border-radius: var(--radius-md); }
.trend-summary strong { color: var(--text-primary); font-size: 16px; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.trend-summary span { color: var(--text-secondary); font-size: 12px; line-height: 1.3; }
.chart { width: 100%; min-width: 0; height: 240px; flex: 1 1 auto; }
.trend-chart { min-height: 190px; }
.data-state, .data-empty { display: grid; place-items: center; flex: 1 1 auto; min-height: 170px; color: var(--text-secondary); text-align: center; line-height: 1.6; }
.data-state.is-error { color: var(--danger-text); }
.score-card { min-height: 230px; display: flex; flex-direction: column; justify-content: space-between; gap: 10px; flex: 1 1 auto; }
.score-title { font-size: 16px; color: var(--text-primary); font-weight: 600; }
.score-value { font-size: 15px; color: var(--text-primary); }
.score-desc { background: var(--surface-subtle); color: var(--text-secondary); font-size: 13px; line-height: 1.6; border-radius: var(--radius-md); padding: 8px 10px; }
.treehole-list { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.treehole-item { background: var(--surface-subtle); padding: 16px; border-radius: var(--radius-md); }
.treehole-item .content { color: var(--text-primary); line-height: 1.5; font-size: 14px; margin: 0; font-style: italic; }
.appointment-meta { color: var(--text-secondary); font-size: 13px; line-height: 1.7; margin-top: -4px; }
.next-appointment-card :deep(.el-card__body) { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.appointment-actions { display: flex; flex-wrap: wrap; gap: 8px; }
@media (max-width: 860px) {
  .dashboard-intro { grid-template-columns: minmax(0, 1fr); padding: 18px; min-width: 0; }
  .insight-grid { grid-template-columns: minmax(0, 1fr); grid-auto-rows: minmax(310px, auto); }
  .trend-card { grid-column: auto; }
}
@media (max-width: 600px) {
  .insight-grid { grid-auto-rows: minmax(300px, auto); }
  .chart-card :deep(.el-card__body) { padding: 16px; }
  .trend-header { flex-direction: column; }
  .trend-header > *, .trend-tools { min-width: 0; max-width: 100%; }
  .trend-tools { width: 100%; justify-content: space-between; }
  .trend-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .next-appointment-card :deep(.el-card__body) { display: grid; gap: 12px; }
  .appointment-actions { flex-wrap: wrap; }
  .next-appointment-copy, .appointment-actions { min-width: 0; }
}
</style>
