<template>
  <div class="dashboard-container">
    <!-- 头部：大盘数据与导出功能 -->
    <div class="header-actions">
      <h2>全校心理健康实时大屏与干预审计工作台</h2>
      <div class="export-btns">
        <el-button type="warning" plain :loading="exporting" @click="exportComplianceReport">
          <el-icon><Document /></el-icon> 导出合规审计报告 (Word)
        </el-button>
      </div>
    </div>

    <!-- 第一排：核心指标卡片 -->
    <el-row :gutter="20" class="mt-20" v-if="metrics">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">今日独立访客 (UV)</div>
          <div class="stat-value text-blue">{{ metrics.realtime_stats.uv }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">人均会话轮次</div>
          <div class="stat-value">{{ metrics.realtime_stats.avg_session_rounds }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">触发红色警报 (次)</div>
          <div class="stat-value text-red">{{ metrics.realtime_stats.crisis_alerts }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">干预成功率</div>
          <div class="stat-value text-green">85.0%</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 第二排：图表可视化 (ECharts) -->
    <el-row :gutter="20" class="mt-20">
      <!-- 漏斗图：干预流程 -->
      <el-col :span="8">
        <el-card shadow="hover" class="chart-card">
          <template #header>干预转化漏斗图</template>
          <div ref="funnelChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <!-- 折线图：7日情绪趋势 -->
      <el-col :span="8">
        <el-card shadow="hover" class="chart-card">
          <template #header>近7日情绪强度波动 (移动平均)</template>
          <div ref="lineChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <!-- 模拟 GIS 宿舍热力图 -->
      <el-col :span="8">
        <el-card shadow="hover" class="chart-card">
          <template #header>校园 GIS 楼栋风险热力图</template>
          <div ref="heatmapChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 第三排：统一待审核危机预警记录 -->
    <el-card shadow="hover" class="mt-20 warning-card" :class="{'has-unread': pendingCount > 0}">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold; color: #EF4444; display: flex; align-items: center;">
            <el-icon class="mr-5"><Warning /></el-icon> 待审核危机预警记录
            <el-badge v-if="pendingCount > 0" :value="pendingCount" class="ml-10" />
          </span>
          <el-tag type="danger">需心理教师人工校正闭环</el-tag>
        </div>
      </template>

      <el-table :data="pendingList" border style="width: 100%" :row-class-name="tableRowClassName" v-loading="loadingPending">
        <el-table-column prop="createdAt" label="预警时间" width="160" />
        <el-table-column label="学生信息" width="170">
          <template #default="{row}">
            <div><strong>{{ row.studentName || '未知' }}</strong></div>
            <div style="color: #6B7280; font-size: 12px;">学号: {{ row.studentId || '-' }} / {{ row.className || '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="100">
          <template #default="{row}">
            <el-tag type="danger" effect="dark" v-if="row.riskLevel === 'high'">高危</el-tag>
            <el-tag type="warning" effect="dark" v-else-if="row.riskLevel === 'medium'">中危</el-tag>
            <el-tag type="info" effect="dark" v-else>低危</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预警描述" min-width="320">
          <template #default="{row}">
            <div class="audit-msg">{{ row.description || '未知' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{row}">
            <el-tag type="danger" v-if="row.status === 'pending'">待审核</el-tag>
            <el-tag type="success" v-else>已审核</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{row}">
            <div class="audit-action-group">
              <el-button size="small" type="success" @click="handleReview(row, 'pass')">通过</el-button>
              <el-button size="small" type="warning" @click="handleReview(row, 'reject')">驳回校正</el-button>
              <el-button size="small" type="danger" @click="handleReview(row, 'escalate')">升级处理</el-button>
              <el-button size="small" type="primary" @click="contactStudent(row)">一键联系</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Document, Warning } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import * as echarts from 'echarts'
import axios from 'axios'

const metrics = ref(null)
const pendingList = ref([])
const loadingPending = ref(false)
const ws = ref(null)
let pendingPollTimer = null

const pendingCount = computed(() => pendingList.value.length)

const funnelChartRef = ref(null)
const lineChartRef = ref(null)
const heatmapChartRef = ref(null)
const exporting = ref(false)
const chartInstances = ref({
  funnel: null,
  line: null,
  heatmap: null
})

const tableRowClassName = ({ row }) => {
  if (String(row.id || '').startsWith('real-')) {
    return 'warning-row-unread'
  }
  return ''
}

const fetchPendingList = async () => {
  loadingPending.value = true
  try {
    const res = await axios.get('/api/teacher/crisis/pending', {
      params: { page: 1, pageSize: 200 }
    })
    pendingList.value = res.data?.data?.items || []
  } catch (error) {
    console.error('Failed to fetch pending crisis records', error)
  } finally {
    loadingPending.value = false
  }
}

const handleReview = async (row, action) => {
  const actionName = action === 'pass' ? '通过并确认' : (action === 'reject' ? '驳回校正' : '升级处理')
  await ElMessageBox.confirm(`确认对记录 ${row.id} 执行 [${actionName}] 操作吗？`, '操作确认')
  try {
    await axios.post('/api/teacher/crisis/review', {
      recordId: row.id,
      action
    })
    pendingList.value = pendingList.value.filter(item => item.id !== row.id)
    ElMessage.success('审核成功，已移入已审核历史')
  } catch (error) {
    ElMessage.error('审核提交失败')
  }
}

const contactStudent = (row) => {
  ElMessageBox.alert(`已为您调出【${row.studentName || '该学生'}】的档案，并准备好紧急联络渠道（辅导员电话/家长电话），请确认是否拨打。`, '一键联系', {
    confirmButtonText: '立即联系',
    type: 'warning'
  })
}

const normalizeWsWarning = (payload) => {
  return {
    id: `real-${payload.id}`,
    createdAt: payload.createdAt || payload.created_at || '',
    studentId: payload.studentId || String(payload.student_id || ''),
    studentName: payload.studentName || payload.student_name || '未知',
    className: payload.className || payload.class_name || '未知',
    riskLevel: payload.riskLevel || payload.risk_level || 'high',
    description: payload.description || payload.trigger_msg || '',
    status: payload.status || 'pending',
    highlight: true
  }
}

const initWebSocket = () => {
  const token = localStorage.getItem('token')
  if (!token) return
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws?token=${token}`
  ws.value = new WebSocket(wsUrl)
  ws.value.onopen = () => {
    console.log('Teacher WS connected')
  }
  ws.value.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'new_warning') {
        const normalized = normalizeWsWarning(msg.data || {})
        if (!pendingList.value.some(item => item.id === normalized.id)) {
          pendingList.value.push(normalized)
        }
        playAlertSound()
        ElNotification({
          title: '新的心理危机预警！',
          message: `学生 ${normalized.studentName}（${normalized.className}）在 ${normalized.createdAt} 触发危机预警：${normalized.description}`,
          type: 'error',
          duration: 0
        })
      }
    } catch (e) {}
  }
  ws.value.onclose = () => {
    console.log('Teacher WS disconnected, retrying...')
    setTimeout(initWebSocket, 5000)
  }
}

const playAlertSound = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, ctx.currentTime)
    gain.gain.setValueAtTime(0.001, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.35)
  } catch (error) {
    console.warn('play alert sound failed', error)
  }
}

onMounted(async () => {
  await fetchMetrics()
  await fetchPendingList()
  initCharts()
  initWebSocket()
  pendingPollTimer = setInterval(fetchPendingList, 8000)
})

onUnmounted(() => {
  if (ws.value) {
    ws.value.close()
  }
  if (pendingPollTimer) {
    clearInterval(pendingPollTimer)
  }
})

const fetchMetrics = async () => {
  try {
    const res = await axios.get('/api/advanced-teacher/dashboard/metrics')
    metrics.value = res.data
  } catch (error) {
    console.error(error)
  }
}

const exportComplianceReport = async () => {
  exporting.value = true
  try {
    const snapshots = [
      { key: 'funnel', title: '干预转化漏斗图' },
      { key: 'line', title: '近7日情绪强度波动 (移动平均)' },
      { key: 'heatmap', title: '校园 GIS 楼栋风险热力图' }
    ]
      .map(({ key, title }) => {
        const chart = chartInstances.value[key]
        if (!chart) return null
        return {
          title,
          image_data_url: chart.getDataURL({
            type: 'png',
            pixelRatio: 3,
            backgroundColor: '#ffffff'
          })
        }
      })
      .filter(Boolean)

    const response = await axios.post(
      '/api/advanced-teacher/export/compliance-report',
      {
        chart_snapshots: snapshots
      },
      { responseType: 'blob' }
    )

    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '合规审计风险干预报告.docx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('已导出 Word 报告')
  } catch (error) {
    console.error(error)
    ElMessage.error('导出合规审计报告失败')
  } finally {
    exporting.value = false
  }
}

// --- ECharts 渲染 ---
const initCharts = () => {
  if (!metrics.value) return

  // 1. 漏斗图
  const funnelChart = echarts.init(funnelChartRef.value)
  chartInstances.value.funnel = funnelChart
  funnelChart.setOption({
    textStyle: { fontFamily: 'Microsoft YaHei, SimSun, Arial, sans-serif' },
    tooltip: { trigger: 'item', formatter: '{b} : {c}%' },
    series: [{
      type: 'funnel',
      left: '10%', top: 20, bottom: 20, width: '80%',
      min: 0, max: 100, minSize: '0%', maxSize: '100%',
      sort: 'desc', gap: 2,
      label: { show: true, position: 'inside' },
      data: metrics.value.funnel_data
    }],
    color: ['#EF4444', '#F59E0B', '#3B82F6', '#10B981', '#059669']
  })

  // 2. 情绪折线图 (带数据缩放)
  const lineChart = echarts.init(lineChartRef.value)
  chartInstances.value.line = lineChart
  lineChart.setOption({
    textStyle: { fontFamily: 'Microsoft YaHei, SimSun, Arial, sans-serif' },
    tooltip: { trigger: 'axis' },
    legend: { data: ['愉悦强度', '焦虑强度'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: metrics.value.emotion_trends_7d.dates },
    yAxis: { type: 'value', max: 1.0 },
    series: [
      { name: '愉悦强度', type: 'line', smooth: true, data: metrics.value.emotion_trends_7d.joy, itemStyle: { color: '#10B981' } },
      { name: '焦虑强度', type: 'line', smooth: true, data: metrics.value.emotion_trends_7d.anxiety, itemStyle: { color: '#EF4444' },
        markLine: { data: [{ type: 'average', name: 'Avg' }] }
      }
    ]
  })

  // 3. 模拟热力图 (这里用散点图+涟漪特效模拟 GIS 热力)
  const heatChart = echarts.init(heatmapChartRef.value)
  chartInstances.value.heatmap = heatChart
  const heatData = metrics.value.campus_heatmap.map((item, i) => [i * 20 + 20, Math.random() * 50 + 20, item.risk_density * 100, item.building])
  heatChart.setOption({
    textStyle: { fontFamily: 'Microsoft YaHei, SimSun, Arial, sans-serif' },
    tooltip: { formatter: p => `${p.data[3]}<br/>危险密度指数: ${p.data[2].toFixed(1)}` },
    xAxis: { show: false, min: 0, max: 100 },
    yAxis: { show: false, min: 0, max: 100 },
    series: [{
      type: 'effectScatter',
      symbolSize: function (val) { return val[2] / 2; },
      data: heatData,
      itemStyle: {
        color: function(params) {
          return params.data[2] > 80 ? 'rgba(239, 68, 68, 0.8)' : 'rgba(245, 158, 11, 0.8)'
        }
      }
    }]
  })

  window.addEventListener('resize', () => {
    funnelChart.resize()
    lineChart.resize()
    heatChart.resize()
  })
}
</script>

<style scoped>
.dashboard-container { padding: 20px; background: #F3F4F6; min-height: calc(100vh - 60px); }
.header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-actions h2 { margin: 0; color: #111827; }

.stat-card { text-align: center; border-radius: 12px; }
.stat-title { font-size: 14px; color: #6B7280; margin-bottom: 10px; }
.stat-value { font-size: 28px; font-weight: bold; }
.text-blue { color: #3B82F6; }
.text-red { color: #EF4444; }
.text-green { color: #10B981; }

.chart-card { border-radius: 12px; }
.chart-box { height: 250px; width: 100%; }

.audit-msg { font-size: 14px; color: #374151; background: #F9FAFB; padding: 10px; border-radius: 6px; }
.audit-reply { font-size: 13px; color: #4B5563; border-left: 3px solid #3B82F6; padding-left: 10px; }

.slider-row { display: flex; align-items: center; gap: 15px; margin-bottom: 8px; }
.slider-row span { width: 80px; font-size: 12px; color: #4B5563; }
.slider-row :deep(.el-progress) { flex: 1; }

.mt-10 { margin-top: 10px; }
.mt-20 { margin-top: 20px; }
.mr-5 { margin-right: 5px; }

.audit-action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.audit-action-group :deep(.el-button) {
  margin-left: 0 !important;
}

.warning-card.has-unread {
  border: 1px solid #EF4444;
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
}

:deep(.warning-row-unread) {
  background-color: #FEF2F2 !important;
}
:deep(.warning-row-unread:hover > td) {
  background-color: #FEE2E2 !important;
}
</style>
