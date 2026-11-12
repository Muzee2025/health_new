<template>
  <el-card class="risk-card" shadow="hover">
    <template #header>
      <div class="risk-header">
        <span>五个方面的观察数据</span>
        <el-button
          v-if="error"
          size="small"
          class="action-btn"
          :loading="loading"
          @click="loadRiskData"
          >重试</el-button
        >
      </div>
    </template>
    <div v-if="loading" class="placeholder">加载中...</div>
    <div v-else-if="error" class="placeholder">
      <LibraryEmpty role="networkError" :description="emptyDescription" />
    </div>
    <div v-else-if="!hasData" class="placeholder">
      <LibraryEmpty role="emptyReport" :description="emptyDescription" />
    </div>
    <div v-else ref="radarRef" class="radar"></div>
    <p v-if="hasData && provenanceLabel" class="provenance">数据依据：{{ provenanceLabel }}</p>
  </el-card>
</template>

<script setup>
import { setLibraryChartOption } from '../design/chart-registry'
import { businessAlpha, businessColor } from '../styles/business-theme.js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import { getFiveDimensionFailure, getFiveDimensionResult } from '../services/fiveDimensionData'
import { ElCard, ElButton } from 'element-plus'

const radarRef = ref(null)
const loading = ref(false)
const error = ref(false)
const riskData = ref(null)
const provenanceLabel = ref('')
const emptyDescription = ref('暂无可核验的五维观察数据')
let requestController = null
let requestEpoch = 0
let activeIdentity = readIdentity()
let radarChart = null
let unmounted = false

function readIdentity() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    return `${user?.id ?? ''}:${localStorage.getItem('token') || localStorage.getItem('access_token') || ''}`
  } catch {
    return `:${localStorage.getItem('token') || localStorage.getItem('access_token') || ''}`
  }
}

const hasData = computed(() => {
  if (!riskData.value) return false
  return ['academic', 'interpersonal', 'family', 'emotion', 'physical'].every(
    (key) => typeof riskData.value[key] === 'number',
  )
})

const renderChart = async (epoch = requestEpoch, identity = activeIdentity) => {
  if (!hasData.value || !radarRef.value) return
  const echarts = await import('../design/charts/radar')
  await nextTick()
  if (unmounted || epoch !== requestEpoch || identity !== readIdentity()) {
    if (!unmounted && epoch === requestEpoch) handleIdentityChange()
    return
  }
  if (!hasData.value || !radarRef.value) return
  if (!radarChart) radarChart = echarts.init(radarRef.value, 'xinyu-business')
  setLibraryChartOption(radarChart, {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: [
        { name: '学业', max: 100 },
        { name: '人际', max: 100 },
        { name: '家庭', max: 100 },
        { name: '情绪', max: 100 },
        { name: '身体', max: 100 },
      ],
      axisName: { color: businessColor('data-primary') },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: [
              riskData.value.academic,
              riskData.value.interpersonal,
              riskData.value.family,
              riskData.value.emotion,
              riskData.value.physical,
            ],
            areaStyle: { color: businessAlpha('data-primary', 0.2) },
            lineStyle: { color: businessColor('data-primary') },
            itemStyle: { color: businessColor('data-primary') },
          },
        ],
      },
    ],
  })
}

const loadRiskData = async () => {
  if (unmounted) return
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  const epoch = ++requestEpoch
  const identity = readIdentity()
  activeIdentity = identity
  loading.value = true
  error.value = false
  riskData.value = null
  provenanceLabel.value = ''
  radarChart?.dispose()
  radarChart = null
  try {
    const res = await axios.get('/api/v1/assistant/risk-factor', {
      timeout: 12000,
      signal: controller.signal,
    })
    if (unmounted || epoch !== requestEpoch || identity !== readIdentity()) return
    if (res.status !== 200 || !res.data) throw new Error('invalid response')
    const result = getFiveDimensionResult(res.data)
    if (result.status === 'ready') {
      riskData.value = result.dimensions
      provenanceLabel.value = result.provenance
      emptyDescription.value = '暂无可核验的五维观察数据'
    } else {
      emptyDescription.value = result.message
    }
    loading.value = false
    if (result.status === 'ready') {
      await nextTick()
      if (!unmounted && epoch === requestEpoch && identity === readIdentity())
        await renderChart(epoch, identity)
    }
  } catch (err) {
    if (unmounted || epoch !== requestEpoch || err?.code === 'ERR_CANCELED') return
    if (identity !== readIdentity()) return
    const result = getFiveDimensionFailure(err)
    if (result.status === 'network-error') {
      error.value = true
      emptyDescription.value = result.message
    } else {
      emptyDescription.value = result.message
    }
  } finally {
    if (epoch === requestEpoch) {
      loading.value = false
      requestController = null
    }
  }
}

const handleIdentityChange = () => {
  const identity = readIdentity()
  if (identity === activeIdentity) return
  requestEpoch += 1
  requestController?.abort()
  requestController = null
  riskData.value = null
  provenanceLabel.value = ''
  loading.value = false
  error.value = false
  radarChart?.dispose()
  radarChart = null
  activeIdentity = identity
  if (identity !== ':') loadRiskData()
}

onMounted(() => {
  loadRiskData()
  window.addEventListener('resize', resizeChart)
  window.addEventListener('storage', handleIdentityChange)
  window.addEventListener('focus', handleIdentityChange)
})

const resizeChart = () => radarChart?.resize()

onBeforeUnmount(() => {
  unmounted = true
  requestEpoch += 1
  requestController?.abort()
  requestController = null
  window.removeEventListener('resize', resizeChart)
  window.removeEventListener('storage', handleIdentityChange)
  window.removeEventListener('focus', handleIdentityChange)
  if (radarChart) radarChart.dispose()
  radarChart = null
})
</script>

<style scoped>
.risk-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px 0 color-mix(in srgb, var(--gray-900) 8%, transparent);
}

.risk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.provenance {
  margin: 0 0 12px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.placeholder {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.radar {
  width: 100%;
  height: 240px;
}

.action-btn {
  transition: transform 200ms ease;
}

.action-btn:hover {
  transform: scale(1.02);
}
</style>
