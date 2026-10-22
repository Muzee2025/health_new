<template>
  <el-card class="risk-card" shadow="hover">
    <template #header>
      <div class="risk-header">
        <span>风险因子五维评估</span>
        <el-button size="small" class="action-btn" @click="loadRiskData">重试</el-button>
      </div>
    </template>
    <div v-if="loading" class="placeholder">加载中...</div>
    <div v-else-if="error" class="placeholder">
      <LibraryEmpty role="networkError" description="数据加载失败，请重试" />
    </div>
    <div v-else-if="!hasData" class="placeholder">
      <LibraryEmpty role="emptyReport" description="暂无五维风险数据" />
    </div>
    <div v-else ref="radarRef" class="radar"></div>
  </el-card>
</template>

<script setup>
import { setLibraryChartOption } from '../design/chart-registry'
import { businessAlpha, businessColor } from '../styles/business-theme.js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue"
import axios from "axios"
import * as echarts from '../design/charts/radar'
import { ElMessage, ElCard, ElButton } from 'element-plus'

const radarRef = ref(null)
const loading = ref(false)
const error = ref(false)
const riskData = ref(null)
let radarChart = null
let unmounted = false

const hasData = computed(() => {
  if (!riskData.value) return false
  return ["academic", "interpersonal", "family", "emotion", "physical"].every(
    (key) => typeof riskData.value[key] === "number"
  )
})

const normalizeData = (raw) => ({
  academic: Number(raw.academic ?? raw.Academic ?? 0),
  interpersonal: Number(raw.interpersonal ?? raw.Interpersonal ?? 0),
  family: Number(raw.family ?? raw.Family ?? 0),
  emotion: Number(raw.emotion ?? raw.Emotion ?? 0),
  physical: Number(raw.physical ?? raw.Physical ?? 0),
})

const isValidData = (data) => {
  return ["academic", "interpersonal", "family", "emotion", "physical"].every((key) => {
    const val = Number(data[key])
    return Number.isFinite(val) && val >= 0 && val <= 100
  })
}

const renderChart = async () => {
  if (!hasData.value || !radarRef.value) return
  await nextTick()
  if (unmounted || !radarRef.value) return
  if (!radarChart) radarChart = echarts.init(radarRef.value, 'xinyu-business')
  setLibraryChartOption(radarChart, {
    tooltip: { trigger: "item" },
    radar: {
      indicator: [
        { name: "学业", max: 100 },
        { name: "人际", max: 100 },
        { name: "家庭", max: 100 },
        { name: "情绪", max: 100 },
        { name: "身体", max: 100 },
      ],
      axisName: { color: businessColor('data-primary') },
    },
    series: [
      {
        type: "radar",
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
  loading.value = true
  error.value = false
  try {
    const res = await axios.get("/api/v1/assistant/risk-factor")
    if (unmounted) return
    if (res.status !== 200 || !res.data) {
      throw new Error("invalid data")
    }
    const normalized = normalizeData(res.data.data || res.data)
    if (!isValidData(normalized)) {
      throw new Error("invalid range")
    }
    riskData.value = normalized
    await renderChart()
  } catch (err) {
    if (unmounted) return
    error.value = true
    ElMessage.warning("风险因子获取失败或数据异常，请重试")
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRiskData()
  window.addEventListener("resize", resizeChart)
})

const resizeChart = () => radarChart?.resize()

onBeforeUnmount(() => {
  unmounted = true
  window.removeEventListener("resize", resizeChart)
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
