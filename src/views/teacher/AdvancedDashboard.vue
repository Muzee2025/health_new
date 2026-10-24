<template>
  <div class="dashboard-container business-page">
    <div class="header-actions business-page__header business-actions">
      <div class="dashboard-actions">
        <el-button plain @click="$router.push('/teacher/support')">求助与跟进工作区</el-button>
        <el-button type="warning" plain :loading="exporting" @click="exportComplianceReport">
          <el-icon><LibraryIcon name="report" /></el-icon> 导出合规审计报告（Word）
        </el-button>
      </div>
    </div>

    <el-alert :title="metrics?.data_status === 'empty' ? '当前尚未分配学生，请由学校完成分配。' : '仅统计明确分配给您的学生'" type="info" :closable="false" show-icon />
    <el-alert v-if="metricsError" title="统计数据加载失败，请刷新后重试。" type="error" :closable="false" show-icon class="mt-20">
      <el-button text type="primary" @click="fetchMetrics">重新加载统计</el-button>
    </el-alert>
    <div v-if="!metrics && !metricsError" class="loading-note" role="status">正在加载统计数据…</div>

    <el-card shadow="never" class="mt-20 warning-card business-card" :class="{'has-unread': pendingCount > 0}">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold; color: var(--danger-text); display: flex; align-items: center;">
            <el-icon class="mr-5"><LibraryIcon name="alert"  /></el-icon> 待审核危机预警记录
            <el-badge v-if="pendingCount > 0" :value="pendingCount" class="ml-10" />
          </span>
          <el-tag type="danger">需心理教师人工校正闭环</el-tag>
        </div>
      </template>

      <el-alert v-if="pendingLoadError" type="error" :closable="false" title="待审核预警暂时无法加载，当前列表可能不完整。">
        <el-button text type="primary" @click="fetchPendingList">重新加载预警</el-button>
      </el-alert>
      <div class="business-table-wrap">
      <el-table :data="pendingList" border style="width: 100%" :row-class-name="tableRowClassName" v-loading="loadingPending" empty-text="当前没有待审核预警。">
        <el-table-column prop="createdAt" label="预警时间" width="160" />
        <el-table-column label="学生信息" width="170">
          <template #default="{row}">
            <div><strong>{{ row.studentName || '未知' }}</strong></div>
            <div style="color: var(--text-secondary); font-size: 12px;">学号: {{ row.studentId || '-' }} / {{ row.className || '-' }}</div>
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
        <el-table-column label="操作" width="360">
          <template #default="{row}">
            <div class="audit-action-group">
              <el-button size="small" type="success" @click="handleReview(row, 'pass')">通过</el-button>
              <el-button size="small" type="warning" @click="handleReview(row, 'reject')">驳回校正</el-button>
              <el-button size="small" type="danger" @click="handleReview(row, 'escalate')">升级处理</el-button>
              <el-button size="small" type="primary" @click="contactStudent(row)">联络说明</el-button>
              <el-button size="small" plain @click="$router.push('/teacher/support')">进入跟进</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </el-card>

    <el-card shadow="never" class="mt-20 review-history-card business-card">
      <template #header>
        <div class="history-heading"><strong>预警审核历史</strong><el-button text @click="fetchReviewHistory" :loading="loadingReviewHistory">刷新历史</el-button></div>
      </template>
      <el-alert v-if="reviewHistoryError" type="error" :closable="false" title="预警审核历史暂时无法加载；请重试后再判断历史原因。">
        <el-button text type="primary" @click="fetchReviewHistory">重新加载审核历史</el-button>
      </el-alert>
      <div class="business-table-wrap"><el-table :data="reviewHistory" style="width: 100%" v-loading="loadingReviewHistory" :empty-text="reviewHistoryError ? '审核历史加载失败。' : '还没有已审核预警记录。'">
        <el-table-column prop="created_at" label="预警时间" width="170" />
        <el-table-column prop="student_name" label="学生" width="130" />
        <el-table-column label="审核结论" width="130">
          <template #default="{row}"><el-tag v-if="row.latestReview" :type="reviewType(row.latestReview.action)">{{ reviewActionLabel(row.latestReview.action) }}</el-tag><span v-else>历史原因不可追溯</span></template>
        </el-table-column>
        <el-table-column label="审核原因" min-width="220">
          <template #default="{row}">{{ row.latestReview?.reason || '没有可追溯的审核原因' }}</template>
        </el-table-column>
        <el-table-column label="跟进" width="120">
          <template #default><el-button type="primary" @click="$router.push('/teacher/support')">创建跟进</el-button></template>
        </el-table-column>
      </el-table>
      </div>
    </el-card>

    <section class="insights-section" aria-labelledby="teacher-insights-heading">
      <div class="insights-heading"><h2 id="teacher-insights-heading">分配范围内的统计与趋势</h2><p>数据用于工作观察；楼宇字段缺失时保留真实空态。</p></div>
      <el-row :gutter="16" class="mt-20" v-if="metrics">
        <el-col :xs="12" :md="6"><el-card shadow="never" class="stat-card business-card"><div class="stat-title">已分配学生（人）</div><div class="stat-value text-blue">{{ metrics.realtime_stats.uv }}</div></el-card></el-col>
        <el-col :xs="12" :md="6"><el-card shadow="never" class="stat-card business-card"><div class="stat-title">每会话用户消息数</div><div class="stat-value">{{ metrics.realtime_stats.avg_session_rounds }}</div></el-card></el-col>
        <el-col :xs="12" :md="6"><el-card shadow="never" class="stat-card business-card"><div class="stat-title">待处理预警（条）</div><div class="stat-value text-red">{{ metrics.realtime_stats.crisis_alerts }}</div></el-card></el-col>
        <el-col :xs="12" :md="6"><el-card shadow="never" class="stat-card business-card"><div class="stat-title">对话消息（条）</div><div class="stat-value text-green">{{ metrics.realtime_stats.pv }}</div></el-card></el-col>
      </el-row>
      <el-row :gutter="16" class="mt-20" v-if="metrics">
        <el-col :xs="24" :lg="8"><el-card shadow="never" class="chart-card business-card"><template #header>学生状态计数</template><div ref="funnelChartRef" class="chart-box"></div></el-card></el-col>
        <el-col :xs="24" :lg="8"><el-card shadow="never" class="chart-card business-card"><template #header>近7日情绪均值</template><LibraryEmpty v-if="!hasEmotionSamples" description="近7日暂无有效情绪样本" :image-size="76" class="chart-empty" /><div v-show="hasEmotionSamples" ref="lineChartRef" class="chart-box"></div></el-card></el-col>
        <el-col :xs="24" :lg="8"><el-card shadow="never" class="chart-card business-card"><template #header>楼栋风险密度</template><LibraryEmpty v-if="!metrics.campus_heatmap?.length" description="尚无可用楼宇数据" :image-size="76" class="chart-empty" /><div v-show="metrics.campus_heatmap?.length" ref="heatmapChartRef" class="chart-box"></div></el-card></el-col>
      </el-row>
    </section>

    <el-dialog v-model="reviewDialogVisible" title="记录预警审核" width="520px" :close-on-click-modal="false" @closed="resetReviewDialog">
      <p class="review-dialog-note">选择“{{ reviewActionLabel(currentReview.action) }}”并说明判断依据。保存后会写入审核历史。</p>
      <el-input v-model="reviewReason" type="textarea" :rows="4" maxlength="1500" show-word-limit placeholder="填写审核原因" :disabled="submittingReview" />
      <p v-if="reviewError" class="review-error" role="alert">{{ reviewError }}</p>
      <template #footer><el-button @click="reviewDialogVisible = false">返回</el-button><el-button type="primary" :loading="submittingReview" :disabled="submittingReview" @click="submitReview">保存审核</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { setLibraryChartOption } from '../../design/chart-registry'
import { businessColor, businessPalette } from '../../styles/business-theme.js'
import { ref, onMounted, onUnmounted, computed, nextTick, shallowRef } from 'vue'
import { ElMessage, ElMessageBox, ElNotification, ElButton, ElIcon, ElAlert, ElRow, ElCol, ElCard, ElBadge, ElTag, ElTable, ElTableColumn, ElDialog, ElInput, vLoading } from 'element-plus'
import * as echarts from '../../design/charts/analytics'
import axios from 'axios'

const metrics = ref(null)
const metricsError = ref(false)
const hasEmotionSamples = computed(() => ['joy', 'anxiety'].some(field => metrics.value?.emotion_trends_7d?.[field]?.some(value => typeof value === 'number' && Number.isFinite(value))))
const pendingList = ref([])
const loadingPending = ref(false)
const pendingLoadError = ref(false)
const reviewHistory = ref([])
const loadingReviewHistory = ref(false)
const reviewHistoryError = ref(false)
const reviewDialogVisible = ref(false)
const currentReview = ref({ row: null, action: '' })
const reviewReason = ref('')
const reviewError = ref('')
const submittingReview = ref(false)
const ws = ref(null)
let pendingPollTimer = null
let reconnectTimer = null
let unmounted = false
const resizeCharts = () => Object.values(chartInstances.value).forEach(chart => chart?.resize())

const pendingCount = computed(() => pendingList.value.length)

const funnelChartRef = ref(null)
const lineChartRef = ref(null)
const heatmapChartRef = ref(null)
const exporting = ref(false)
const chartInstances = shallowRef({
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
    pendingLoadError.value = false
    return true
  } catch (error) {
    console.error('Failed to fetch pending crisis records', error)
    pendingLoadError.value = true
    return false
  } finally {
    loadingPending.value = false
  }
}

const handleReview = (row, action) => {
  currentReview.value = { row, action }
  reviewReason.value = ''
  reviewError.value = ''
  reviewDialogVisible.value = true
}

const submitReview = async () => {
  if (submittingReview.value) return
  const reason = reviewReason.value.trim()
  if (!reason) { reviewError.value = '请填写审核原因。'; return }
  const { row, action } = currentReview.value
  if (!row) return
  submittingReview.value = true
  reviewError.value = ''
  try {
    await axios.post('/api/teacher/crisis/review', {
      recordId: row.id,
      action,
      reason
    })
    reviewDialogVisible.value = false
    const [pendingUpdated, historyUpdated] = await Promise.all([fetchPendingList(), fetchReviewHistory()])
    if (pendingUpdated && historyUpdated) ElMessage.success('审核已保存，预警列表和审核历史已刷新。')
    else ElMessage.warning('审核已保存，但页面刷新未完成，请稍后刷新查看。')
  } catch (error) {
    if (error?.response?.status === 409) reviewError.value = '这条预警已被处理，请刷新预警列表后查看。'
    else if (error?.response?.status === 404) reviewError.value = '这条预警不在你的分配范围内。'
    else if (error?.response?.status === 422) reviewError.value = '审核原因未通过检查，请修改后重试。'
    else if (error?.response?.status === 503) reviewError.value = '审核服务尚未启用，请联系管理员。'
    else reviewError.value = '审核提交失败，请稍后重试。'
  } finally {
    submittingReview.value = false
  }
}

const fetchReviewHistory = async () => {
  loadingReviewHistory.value = true
  reviewHistoryError.value = false
  try {
    const response = await axios.get('/api/advanced-teacher/warnings')
    const rows = Array.isArray(response.data?.data) ? response.data.data : []
    const processed = rows.filter(row => row.status !== 'pending').slice(0, 30)
    const reviews = await Promise.all(processed.map(async row => {
      try {
        const result = await axios.get(`/api/teacher/crisis/${encodeURIComponent(row.id)}/reviews`)
        const items = Array.isArray(result.data?.data) ? result.data.data : []
        return { ...row, latestReview: items.at(-1) || null }
      } catch { return { ...row, latestReview: null } }
    }))
    reviewHistory.value = reviews
    reviewHistoryError.value = false
    return true
  } catch {
    reviewHistoryError.value = true
    return false
  } finally { loadingReviewHistory.value = false }
}

const reviewActionLabel = (action) => ({ pass: '通过', reject: '驳回校正', escalate: '升级处理' }[action] || '审核')
const reviewType = (action) => action === 'pass' ? 'success' : action === 'escalate' ? 'danger' : 'warning'
const resetReviewDialog = () => { currentReview.value = { row: null, action: '' }; reviewReason.value = ''; reviewError.value = '' }

const contactStudent = (row) => {
  ElMessageBox.alert('当前预警记录未提供可拨打的联络方式。请在学生管理中核实档案与校内联络流程。', '联络说明', {
    confirmButtonText: '知道了',
    type: 'info'
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
  const token = (localStorage.getItem('token') || localStorage.getItem('access_token') || '').trim().replace(/^bearer\s+/i, '').trim()
  if (!token) return
  const wsUrl = new URL(axios.getUri({ url: '/api/ws' }), window.location.href)
  wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  ws.value = new WebSocket(wsUrl.href, ['access_token', token])
  ws.value.onopen = () => {
    console.log('Teacher WS connected')
  }
  ws.value.onmessage = (event) => {
    if (unmounted) return
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
  ws.value.onclose = (event) => {
    console.log('Teacher WS disconnected, retrying...')
    if (!unmounted && event.code !== 1008) reconnectTimer = setTimeout(initWebSocket, 5000)
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
  window.addEventListener('resize', resizeCharts)
  await fetchMetrics()
  await fetchPendingList()
  await fetchReviewHistory()
  await nextTick()
  if (unmounted) return
  initCharts()
  initWebSocket()
  pendingPollTimer = setInterval(fetchPendingList, 8000)
})

onUnmounted(() => {
  unmounted = true
  clearTimeout(reconnectTimer)
  window.removeEventListener('resize', resizeCharts)
  Object.values(chartInstances.value).forEach(chart => chart?.dispose())
  if (ws.value) {
    ws.value.close()
  }
  if (pendingPollTimer) {
    clearInterval(pendingPollTimer)
  }
})

const fetchMetrics = async () => {
  metricsError.value = false
  try {
    const res = await axios.get('/api/advanced-teacher/dashboard/metrics')
    metrics.value = res.data
  } catch (error) {
    metricsError.value = true
  }
}

const exportComplianceReport = async () => {
  exporting.value = true
  try {
    const snapshots = [
      { key: 'funnel', title: '学生状态计数' },
      { key: 'line', title: '近7日情绪均值' },
      { key: 'heatmap', title: '楼栋风险密度' }
    ]
      .map(({ key, title }) => {
        const chart = chartInstances.value[key]
        if (!chart) return null
        return {
          title,
          image_data_url: chart.getDataURL({
            type: 'png',
            pixelRatio: 3,
            backgroundColor: businessColor('surface')
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

  // 1. Actual category counts, without an assumed conversion denominator.
  Object.values(chartInstances.value).forEach(chart => chart?.dispose())
  chartInstances.value = { funnel: null, line: null, heatmap: null }
  const funnelChart = echarts.init(funnelChartRef.value, 'xinyu-business')
  chartInstances.value.funnel = funnelChart
  setLibraryChartOption(funnelChart, {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 10, right: 28, top: 16, bottom: 16, containLabel: true },
    xAxis: { type: 'value', min: 0, minInterval: 1 },
    yAxis: { type: 'category', inverse: true, data: metrics.value.funnel_data.map(item => item.name) },
    series: [{
      name: '学生数', type: 'bar', barMaxWidth: 24,
      label: { show: true, position: 'right', fontSize: 12, color: businessColor('text-secondary') },
      itemStyle: { color: businessColor('data-primary'), borderRadius: [0, 4, 4, 0] },
      data: metrics.value.funnel_data.map(item => item.value),
    }],
  })

  // 2. Null days remain gaps; no sample never becomes a zero emotion score.
  if (hasEmotionSamples.value) {
    const trend = metrics.value.emotion_trends_7d
    const lineChart = echarts.init(lineChartRef.value, 'xinyu-business')
    chartInstances.value.line = lineChart
    setLibraryChartOption(lineChart, {
      tooltip: {
        trigger: 'axis', renderMode: 'richText',
        formatter: params => {
          const index = params[0]?.dataIndex ?? 0
          return [trend.dates[index], `有效样本：${trend.sample_counts?.[index] ?? '未提供'}`, ...params.map(item => `${item.seriesName}：${item.value == null ? '暂无样本' : item.value}`)].join('\n')
        },
      },
      legend: { data: ['愉悦强度', '焦虑强度'], top: 0, bottom: 'auto' },
      grid: { left: 12, right: 16, top: 44, bottom: 20, containLabel: true },
      xAxis: { type: 'category', boundaryGap: false, data: trend.dates, axisLabel: { formatter: value => value.length >= 10 ? value.slice(5) : value } },
      yAxis: { type: 'value', min: 0, max: 1.0 },
      series: [
        { name: '愉悦强度', type: 'line', connectNulls: false, data: trend.joy, itemStyle: { color: businessPalette.emotions.joy } },
        { name: '焦虑强度', type: 'line', connectNulls: false, data: trend.anxiety, itemStyle: { color: businessPalette.emotions.anxiety } },
      ],
    })
  }

  // Display the returned density by building; no invented geographic coordinates.
  if (metrics.value.campus_heatmap?.length) {
    const heatChart = echarts.init(heatmapChartRef.value, 'xinyu-business')
    chartInstances.value.heatmap = heatChart
    setLibraryChartOption(heatChart, {
      tooltip: { trigger: 'axis' },
      grid: { left: 12, right: 24, top: 16, bottom: 16, containLabel: true },
      xAxis: { type: 'value', min: 0, max: 1, name: '密度' },
      yAxis: { type: 'category', data: metrics.value.campus_heatmap.map(item => item.building) },
      series: [{ type: 'bar', barMaxWidth: 24, data: metrics.value.campus_heatmap.map(item => item.risk_density), itemStyle: { color: businessColor('data-primary') } }],
    })
  }
}
</script>

<style scoped>
.dashboard-container { display: flex; flex-direction: column; gap: 16px; }
.header-actions { display: flex; justify-content: flex-end; align-items: center; }
.dashboard-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.dashboard-actions :deep(.el-button) { margin-left: 0; }
.insights-section { margin-top: 12px; }
.insights-heading h2 { margin: 0; color: var(--text-primary); font-size: 18px; }
.insights-heading p { margin: 5px 0 0; color: var(--text-secondary); }
.loading-note { padding: 14px 4px; color: var(--text-secondary); }

.stat-card { text-align: center; border-radius: 12px; }
.stat-title { font-size: 14px; color: var(--text-secondary); margin-bottom: 10px; }
.stat-value { font-size: 28px; font-weight: bold; }
.text-blue { color: var(--brand-600); }
.text-red { color: var(--danger-text); }
.text-green { color: var(--success-text); }

.chart-card { border-radius: 12px; }
.chart-box { height: 250px; width: 100%; }
.chart-empty { min-height: 250px; }
:deep(.el-table) { min-width: 980px; }

.audit-msg { font-size: 14px; color: var(--text-primary); background: var(--surface-subtle); padding: 10px; border-radius: 6px; }
.audit-reply { font-size: 13px; color: var(--text-secondary); border-left: 3px solid var(--brand-600); padding-left: 10px; }

.slider-row { display: flex; align-items: center; gap: 15px; margin-bottom: 8px; }
.slider-row span { width: 80px; font-size: 12px; color: var(--text-secondary); }
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
  border: 1px solid var(--danger-text);
  box-shadow: 0 0 10px color-mix(in srgb, var(--danger-text) 20%, transparent);
}

:deep(.warning-row-unread) {
  background-color: var(--danger-100) !important;
}
:deep(.warning-row-unread:hover > td) {
  background-color: var(--danger-100) !important;
}
@media (max-width: 640px) {
  .dashboard-actions { display: grid; grid-template-columns: 1fr; width: 100%; }
  .dashboard-actions :deep(.el-button) { width: 100%; }
  .stat-value { font-size: 24px; }
  .insights-heading h2 { font-size: 17px; }
}
</style>
