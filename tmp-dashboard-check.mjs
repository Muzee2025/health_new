
import { ref, onMounted, nextTick, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(true)

// Data refs
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

// Dialog
const wordDialogVisible = ref(false)
const currentWord = ref('')
const treeholePosts = ref([])
const positiveWords = new Set(['寮€蹇?, '鏈熷緟', '鏀炬澗', '甯屾湜', '鑷俊', '骞抽潤', '婊¤冻', '鎰熸縺'])
const negativeWords = new Set(['鐒﹁檻', '澶辩湢', '鍘嬪姏', '宕╂簝', '闅捐繃', '鎶戦儊', '鎯冲摥', '杩疯尗', '瀛ょ嫭'])

const sdsScoreObj = computed(() => latestScores.value.find(item => item.name === 'SDS'))
const showSdsCard = computed(() => latestScores.value.length === 1 && !!sdsScoreObj.value)
const sdsScore = computed(() => Number(sdsScoreObj.value?.score || 0))
const sdsNorm = computed(() => Number(sdsScoreObj.value?.norm || 42))
const sdsLevel = computed(() => {
  if (sdsScore.value >= 73) return '閲嶅害'
  if (sdsScore.value >= 63) return '涓害'
  if (sdsScore.value >= 53) return '杞诲害'
  return '鏃犳槑鏄?
})
const sdsAdvice = computed(() => {
  if (sdsScore.value >= 63) return '寤鸿灏藉揩棰勭害蹇冪悊鍜ㄨ锛屽苟鍑忓皯杩炵画楂樺帇瀛︿範鏃堕暱銆?
  if (sdsScore.value >= 53) return '寤鸿澶氳繘琛屾埛澶栨椿鍔紝蹇呰鏃跺彲棰勭害鍜ㄨ銆?
  return '寤鸿淇濇寔瑙勫緥浣滄伅骞舵寔缁叧娉ㄦ儏缁尝鍔ㄣ€?
})
const sdsColor = computed(() => {
  if (sdsScore.value >= 73) return '#DC2626'
  if (sdsScore.value >= 63) return '#F59E0B'
  if (sdsScore.value >= 53) return '#FB7185'
  return '#10B981'
})

onMounted(async () => {
  await fetchAllData()
  
  loading.value = false
  loading.value = false
  nextTick(() => {
    initCharts()
  
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  if (trendChart) trendChart.dispose()
  if (scoreChart) scoreChart.dispose()
  if (energyChart) energyChart.dispose()
  if (wordChart) wordChart.dispose()
  if (appointmentChart) appointmentChart.dispose()
})

const resizeCharts = () => {
  if (trendChart) trendChart.resize()
  if (scoreChart) scoreChart.resize()
  if (energyChart) energyChart.resize()
  if (wordChart) wordChart.resize()
  if (appointmentChart) appointmentChart.resize()
}

const fetchAllData = async () => {
  let useMockData = false
  try {
    const [trendRes, scoresRes, energyRes, wordsRes, aptRes] = await Promise.all([
      axios.get('/api/student/dashboard/emotion_trend'),
      axios.get('/api/student/dashboard/latest_scores'),
      axios.get('/api/student/dashboard/red_energy'),
      axios.get('/api/student/dashboard/treehole_words'),
      axios.get('/api/student/dashboard/appointment_stats')
    ])
    
    emotionTrend.value = trendRes.data
    latestScores.value = scoresRes.data
    redEnergy.value = energyRes.data
    treeholeWords.value = wordsRes.data
    appointmentStats.value = aptRes.data

    if (emotionTrend.value.length === 0) {
      useMockData = true
    }
  } catch (error) {
    console.error('Failed to fetch dashboard data', error)
    useMockData = true
  }

  if (useMockData) {
    console.warn("婕旂ず鏁版嵁妯″紡锛屾帴鍏ョ湡瀹炴暟鎹悗鑷姩鏇存柊")
    
    // 鎯呯华瓒嬪娍鎶樼嚎鍥?    emotionTrend.value = [
      { date: '10-01', index: 65 },
      { date: '10-02', index: 70 },
      { date: '10-03', index: 62 },
      { date: '10-04', index: 58 },
      { date: '10-05', index: 72 }
    ]

    // 閲忚〃寰楀垎瀵规瘮鏌辩姸鍥?    latestScores.value = [
      { name: 'SDS', score: 55, norm: 41 },
      { name: 'SAS', score: 48, norm: 40 },
      { name: '蹇冪悊骞撮緞', score: 28, norm: 45 }
    ]

    redEnergy.value = [
      { date: '10-01', score: 5 },
      { date: '10-02', score: 8 },
      { date: '10-03', score: 6 },
      { date: '10-04', score: 10 },
      { date: '10-05', score: 7 },
      { date: '10-06', score: 9 },
      { date: '10-07', score: 12 }
    ]

    treeholeWords.value = [
      { word: '鐒﹁檻', count: 5 },
      { word: '澶辩湢', count: 3 },
      { word: '寮€蹇?, count: 2 },
      { word: '鍘嬪姏', count: 4 },
      { word: '杩疯尗', count: 3 }
    ]

    // 棰勭害瀹屾垚搴︾幆褰㈠浘
    appointmentStats.value = {
      completed: 3,
      pending: 2,
      cancelled: 0,
      total: 5
    }
  }
}

const initCharts = () => {
  if (trendChartRef.value) initTrendChart()
  if (scoreChartRef.value) initScoreChart()
  if (energyChartRef.value) initEnergyChart()
  if (wordChartRef.value) initWordChart()
  if (appointmentChartRef.value) initAppointmentChart()
}

const initTrendChart = () => {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const data = params[0].data
        const events = (data.events || []).join('锛?)
        return `${params[0].name}<br/>${params[0].marker} 鎯呯华鎸囨暟: <b>${data.value}</b><br/><span style="font-size:12px;color:#666;">${events || '鏆傛棤鍏宠仈浜嬩欢'}</span>`
      }
    },
    grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: emotionTrend.value.map(item => item.date),
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280' }
    },
    yAxis: {
      type: 'value',
      min: 30,
      max: 80,
      splitLine: { lineStyle: { type: 'dashed', color: '#F3F4F6' } },
      axisLabel: { color: '#6B7280' },
      name: '60鍩哄噯',
      nameTextStyle: { color: '#9CA3AF' },
      nameLocation: 'middle',
      nameGap: 38
    },
    series: [
      {
        type: 'line',
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: '#3B82F6' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ])
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0)' }
          ])
        },
        data: emotionTrend.value.map(item => ({
          value: item.index,
          test_id: item.test_id,
          events: item.events || []
        })),
        markLine: {
          silent: true,
          lineStyle: { color: '#10B981', type: 'dashed' },
          label: { position: 'end', formatter: '鍋ュ悍绾?(80)' },
          data: [{ yAxis: 80 }]
        },
        markPoint: {
          symbolSize: 44,
          itemStyle: { color: '#EF4444' },
          label: {
            formatter: (params) => params.data?.name || '',
            color: '#334155',
            fontSize: 10
          },
          data: (() => {
            if (!emotionTrend.value.length) return []
            const sorted = [...emotionTrend.value].sort((a, b) => a.index - b.index)
            const low = sorted[0]
            const high = sorted[sorted.length - 1]
            return [
              { coord: [low.date, low.index], value: low.index, name: '鏈€浣庣偣', events: low.events || [] },
              { coord: [high.date, high.index], value: high.index, name: '鏈€楂樼偣', events: high.events || [] }
            ]
          })()
        }
      }
    ],
    graphic: [
      {
        type: 'text',
        right: 10,
        top: 6,
        style: { text: '鎯呯华鐘舵€佽秺濂?, fill: '#16A34A', fontSize: 12 }
      },
      {
        type: 'text',
        right: 10,
        bottom: 6,
        style: { text: '鎯呯华鐘舵€佽秺宸?, fill: '#DC2626', fontSize: 12 }
      }
    ]
  }
  
  trendChart.setOption(option)
  trendChart.on('click', (params) => {
    router.push('/student/report')
  })
}

const initScoreChart = () => {
  if (!scoreChartRef.value) return
  scoreChart = echarts.init(scoreChartRef.value)
  
  const names = latestScores.value.map(item => item.name)
  const scores = latestScores.value.map(item => item.score)
  const norms = latestScores.value.map(item => item.norm)
  
  const option = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['鎴戠殑寰楀垎', '甯告ā骞冲潎'], bottom: 0, itemWidth: 10, itemHeight: 10 },
    grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280' }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#F3F4F6' } },
      axisLabel: { color: '#6B7280' }
    },
    series: [
      {
        name: '鎴戠殑寰楀垎',
        type: 'bar',
        data: scores,
        itemStyle: { color: '#8B5CF6', borderRadius: [4, 4, 0, 0] },
        barWidth: '25%'
      },
      {
        name: '甯告ā骞冲潎',
        type: 'bar',
        data: norms,
        itemStyle: { color: '#D1D5DB', borderRadius: [4, 4, 0, 0] },
        barWidth: '25%'
      }
    ]
  }
  scoreChart.setOption(option)
}

const initEnergyChart = () => {
  if (!energyChartRef.value) return
  energyChart = echarts.init(energyChartRef.value)
  
  const option = {
    tooltip: { trigger: 'axis' },
    grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: redEnergy.value.map(item => item.date),
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280' }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#F3F4F6' } },
      axisLabel: { color: '#6B7280' }
    },
    series: [
      {
        type: 'line',
        smooth: true,
        symbol: 'none',
        itemStyle: { color: '#EF4444' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(239, 68, 68, 0.5)' },
            { offset: 1, color: 'rgba(239, 68, 68, 0.05)' }
          ])
        },
        data: redEnergy.value.map(item => item.score)
      }
    ]
  }
  energyChart.setOption(option)
}

const initWordChart = () => {
  if (!wordChartRef.value) return
  wordChart = echarts.init(wordChartRef.value)
  
  const words = treeholeWords.value.map(item => ({
    name: item.word,
    value: item.count,
    textStyle: {
      color: positiveWords.has(item.word)
        ? '#16A34A'
        : negativeWords.has(item.word)
          ? '#475569'
          : '#64748B'
    }
  }))
  
  const option = {
    tooltip: { trigger: 'item', formatter: (p) => `${p.name}锛?{p.value}` },
    series: [
      {
        type: 'wordCloud',
        shape: 'circle',
        left: 'center',
        top: 'center',
        width: '100%',
        height: '100%',
        sizeRange: [16, 40],
        rotationRange: [-20, 20],
        gridSize: 8,
        drawOutOfBound: false,
        textStyle: { fontWeight: 'bold' },
        data: words
      }
    ]
  }
  wordChart.setOption(option)
  
  wordChart.on('click', async (params) => {
    const word = params.name
    currentWord.value = word
    try {
      const res = await axios.get(`/api/student/treehole/search_by_word?word=${encodeURIComponent(word)}`)
      treeholePosts.value = res.data
      wordDialogVisible.value = true
    } catch (error) {
      ElMessage.error('鑾峰彇鏍戞礊璇︽儏澶辫触')
    }
  })
}

const initAppointmentChart = () => {
  if (!appointmentChartRef.value) return
  appointmentChart = echarts.init(appointmentChartRef.value)
  
  const { completed, pending, cancelled, total } = appointmentStats.value
  
  const data = total > 0 ? [
    { value: completed, name: '宸插畬鎴?, itemStyle: { color: '#10B981' } },
    { value: pending, name: '寰呭鐞?, itemStyle: { color: '#F59E0B' } },
    { value: cancelled, name: '宸插彇娑?, itemStyle: { color: '#9CA3AF' } }
  ] : [{ value: 0, name: '鏆傛棤棰勭害', itemStyle: { color: '#E5E7EB' } }]
  
  const option = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10 },
    series: [
      {
        type: 'pie',
        radius: ['50%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        label: { show: false },
        labelLine: { show: false },
        data: data,
        emphasis: { scale: true }
      }
    ],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '39%',
        style: { text: `${total || 0}`, textAlign: 'center', fill: '#111827', fontSize: 24, fontWeight: 700 }
      },
      {
        type: 'text',
        left: 'center',
        top: '52%',
        style: { text: '鎬婚绾?, textAlign: 'center', fill: '#6B7280', fontSize: 12 }
      }
    ]
  }
  appointmentChart.setOption(option)
}

const cancelNextAppointment = async () => {
  const next = appointmentStats.value?.next_appointment
  if (!next?.id) return
  try {
    await axios.post(`/api/student/appointments/${next.id}/cancel`)
    ElMessage.success('宸插彇娑堜笅涓€娆￠绾?)
    await fetchAllData()
    nextTick(() => initAppointmentChart())
  } catch (error) {
    ElMessage.error('鍙栨秷棰勭害澶辫触')
  }
}

const goModifyAppointment = () => {
  router.push('/student/appointments')
}


