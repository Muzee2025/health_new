<template>
  <div class="report-container business-page">
    <el-alert
      v-if="loadError"
      type="error"
      :closable="false"
      show-icon
      :title="processingError || '报告暂时无法加载，请稍后重试。'"
    >
      <el-button link type="primary" @click="fetchLatest({ retryTrigger: true })">{{
        processingError ? '重新尝试分析' : '重新加载报告'
      }}</el-button>
    </el-alert>
    <div class="header-container">
      <div>
        <h2 class="page-title">我的心理报告（对话驱动）</h2>
        <p class="page-desc">
          汇总已保存记录与本地规则线索；可用字段、具体来源和资料范围会在报告中注明，不代替专业评估。
        </p>
      </div>
      <div class="actions">
        <el-button
          v-if="collabEnabled"
          :loading="refreshing || collabRunning"
          :disabled="collabRunning"
          type="primary"
          @click="refreshReport"
        >
          {{ collabRunning ? '分析中...' : '重新运行协同分析' }}
        </el-button>
        <span v-else class="collab-status" role="status">多模型协同未启用</span>
        <el-button
          :disabled="loading || loadError || (!reportData && !collaborativeReport)"
          @click="openPrintPreview"
          >打印报告</el-button
        >
        <el-button @click="shareReport">分享说明</el-button>
      </div>
    </div>

    <el-alert
      v-if="!collabEnabled"
      class="collab-safety-note"
      type="info"
      :closable="false"
      show-icon
      title="当前可查看本地汇总和已保存记录；多模型协同未启用。"
    />

    <el-skeleton :loading="loading" animated>
      <template #template>
        <el-skeleton-item variant="rect" style="width: 100%; height: 180px" />
      </template>
      <template #default>
        <el-card class="summary-card" v-if="reportData">
          <h3>
            风险状态：
            <span :class="`risk-${riskLevel.toLowerCase()}`">{{ riskLevel }}</span>
          </h3>
          <p>
            情绪维度 {{ displayValue(reportData.scores?.emotion) }} / 认知维度
            {{ displayValue(reportData.scores?.cognition) }} / 行为维度
            {{ displayValue(reportData.scores?.behavior) }}
          </p>
          <p>
            抑郁 {{ displayValue(reportData.risk?.depression_confidence) }}，焦虑
            {{ displayValue(reportData.risk?.anxiety_confidence) }}，自杀风险
            {{ displayValue(reportData.risk?.suicide_confidence) }}
          </p>
          <p v-if="reportData.data_status === 'insufficient'">
            当前没有足够的已记录对话数据，暂不生成风险结论。
          </p>
          <p v-else-if="reportData.generated_mode">
            本报告生成方式：{{ generationModeLabel
            }}<template v-if="reportData.generation?.status"
              >；状态：{{ generationStatusLabel }}</template
            >
          </p>
          <p v-if="reportData.interventions?.length">{{ reportData.interventions.join(' ') }}</p>
        </el-card>
      </template>
    </el-skeleton>

    <el-card v-if="!loading && !loadError && !reportData" class="report-empty" shadow="never">
      <LibraryEmpty role="emptyReport" description="还没有可汇总的对话记录" :image-size="110">
        <p class="report-empty-copy">有已保存的记录后，这里会展示来源、变化与报告说明。</p>
        <div class="business-actions">
          <el-button type="primary" @click="$router.push('/student/advanced-chat')"
            >查看智能助手</el-button
          >
          <el-button plain @click="$router.push('/student/questions')">向老师留言</el-button>
        </div>
      </LibraryEmpty>
    </el-card>

    <section
      v-if="reportData"
      class="interpretation-section"
      aria-labelledby="interpretation-title"
    >
      <div class="interpretation-heading">
        <div>
          <h3 id="interpretation-title">报告说明</h3>
          <p>按需获取简要说明。服务只接收已保存记录的位置，不发送对话原文。</p>
        </div>
        <el-button
          type="primary"
          :loading="interpretationLoading"
          :disabled="interpretationLoading || latestReportRecordId === null"
          @click="requestInterpretation"
          >{{ interpretationLoading ? '正在整理…' : '请求说明' }}</el-button
        >
      </div>
      <AIInterpretCard
        :text="interpretation?.text || ''"
        :status="interpretation?.status || 'idle'"
        :source="interpretation?.source || ''"
        :model-id="interpretation?.model_id || ''"
        :error-message="interpretationError"
        :empty-message="interpretationEmptyMessage"
      />
    </section>

    <el-dialog
      v-model="collabVisible"
      width="960px"
      :close-on-click-modal="false"
      :show-close="!collabRunning"
      :class="['collab-dialog', collabFading ? 'is-fading' : '']"
      title="多模型协同分析中"
      @closed="handleCollabDialogClosed"
    >
      <div class="collab-top">
        <el-progress :percentage="collabProgress" :status="collabRunning ? '' : 'success'" />
        <div class="collab-meta">
          <span>当前模型：{{ collabCurrentModel || '-' }}</span>
          <span>阶段：{{ collabCurrentStage || '-' }}</span>
          <span>预计剩余：{{ collabEtaSec }}s</span>
        </div>
      </div>

      <div class="collab-grid">
        <el-card class="collab-card">
          <template #header><span>模型处理状态</span></template>
          <div class="collab-step-list">
            <div v-for="step in collabSteps" :key="step.model" class="collab-step-row">
              <el-tag
                :type="
                  step.status === 'done'
                    ? 'success'
                    : step.status === 'error'
                      ? 'danger'
                      : step.status === 'degraded'
                        ? 'warning'
                        : step.status === 'running'
                          ? 'warning'
                          : 'info'
                "
                size="small"
              >
                {{ step.statusText }}
              </el-tag>
              <span class="collab-step-model">{{ step.model }}</span>
              <span class="collab-step-stage">{{ step.stage }}</span>
            </div>
          </div>
        </el-card>

        <el-card class="collab-card">
          <template #header><span>关键中间结果</span></template>
          <div class="middle-list">
            <div v-for="(m, i) in collabMiddle" :key="`${m.model}-${i}`" class="middle-row">
              <strong>{{ m.model }}</strong>
              <p>{{ m.summary }}</p>
            </div>
          </div>
        </el-card>

        <el-card class="collab-card collab-flow-card">
          <template #header><span>本次模型调用状态</span></template>
          <div ref="collabFlowRef" class="chart-box flow-box"></div>
        </el-card>
      </div>
    </el-dialog>

    <el-dialog
      v-model="reportVisible"
      width="900px"
      :close-on-click-modal="true"
      :show-close="true"
      class="report-dialog"
      title="多模型协同分析报告"
      @closed="handleReportDialogClosed"
    >
      <div v-if="collaborativeReport" class="report-dialog-body">
        <div class="modern-metric-grid">
          <div class="modern-card metric-card">
            <div class="metric-label">总置信度</div>
            <div class="metric-value">{{ displayConfidence(collaborativeReport.confidence) }}</div>
            <div
              v-if="isPresentNumber(collaborativeReport.confidence)"
              class="metric-progress-track"
            >
              <div
                class="metric-progress-fill"
                :style="{ width: `${Math.round(Number(collaborativeReport.confidence) * 100)}%` }"
              ></div>
            </div>
          </div>
          <div class="modern-card metric-card">
            <div class="metric-label">模型数</div>
            <div class="metric-value">{{ (collaborativeReport.modelResults || []).length }}</div>
          </div>
          <div class="modern-card metric-card">
            <div class="metric-label">总Token</div>
            <div class="metric-value">{{ totalTokens }}</div>
          </div>
          <div class="modern-card metric-card">
            <div class="metric-label">更新时间</div>
            <div class="metric-value metric-time">{{ collaborativeReport.updated_at || '-' }}</div>
          </div>
        </div>

        <div class="modern-two-col-grid">
          <section class="modern-card report-section">
            <h4 class="section-title">执行摘要</h4>
            <div v-if="hasQwenDegrade" class="summary-alert">
              <LibraryIcon name="alert" class="summary-alert-icon" />
              <span class="summary-alert-text">qwen3.6-plus 异常降级</span>
            </div>
            <ul class="summary-list">
              <li v-for="(item, idx) in executiveSummaryItems" :key="`summary-${idx}`">
                {{ item }}
              </li>
            </ul>
          </section>
          <section class="modern-card report-section">
            <h4 class="section-title">协同结论</h4>
            <div class="conclusion-highlight">
              <LibraryIcon name="alert" class="warn-icon" />
              <p class="report-paragraph">
                {{ collaborativeReport.collaborativeConclusion || '暂无协同结论' }}
              </p>
            </div>
          </section>
        </div>

        <div class="modern-two-col-grid core-stack-grid">
          <section class="modern-card report-section">
            <h4 class="section-title">模型置信度字段</h4>
            <div v-if="hasModelConfidenceRows" class="confidence-canvas-wrap">
              <canvas ref="collabConfidenceCanvasRef" class="confidence-canvas" />
            </div>
            <p v-else class="diag-empty">本次报告没有可展示的置信度值。</p>
          </section>

          <section class="modern-card report-section">
            <h4 class="section-title">核心明细（Top 3）</h4>
            <div class="core-detail-list">
              <div class="core-detail-item" v-for="row in topModelRows" :key="row.model">
                <div class="core-detail-top">
                  <span class="model-cell">{{ row.model }}</span>
                  <div class="table-progress-row">
                    <span class="table-progress-label">{{
                      displayConfidence(row.confidence)
                    }}</span>
                    <div v-if="isPresentNumber(row.confidence)" class="table-progress-track">
                      <div
                        class="table-progress-fill"
                        :style="{ width: `${Math.round(Number(row.confidence) * 100)}%` }"
                      ></div>
                    </div>
                  </div>
                </div>
                <p class="summary-cell">{{ row.summary || '-' }}</p>
              </div>
            </div>
          </section>
        </div>

        <section class="modern-card report-section diag-section">
          <h4 class="section-title">模型异常诊断</h4>
          <div v-if="modelDiagRows.length" class="diag-warning-box">
            <LibraryIcon name="alert" class="diag-warning-icon" />
            <div class="diag-warning-text">
              <strong>检测到{{ modelDiagRows.length }}个模型异常</strong>
              <p>
                {{ primaryDiagReason }}
              </p>
            </div>
          </div>
          <div v-if="modelDiagRows.length" class="diag-list">
            <div class="diag-row" v-for="item in modelDiagRows" :key="item.model">
              <span class="diag-model">{{ item.model }}</span>
              <span class="diag-reason">{{ item.reason }}</span>
              <span class="diag-fix">{{ item.fix }}</span>
            </div>
          </div>
          <p v-else class="diag-empty">
            {{
              (collaborativeReport.modelResults || []).length
                ? '本次未发现已报告异常'
                : '本次没有模型调用记录'
            }}
          </p>
        </section>
      </div>
    </el-dialog>

    <el-dialog
      v-model="printPreviewVisible"
      width="85vw"
      top="3vh"
      class="print-preview-dialog"
      title="心理报告打印预览（A4）"
    >
      <div class="preview-shell">
        <section class="print-report print-report-preview">
          <header class="print-header">
            <h1>心理报告（图表与 AI 针对性分析）</h1>
            <p>生成时间：{{ printPayload.generatedAt }}</p>
            <p>风险状态：{{ printPayload.riskLevel }}</p>
          </header>

          <section class="print-section" v-if="printPayload.targetedAnalysis.length">
            <h2>AI 针对性分析</h2>
            <p
              v-for="(text, idx) in printPayload.targetedAnalysis"
              :key="`preview-analysis-${idx}`"
              class="print-paragraph"
            >
              {{ text }}
            </p>
          </section>

          <section class="print-section">
            <h2>核心指标摘要</h2>
            <div class="print-indicator-grid">
              <div
                class="print-indicator-item"
                v-for="item in printPayload.indicators"
                :key="`preview-${item.label}`"
              >
                <span class="print-indicator-label">{{ item.label }}</span>
                <strong class="print-indicator-value">{{ item.value }}</strong>
              </div>
            </div>
          </section>

          <section class="print-section">
            <h2>心理图表与说明</h2>
            <article
              class="print-chart-card"
              v-for="item in printPayload.charts"
              :key="`preview-${item.key}`"
            >
              <h3>{{ item.title }}</h3>
              <p class="print-caption">{{ item.caption }}</p>
              <img
                v-if="item.image"
                :src="item.image"
                :alt="item.title"
                class="print-chart-image"
              />
              <p v-else class="print-chart-missing">图表暂不可用（当前会话未完成渲染）。</p>
              <p class="print-analysis"><strong>图表说明：</strong>{{ item.analysis }}</p>
            </article>
          </section>
        </section>
      </div>
      <template #footer>
        <div class="preview-actions">
          <el-button @click="printPreviewVisible = false">关闭预览</el-button>
          <el-button type="primary" @click="confirmPrintFromPreview">确认打印</el-button>
        </div>
      </template>
    </el-dialog>

    <el-card v-if="reportData && !hasAnyChartData" class="chart-card">
      <LibraryEmpty
        role="emptyReport"
        description="还没有足够的记录生成图表。你可以先记录近况，或直接选择人工求助。"
      />
      <el-button type="primary" @click="$router.push('/student/advanced-chat')"
        >先记录近况</el-button
      >
    </el-card>
    <div v-if="hasAnyChartData" class="charts-grid">
      <el-card v-if="hasMetricData" class="chart-card">
        <template #header><span>已有记录展示值</span></template>
        <div v-if="hasMetricData" ref="barRef" class="chart-box"></div>
        <div v-else class="chart-empty">当前没有可绘制的指标数据。</div>
        <p class="chart-ai">{{ chartExplanation('bar') }}</p>
      </el-card>
      <el-card v-if="hasEmotionSamples" class="chart-card">
        <template #header><span>对话规则标签占比</span></template>
        <div v-if="hasEmotionSamples" ref="pieRef" class="chart-box"></div>
        <div v-else class="chart-empty">当前没有带情绪标注的对话记录。</div>
        <p class="chart-ai">{{ chartExplanation('pie') }}</p>
      </el-card>
      <el-card v-if="hasHeatmapData" class="chart-card">
        <template #header><span>热图：情绪强度与时间</span></template>
        <div v-if="hasHeatmapData" ref="heatmapRef" class="chart-box"></div>
        <div v-else class="chart-empty">当前没有足够的时间序列数据。</div>
        <p class="chart-ai">{{ chartExplanation('heatmap') }}</p>
      </el-card>
      <el-card v-if="hasTrendData" class="chart-card">
        <template #header><span>时间序列：规则展示值</span></template>
        <div v-if="hasTrendData" ref="trendRef" class="chart-box"></div>
        <div v-else class="chart-empty">当前没有可展示的历史趋势点。</div>
        <p class="chart-ai">{{ chartExplanation('trend') }}</p>
      </el-card>
      <el-card v-if="hasDistributionSamples" class="chart-card">
        <template #header><span>直方图：心理数据分布</span></template>
        <div v-if="hasDistributionSamples" ref="histogramRef" class="chart-box"></div>
        <div v-else class="chart-empty">当前没有服务端返回的数值样本。</div>
        <p class="chart-ai">{{ chartExplanation('histogram') }}</p>
      </el-card>
    </div>

    <el-card v-if="hasModelConfidenceRows" class="chart-card">
      <template #header>
        <div class="model-compare-header">
          <span>本次协同报告模型结果</span>
          <div class="model-compare-actions">
            <el-select
              v-model="selectedModels"
              :disabled="!hasModelConfidenceRows"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="筛选模型"
              style="width: 320px"
            >
              <el-option
                v-for="item in modelSelectOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-segmented
              v-model="compareChartType"
              :disabled="!hasModelConfidenceRows"
              :options="[
                { label: '柱状图', value: 'bar' },
                { label: '雷达图', value: 'radar' },
              ]"
            />
          </div>
        </div>
      </template>
      <div v-if="hasModelConfidenceRows" ref="collabCompareRef" class="chart-box"></div>
      <div v-else class="chart-empty">当前没有可比较的模型置信度记录。</div>
      <p class="chart-ai">图表展示本次报告返回的置信度字段；缺失值不会按零显示。</p>
    </el-card>

    <el-card v-if="dialogueRows.length" class="chart-card">
      <template #header><span>本次报告依据的对话记录</span></template>
      <el-table :data="dialogueRows" stripe height="320">
        <el-table-column prop="created_at" label="时间戳" width="180" />
        <el-table-column prop="role" label="角色" width="90" />
        <el-table-column prop="content" label="文本内容" min-width="260" />
        <el-table-column label="情绪标签" min-width="180">
          <template #default="{ row }">
            <div class="emotion-tag-row">
              <span v-if="!formatEmotionTags(row.emotion_tags).length" class="emotion-empty"
                >未提供</span
              >
              <template
                v-for="(tag, idx) in formatEmotionTags(row.emotion_tags)"
                :key="`${tag.key}-${idx}`"
              >
                <span class="emotion-chip" :class="`chip-${tag.key}`"
                  >{{ tag.label }} {{ tag.percent }}%</span
                >
                <span
                  v-if="idx < formatEmotionTags(row.emotion_tags).length - 1"
                  class="emotion-sep"
                  >|</span
                >
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="关键词" min-width="160">
          <template #default="{ row }">{{ (row.keywords || []).join('、') }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <section class="print-report">
      <header class="print-header">
        <h1>心理报告（图表与 AI 针对性分析）</h1>
        <p>生成时间：{{ printPayload.generatedAt }}</p>
        <p>风险状态：{{ printPayload.riskLevel }}</p>
      </header>

      <section class="print-section" v-if="printPayload.targetedAnalysis.length">
        <h2>AI 针对性分析</h2>
        <p
          v-for="(text, idx) in printPayload.targetedAnalysis"
          :key="`analysis-${idx}`"
          class="print-paragraph"
        >
          {{ text }}
        </p>
      </section>

      <section class="print-section">
        <h2>核心指标摘要</h2>
        <div class="print-indicator-grid">
          <div
            class="print-indicator-item"
            v-for="item in printPayload.indicators"
            :key="item.label"
          >
            <span class="print-indicator-label">{{ item.label }}</span>
            <strong class="print-indicator-value">{{ item.value }}</strong>
          </div>
        </div>
      </section>

      <section class="print-section">
        <h2>心理图表与说明</h2>
        <article class="print-chart-card" v-for="item in printPayload.charts" :key="item.key">
          <h3>{{ item.title }}</h3>
          <p class="print-caption">{{ item.caption }}</p>
          <img v-if="item.image" :src="item.image" :alt="item.title" class="print-chart-image" />
          <p v-else class="print-chart-missing">图表暂不可用（当前会话未完成渲染）。</p>
          <p class="print-analysis"><strong>图表说明：</strong>{{ item.analysis }}</p>
        </article>
      </section>
    </section>
  </div>
</template>

<script setup>
import {
  setLibraryChartOption,
  createLibraryChartJsConfig,
  libraryChartFont,
} from '../../design/chart-registry'
import { businessAlpha, businessColor, businessPalette } from '../../styles/business-theme.js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import {
  ElMessage,
  ElButton,
  ElSkeleton,
  ElSkeletonItem,
  ElCard,
  ElDialog,
  ElProgress,
  ElTag,
  ElSelect,
  ElOption,
  ElSegmented,
  ElTable,
  ElTableColumn,
  ElAlert,
} from 'element-plus'
import { computeRenderStrategy, parseSseBlocks } from '@/services/reportStream'
import { getReportPollDelayMs, shouldPollReportAgain } from '@/services/reportPolling'
import { finiteNumberOrNull, isPresentNumber } from '@/services/reportNumbers'
import AIInterpretCard from '@/components/AIInterpretCard.vue'

const loading = ref(false)
const loadError = ref(false)
const refreshing = ref(false)
const reportData = ref(null)
const interpretation = ref(null)
const interpretationLoading = ref(false)
const interpretationError = ref('')
/** @type {AbortController | null} */
let interpretationController = null
let interpretationEpoch = 0
const barRef = ref(null)
const pieRef = ref(null)
const heatmapRef = ref(null)
const trendRef = ref(null)
const histogramRef = ref(null)
const collabFlowRef = ref(null)
const collabConfidenceCanvasRef = ref(null)
const collabCompareRef = ref(null)
let barChart = null
let pieChart = null
let heatmapChart = null
let trendChart = null
let networkChart = null
let histogramChart = null
let collabFlowChart = null
let collabConfidenceChart = null
let collabCompareChart = null
let echartsRuntime = null
let echartsRuntimePromise = null
let chartJsRuntimePromise = null
let realtimeTimer = null
/** @type {AbortController | null} */
let esAbort = null
/** @type {AbortController | null} */
let collabAbort = null
let reportSnapshot = null
let assistantEventHandler = null
let unmounted = false
let processingRetryTimer = null
let reportLoadController = null
let metadataController = null
let reportLoadEpoch = 0
let reportProcessingTriggered = false
const processingError = ref('')
let reportIdentity = readReportIdentity()
let collabFadeTimer = null
let collabCloseTimer = null
const collabVisible = ref(false)
const collabRunning = ref(false)
const collabEnabled = ref(false)
const collabFading = ref(false)
const reportVisible = ref(false)
const shouldOpenReportAfterCollab = ref(false)
const collabTaskId = ref('')
const collabProgress = ref(0)
const collabCurrentModel = ref('')
const collabCurrentStage = ref('')
const collabEtaSec = ref(0)
const collabMiddle = ref([])
const collaborativeReport = ref(null)
const collabSteps = ref([])
const compareChartType = ref('bar')
const selectedModels = ref([])
const primaryModelName = ref('当前模型')
const legacyPrimaryModelAlias = ref('')
const printPreviewVisible = ref(false)
const printPayload = ref({
  generatedAt: '-',
  riskLevel: 'UNKNOWN',
  targetedAnalysis: [],
  indicators: [],
  charts: [],
})

const normalizeModelName = (name) => {
  if (name === legacyPrimaryModelAlias.value) return primaryModelName.value
  return name
}

const riskLevel = computed(() => {
  const value = String(reportData.value?.risk?.risk_level || 'UNKNOWN').toUpperCase()
  return { UNKNOWN: '待人工评估', LOW: '低', MEDIUM: '中', HIGH: '高' }[value] || value
})
const generationModeLabel = computed(() => {
  const mode = reportData.value?.generation?.source || reportData.value?.generated_mode
  return { quick: '快速汇总', local_rules: '本地规则', provider: '模型服务' }[mode] || '未注明'
})
const generationStatusLabel = computed(
  () =>
    ({
      completed: '已完成',
      fallback: '本地回退',
      insufficient: '资料不足',
      unverified: '来源未核验',
    })[reportData.value?.generation?.status] || '状态未注明',
)
const displayValue = (value) => (!isPresentNumber(value) ? '暂无数据' : Number(value).toFixed(1))
const hasMetricData = computed(() => {
  const scores = reportData.value?.scores || {}
  const risk = reportData.value?.risk || {}
  return [
    scores.emotion,
    scores.cognition,
    scores.behavior,
    risk.depression_confidence,
    risk.anxiety_confidence,
    risk.suicide_confidence,
  ].some(isPresentNumber)
})
const hasEmotionSamples = computed(() =>
  dialogueRows.value.some((row) => formatEmotionTags(row?.emotion_tags).length > 0),
)
const hasDistributionSamples = computed(() =>
  dialogueRows.value.some(
    (row) => isPresentNumber(row?.score) && Number(row.score) >= 0 && Number(row.score) <= 100,
  ),
)
const hasHeatmapData = computed(() =>
  (reportData.value?.trends?.heatmap || []).some(
    (row) => row && [row.depression, row.anxiety, row.suicide].some(isPresentNumber),
  ),
)
const hasTrendData = computed(() =>
  [
    ...(reportData.value?.trends?.seven_days || []),
    ...(reportData.value?.trends?.thirty_days || []),
  ].some((row) => isPresentNumber(row?.score)),
)
const hasAnyChartData = computed(
  () =>
    hasMetricData.value ||
    hasEmotionSamples.value ||
    hasHeatmapData.value ||
    hasTrendData.value ||
    hasDistributionSamples.value,
)
const dialogueRows = computed(() => reportData.value?.source?.messages || [])
const latestReportRecordId = computed(() =>
  dialogueRows.value.length > 0 && dialogueRows.value.length - 1 <= 5000
    ? dialogueRows.value.length - 1
    : null,
)
const interpretationEmptyMessage = computed(() =>
  dialogueRows.value.length === 0
    ? '暂无已保存对话可供说明。'
    : '当前记录数量超出说明服务范围，暂不能生成说明。',
)
const modelConfidenceRows = computed(() => {
  const rows = collaborativeReport.value?.modelResults || []
  if (!selectedModels.value.length) return rows
  return rows.filter((x) => selectedModels.value.includes(x.model))
})
const hasModelConfidenceRows = computed(() =>
  modelConfidenceRows.value.some((row) => isPresentNumber(row.confidence)),
)
const modelSelectOptions = computed(() => {
  const rows = collaborativeReport.value?.modelResults || []
  return rows.map((x) => ({
    label: normalizeModelName(x.model),
    value: normalizeModelName(x.model),
  }))
})
const readTotalTokens = (row) => {
  const fromTop = row?.totalTokens
  const fromUsage = row?.usage?.total_tokens ?? row?.detail?.usage?.total_tokens
  const value = fromTop ?? fromUsage
  return isPresentNumber(value) && Number(value) >= 0 ? Number(value) : null
}
const totalTokens = computed(() => {
  const values = (collaborativeReport.value?.modelResults || [])
    .map(readTotalTokens)
    .filter((value) => value !== null)
  return values.length ? values.reduce((sum, value) => sum + value, 0) : '暂无数据'
})
const displayConfidence = (value) =>
  isPresentNumber(value) ? `${Math.round(Number(value) * 100)}%` : '暂无数据'
const topModelRows = computed(() => {
  const rows = [...(collaborativeReport.value?.modelResults || [])]
  return rows.sort((a, b) => Number(b.confidence || 0) - Number(a.confidence || 0)).slice(0, 3)
})
const hasQwenDegrade = computed(() => {
  return modelDiagRows.value.some((x) => String(x.model || '').includes('qwen3.6-plus'))
})
const executiveSummaryItems = computed(() => {
  const raw = String(collaborativeReport.value?.executiveSummary || '').trim()
  if (!raw) return ['暂无执行摘要']
  const normalized = raw.replace(/\r/g, '')
  const candidateLines = normalized
    .split(/\n+/)
    .map((x) => x.replace(/^[\s•\-·\d.)]+/, '').trim())
    .filter(Boolean)
  if (candidateLines.length > 1) return candidateLines.slice(0, 5)
  return normalized
    .split(/[；;。]/)
    .map((x) => x.trim())
    .filter(Boolean)
    .slice(0, 5)
})
const primaryDiagReason = computed(() => {
  const qwen = modelDiagRows.value.find((x) => String(x.model || '').includes('qwen3.6-plus'))
  if (qwen) return `qwen3.6-plus 已降级：${qwen.reason}`
  const first = modelDiagRows.value[0]
  if (!first) return '暂无异常'
  return `${first.model} 异常：${first.reason}`
})
const modelDiagRows = computed(() => {
  const rows = collaborativeReport.value?.modelResults || []
  const bad = rows.filter((x) => {
    const raw = String(x?.detail?.raw?.error || '')
    const status = String(x?.detail?.status || '').toLowerCase()
    return raw || ['error', 'failed', 'timeout', 'unavailable'].includes(status)
  })
  return bad.map((x) => {
    const raw = String(x?.detail?.raw?.error || '')
    const status = String(x?.detail?.status || '')
    let reason = raw || `服务状态：${status || '异常'}`
    let fix = '建议检查模型可用性与入参配置。'
    if (reason.includes('does not support http call')) {
      fix = '当前账号未开通该模型HTTP调用权限，请在DashScope控制台开通或更换可用模型。'
    } else if (reason.includes('The voice property is required')) {
      fix = '该模型是TTS语音模型，需提供voice参数与音频流程，或改为文本模型。'
    } else if (reason.includes('audio_pipeline_not_implemented')) {
      fix =
        '语音模型已改为无音频时自动跳过。若需启用，请补充 audioUrl/audioBase64 并接入完整音频链路。'
    } else if (reason.includes('AccessDenied') || reason.includes('synchronous calls')) {
      fix = '当前账号不支持同步调用该接口，需改异步任务模式或升级账号权限。'
    } else if (reason.includes('model_not_found')) {
      fix = '该模型名在当前供应商下不可用，请改用对应供应商SDK直连或开通权限。'
    }
    return { model: x.model, reason, fix }
  })
})
const localExplainFallback = {
  bar: '图中数值来自当前报告返回的指标字段；未提供的指标不会按零分解释。',
  pie: '图中占比按已有情绪标注汇总，不代表诊断或风险概率。',
  heatmap: '图中只显示服务端返回的时间点；空白表示没有可用记录。',
  trend: '图中按服务端提供的日期和分值绘制，不推断缺失日期的变化。',
  network: '当前没有可核验的因子关联数据，因此不生成关系图。',
  histogram: '分布仅概括服务端返回的对话分值，不代表临床量表结果。',
}
const PRINT_CHART_META = [
  {
    key: 'bar',
    title: '已有记录展示值',
    caption: '仅显示报告实际提供的规则展示值，空缺不按零分解释。',
  },
  { key: 'pie', title: '心理状态占比饼图', caption: '展示对话样本中的主要情绪结构占比。' },
  {
    key: 'heatmap',
    title: '记录热图',
    caption: '仅在存在可核验记录时展示，不能解释为疾病风险强度。',
  },
  {
    key: 'trend',
    title: '规则展示值时间序列',
    caption: '按实际日期展示近7天与30天的已有记录，缺失日期保留空缺。',
  },
  { key: 'network', title: '关联记录', caption: '当前没有可核验的因子关联数据，不生成关系结论。' },
  {
    key: 'histogram',
    title: '已有展示值分布',
    caption: '只统计有效记录，不包含空值，不代表临床量表分布。',
  },
  {
    key: 'compare',
    title: '解析来源记录',
    caption: '仅列实际提供的解析元信息，不将模型自述置信度解释为准确率。',
  },
]

function readReportIdentity() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    return user?.id == null ? '' : String(user.id)
  } catch {
    return ''
  }
}

const handleReportStorageChange = (event) => {
  if (
    !['user', 'token', 'access_token'].includes(event.key) ||
    readReportIdentity() === reportIdentity
  )
    return
  reportIdentity = readReportIdentity()
  reportLoadEpoch += 1
  reportLoadController?.abort()
  reportLoadController = null
  metadataController?.abort()
  collabEnabled.value = false
  interpretationEpoch += 1
  interpretationController?.abort()
  interpretationController = null
  interpretationLoading.value = false
  clearTimeout(processingRetryTimer)
  if (collabAbort) collabAbort.abort()
  reportData.value = null
  interpretationController?.abort()
  interpretationController = null
  interpretation.value = null
  interpretationLoading.value = false
  interpretationError.value = ''
  collaborativeReport.value = null
  disposeReportCharts()
  reportSnapshot = null
  printPayload.value = {
    generatedAt: '-',
    riskLevel: 'UNKNOWN',
    targetedAnalysis: [],
    indicators: [],
    charts: [],
  }
  printPreviewVisible.value = false
  reportVisible.value = false
  collabVisible.value = false
  shouldOpenReportAfterCollab.value = false
  clearTimeout(collabFadeTimer)
  clearTimeout(collabCloseTimer)
  exitPrintMode()
  loading.value = false
  refreshing.value = false
  collabRunning.value = false
  loadError.value = true
  processingError.value = '登录身份已变化，请重新进入报告页查看当前账号的数据。'
}

const fetchLatest = async ({ retryTrigger = false, sequence = null, attempt = 0 } = {}) => {
  if (unmounted) return
  if (sequence === null) {
    clearTimeout(processingRetryTimer)
    reportLoadController?.abort()
    sequence = ++reportLoadEpoch
    if (retryTrigger) reportProcessingTriggered = false
  }
  if (sequence !== reportLoadEpoch) return
  if (reportIdentity !== readReportIdentity()) {
    handleReportStorageChange({ key: 'user' })
    return
  }
  loading.value = true
  loadError.value = false
  processingError.value = ''
  const controller = new AbortController()
  reportLoadController = controller
  try {
    const res = await axios.get('/api/v1/report/analysis/latest', {
      timeout: 15000,
      params: { _t: Date.now() },
      headers: { 'Cache-Control': 'no-cache' },
      signal: controller.signal,
    })
    if (unmounted || sequence !== reportLoadEpoch) return
    if (res.data.status === 'processing') {
      if (!reportProcessingTriggered) {
        reportProcessingTriggered = true
        await axios.post(
          '/api/v1/report/analysis/trigger',
          {},
          { timeout: 15000, signal: controller.signal },
        )
        if (unmounted || sequence !== reportLoadEpoch) return
      }
      if (!shouldPollReportAgain(attempt)) {
        processingError.value = '报告仍在生成，已暂停自动检查。你可以稍后手动重试。'
        loadError.value = true
        return
      }
      const delay = getReportPollDelayMs(attempt)
      processingRetryTimer = setTimeout(
        () => fetchLatest({ sequence, attempt: attempt + 1 }),
        delay,
      )
      return
    }
    reportProcessingTriggered = false
    interpretationEpoch += 1
    interpretationController?.abort()
    interpretationController = null
    interpretation.value = null
    interpretationError.value = ''
    interpretationLoading.value = false
    reportData.value = res.data.data
    await nextTick()
    await renderCharts()
  } catch (error) {
    if (
      unmounted ||
      sequence !== reportLoadEpoch ||
      error?.name === 'CanceledError' ||
      error?.code === 'ERR_CANCELED'
    )
      return
    loadError.value = true
    ElMessage.error('报告加载失败')
  } finally {
    if (sequence === reportLoadEpoch) {
      loading.value = false
      if (reportLoadController === controller) reportLoadController = null
    }
  }
}

const requestInterpretation = async () => {
  if (latestReportRecordId.value === null || interpretationLoading.value) return
  interpretationController?.abort()
  const requestId = ++interpretationEpoch
  interpretationController = new AbortController()
  interpretationLoading.value = true
  interpretationError.value = ''
  interpretation.value = { status: 'loading', text: '' }
  const identity = reportIdentity
  try {
    const response = await axios.post(
      '/api/v1/report/ai-interpret',
      { recordId: latestReportRecordId.value },
      { timeout: 15000, signal: interpretationController.signal },
    )
    if (
      unmounted ||
      requestId !== interpretationEpoch ||
      identity !== reportIdentity ||
      identity !== readReportIdentity()
    )
      return
    interpretation.value = response?.data || {
      status: 'insufficient',
      source: 'local_rules',
      text: '暂无可用说明。',
    }
  } catch (error) {
    if (
      error?.code === 'ERR_CANCELED' ||
      unmounted ||
      requestId !== interpretationEpoch ||
      identity !== reportIdentity
    )
      return
    interpretation.value = { status: 'error', text: '' }
    interpretationError.value = error?.response?.data?.detail || '报告说明获取失败，请稍后重试。'
  } finally {
    if (requestId === interpretationEpoch && identity === reportIdentity) {
      interpretationLoading.value = false
      interpretationController = null
    }
  }
}

const refreshReport = async () => {
  if (!collabEnabled.value) {
    ElMessage.info('多模型协同未启用，可继续查看本地报告。')
    return
  }
  if (collabRunning.value) return
  refreshing.value = true
  await startCollaborativeAnalysis()
  refreshing.value = false
}

const toEmotionObject = (emotion) => {
  let emoObj = emotion
  // 兼容后端偶发返回 JSON 字符串的情况
  if (typeof emoObj === 'string') {
    try {
      emoObj = JSON.parse(emoObj)
    } catch {
      return null
    }
  }
  if (!emoObj || typeof emoObj !== 'object') return null

  return emoObj
}

const formatEmotionTags = (emotion) => {
  const emoObj = toEmotionObject(emotion)
  if (!emoObj) return []

  const order = ['joy', 'sadness', 'neutral', 'fear', 'anxiety', 'anger']
  /** @type {Array<[string, number]>} */
  const entries = order
    .map((k) => /** @type {[string, number]} */ ([k, Number(emoObj[k] || 0)]))
    .filter(([, v]) => Number.isFinite(v))

  const total = entries.reduce((sum, [, v]) => sum + Math.max(0, v), 0)
  if (total <= 0) return []

  // 按权重排序，优先展示占比更高的情绪，避免固定显示前三个维度导致“全是0”的错觉
  return [...entries]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([k, v]) => ({
      key: k,
      label: k,
      percent: Math.round(v * 100),
    }))
}

const chartExplanation = (key) => {
  const supplied =
    reportData.value?.chart_insights?.[key] || reportData.value?.chart_explanations?.[key]
  return supplied || localExplainFallback[key] || '暂无说明'
}

const initChart = (container, chart) => {
  if (unmounted || !container || !echartsRuntime) return null
  if (chart && !chart.isDisposed?.()) return chart
  const renderer = window.matchMedia('print').matches ? 'svg' : 'canvas'
  return echartsRuntime.init(container, 'xinyu-business', { renderer })
}

const loadEchartsRuntime = async () => {
  if (!echartsRuntimePromise) {
    echartsRuntimePromise = import('../../design/charts/report')
      .then((runtime) => {
        echartsRuntime = runtime
        return runtime
      })
      .catch((error) => {
        echartsRuntimePromise = null
        throw error
      })
  }
  return echartsRuntimePromise
}

const loadChartJsRuntime = async () => {
  if (!chartJsRuntimePromise) {
    chartJsRuntimePromise = import('../../design/charts/confidence')
      .then((runtime) => runtime.default)
      .catch((error) => {
        chartJsRuntimePromise = null
        throw error
      })
  }
  return chartJsRuntimePromise
}

const renderBar = () => {
  barChart = initChart(barRef.value, barChart)
  if (!barChart) return
  const scores = reportData.value?.scores || {}
  const risk = reportData.value?.risk || {}
  const x = ['情绪', '认知', '行为', '抑郁', '焦虑', '自杀风险']
  const y = [
    scores.emotion,
    scores.cognition,
    scores.behavior,
    risk.depression_confidence,
    risk.anxiety_confidence,
    risk.suicide_confidence,
  ].map((value) => (isPresentNumber(value) ? Number(value) : null))
  setLibraryChartOption(barChart, {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: x },
    yAxis: { type: 'value', max: 100 },
    series: [
      {
        type: 'bar',
        barWidth: '48%',
        data: y,
        itemStyle: { color: businessColor('data-primary') },
      },
    ],
  })
}

const renderPie = () => {
  pieChart = initChart(pieRef.value, pieChart)
  if (!pieChart) return
  const rows = dialogueRows.value.filter((row) => formatEmotionTags(row?.emotion_tags).length > 0)
  const bucket = { joy: 0, sadness: 0, fear: 0, anger: 0, neutral: 0 }
  rows.forEach((row) => {
    const emo = toEmotionObject(row.emotion_tags) || {}
    Object.keys(bucket).forEach((key) => {
      bucket[key] += Number(emo[key] || 0)
    })
  })
  setLibraryChartOption(pieChart, {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['35%', '68%'],
        label: { formatter: '{b}: {d}%' },
        data: Object.entries(bucket).map(([name, value]) => ({
          name,
          value: Number(value.toFixed(2)),
          itemStyle: { color: businessPalette.emotions[name] },
        })),
      },
    ],
  })
}

const renderHeatmap = () => {
  const heat = reportData.value?.trends?.heatmap || []
  heatmapChart = initChart(heatmapRef.value, heatmapChart)
  if (!heatmapChart) return
  const dims = ['depression', 'anxiety', 'suicide']
  const values = []
  heat.forEach((item, x) => {
    dims.forEach((dim, y) => {
      if (isPresentNumber(item[dim])) values.push([x, y, Number(item[dim])])
    })
  })
  setLibraryChartOption(heatmapChart, {
    tooltip: { position: 'top' },
    xAxis: { type: 'category', data: heat.map((x) => x.date.slice(5)) },
    yAxis: { type: 'category', data: ['抑郁', '焦虑', '自杀'] },
    visualMap: {
      min: 0,
      max: 100,
      inRange: { color: businessPalette.sequential },
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
    },
    series: [{ type: 'heatmap', data: values }],
  })
}

const renderTrend = () => {
  const seven = reportData.value?.trends?.seven_days || []
  const thirty = reportData.value?.trends?.thirty_days || []
  trendChart = initChart(trendRef.value, trendChart)
  if (!trendChart) return
  setLibraryChartOption(trendChart, {
    tooltip: { trigger: 'axis' },
    legend: { data: ['7天', '30天'] },
    xAxis: { type: 'category', data: thirty.map((x) => x.date.slice(5)) },
    yAxis: { type: 'value', min: 0, max: 100 },
    series: [
      {
        name: '30天',
        type: 'line',
        smooth: true,
        connectNulls: false,
        data: thirty.map((row) => finiteNumberOrNull(row.score)),
        lineStyle: { width: 3 },
      },
      {
        name: '7天',
        type: 'line',
        smooth: true,
        connectNulls: false,
        data: thirty.map((day) =>
          finiteNumberOrNull(seven.find((item) => item.date === day.date)?.score),
        ),
        lineStyle: { width: 3, type: 'dashed' },
      },
    ],
  })
}

const renderHistogram = () => {
  histogramChart = initChart(histogramRef.value, histogramChart)
  if (!histogramChart) return
  const rawScores = dialogueRows.value
    .map((row) => finiteNumberOrNull(row?.score))
    .filter((value) => value !== null && value >= 0 && value <= 100)
  const bins = [0, 0, 0, 0, 0]
  rawScores.forEach((s) => {
    if (s < 20) bins[0] += 1
    else if (s < 40) bins[1] += 1
    else if (s < 60) bins[2] += 1
    else if (s < 80) bins[3] += 1
    else bins[4] += 1
  })
  setLibraryChartOption(histogramChart, {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['0-20', '20-40', '40-60', '60-80', '80-100'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: bins, itemStyle: { color: businessColor('data-primary') } }],
  })
}

const renderCharts = async () => {
  const identity = reportIdentity
  const epoch = reportLoadEpoch
  if (!reportData.value) return
  if (!hasMetricData.value && barChart) {
    barChart.dispose()
    barChart = null
  }
  if (!hasEmotionSamples.value && pieChart) {
    pieChart.dispose()
    pieChart = null
  }
  if (!hasDistributionSamples.value && histogramChart) {
    histogramChart.dispose()
    histogramChart = null
  }
  if (!hasHeatmapData.value && heatmapChart) {
    heatmapChart.dispose()
    heatmapChart = null
  }
  if (!hasTrendData.value && trendChart) {
    trendChart.dispose()
    trendChart = null
  }
  if (!hasAnyChartData.value) return
  await loadEchartsRuntime()
  if (
    unmounted ||
    epoch !== reportLoadEpoch ||
    identity !== readReportIdentity() ||
    !reportData.value ||
    !hasAnyChartData.value
  )
    return
  const nextSnapshot = {
    updated_at: reportData.value?.updated_at,
    msgCount: reportData.value?.source?.message_count,
    risk: reportData.value?.risk,
  }
  console.log('[Report] renderCharts snapshot:', nextSnapshot)
  const prev = reportSnapshot
  reportSnapshot = nextSnapshot
  const strategy = computeRenderStrategy(prev, nextSnapshot)
  if (strategy === 'skip') return
  if (strategy === 'incremental') {
    // 大会话优先增量更新核心时序图，避免每次重建全部图造成“视觉无差异”与性能浪费。
    if (hasTrendData.value) renderTrend()
    if (hasHeatmapData.value) renderHeatmap()
    if (hasEmotionSamples.value) renderPie()
    if (hasDistributionSamples.value) renderHistogram()
    return
  }
  if (hasMetricData.value) renderBar()
  if (hasEmotionSamples.value) renderPie()
  if (hasDistributionSamples.value) renderHistogram()
  if (hasHeatmapData.value) renderHeatmap()
  if (hasTrendData.value) renderTrend()
}

const safeExportChart = (chart) => {
  if (!chart || chart.isDisposed?.()) return ''
  try {
    return chart.getDataURL({
      type: 'png',
      pixelRatio: 2.5,
      backgroundColor: businessColor('surface'),
      excludeComponents: ['toolbox'],
    })
  } catch {
    return ''
  }
}

const buildPrintPayload = () => {
  if (
    reportIdentity !== readReportIdentity() ||
    (!reportData.value && !collaborativeReport.value)
  ) {
    printPayload.value = {
      generatedAt: '-',
      riskLevel: 'UNKNOWN',
      targetedAnalysis: [],
      indicators: [],
      charts: [],
    }
    return
  }
  const scores = reportData.value?.scores || {}
  const risk = reportData.value?.risk || {}
  const interventions = Array.isArray(reportData.value?.interventions)
    ? reportData.value.interventions
    : []
  const collab = collaborativeReport.value || {}
  const targetedAnalysis = [
    collab.executiveSummary,
    collab.collaborativeConclusion,
    interventions.length ? `建议措施：${interventions.join('；')}` : '',
  ].filter((x) => typeof x === 'string' && x.trim())

  const chartImageMap = {
    bar: safeExportChart(barChart),
    pie: safeExportChart(pieChart),
    heatmap: safeExportChart(heatmapChart),
    trend: safeExportChart(trendChart),
    network: safeExportChart(networkChart),
    histogram: safeExportChart(histogramChart),
    compare: safeExportChart(collabCompareChart),
  }

  const charts = PRINT_CHART_META.map((meta) => ({
    ...meta,
    analysis:
      meta.key === 'compare' ? '该图显示本次协同报告返回的模型字段。' : chartExplanation(meta.key),
    image: chartImageMap[meta.key] || '',
  })).filter((item) => item.image)

  printPayload.value = {
    generatedAt: new Date().toLocaleString(),
    riskLevel: riskLevel.value,
    targetedAnalysis,
    indicators: [
      { label: '情绪维度', value: displayValue(scores.emotion) },
      { label: '认知维度', value: displayValue(scores.cognition) },
      { label: '行为维度', value: displayValue(scores.behavior) },
      { label: '抑郁字段', value: displayValue(risk.depression_confidence) },
      { label: '焦虑字段', value: displayValue(risk.anxiety_confidence) },
      { label: '自杀风险字段', value: displayValue(risk.suicide_confidence) },
    ],
    charts,
  }
}

const resetCollabState = () => {
  collabProgress.value = 0
  collabCurrentModel.value = ''
  collabCurrentStage.value = ''
  collabEtaSec.value = 0
  collabMiddle.value = []
  collabSteps.value = []
}

const renderCollabFlow = async () => {
  if (!collabFlowRef.value || !collabSteps.value.length) return
  const identity = reportIdentity
  const epoch = reportLoadEpoch
  await loadEchartsRuntime()
  if (
    unmounted ||
    epoch !== reportLoadEpoch ||
    identity !== readReportIdentity() ||
    !collabFlowRef.value
  )
    return
  collabFlowChart = initChart(collabFlowRef.value, collabFlowChart)
  if (!collabFlowChart) return
  const colorByStatus = (status) => {
    if (status === 'done') return businessColor('data-risk-low')
    if (status === 'running') return businessColor('data-risk-mid')
    if (status === 'error') return businessColor('data-risk-high')
    return businessColor('text-secondary')
  }
  const nodes = collabSteps.value.map((step, index) => ({
    id: step.model,
    name: step.model,
    x: 80 + index * 130,
    y: 120 + (index % 2) * 50,
    symbolSize: 46,
    itemStyle: { color: colorByStatus(step.status) },
    label: { show: true, fontSize: 12, formatter: step.model },
  }))
  setLibraryChartOption(collabFlowChart, {
    animationDurationUpdate: 200,
    xAxis: { show: false, min: 0, max: Math.max(260, nodes.length * 130) },
    yAxis: { show: false, min: 0, max: 260 },
    series: [{ type: 'graph', coordinateSystem: null, roam: false, data: nodes, links: [] }],
  })
}

const renderCollabConfidence = async () => {
  if (!collaborativeReport.value) return
  const canvas = collabConfidenceCanvasRef.value
  if (!canvas || !hasModelConfidenceRows.value) return
  const identity = reportIdentity
  const epoch = reportLoadEpoch
  const Chart = await loadChartJsRuntime()
  if (
    unmounted ||
    epoch !== reportLoadEpoch ||
    identity !== readReportIdentity() ||
    canvas !== collabConfidenceCanvasRef.value ||
    !collaborativeReport.value
  )
    return
  if (collabConfidenceChart) {
    collabConfidenceChart.destroy()
    collabConfidenceChart = null
  }
  const rows = collaborativeReport.value.modelResults || []
  const labels = rows.map((x) => normalizeModelName(x.model))
  const wrapLabel = (name) => {
    const text = String(name || '')
    if (text.length <= 10) return text
    const chunks = []
    for (let i = 0; i < text.length; i += 10) {
      chunks.push(text.slice(i, i + 10))
    }
    return chunks
  }
  const values = rows.map((x) => (isPresentNumber(x.confidence) ? Number(x.confidence) : null))
  collabConfidenceChart = new Chart(
    canvas,
    createLibraryChartJsConfig({
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: businessColor('data-primary'),
            borderRadius: 6,
            barThickness: 28,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        responsive: true,
        animation: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) =>
                isPresentNumber(ctx.raw)
                  ? `置信度：${Math.round(Number(ctx.raw) * 100)}%`
                  : '置信度：暂无数据',
            },
          },
        },
        scales: {
          y: {
            min: 0,
            max: 1,
            ticks: {
              callback: (value) => `${Math.round(Number(value) * 100)}%`,
            },
            grid: { display: false },
          },
          x: {
            ticks: {
              maxRotation: 0,
              minRotation: 0,
              color: businessColor('text-secondary'),
              font: { size: 11 },
              callback: (_, index) => wrapLabel(labels[index]),
            },
            grid: { display: false },
          },
        },
      },
      plugins: [
        {
          id: 'barValueLabelPlugin',
          afterDatasetsDraw(chart) {
            const { ctx } = chart
            const meta = chart.getDatasetMeta(0)
            ctx.save()
            ctx.fillStyle = businessColor('data-text')
            ctx.font = libraryChartFont()
            ctx.textAlign = 'center'
            meta.data.forEach((bar, index) => {
              const value = values[index]
              if (!isPresentNumber(value)) return
              ctx.fillText(`${Math.round(Number(value) * 100)}%`, bar.x, bar.y - 8)
            })
            ctx.restore()
          },
        },
      ],
    }),
  )
}

const renderModelCompare = async () => {
  const rows = modelConfidenceRows.value
  if (!rows.length || !collabCompareRef.value) return
  const identity = reportIdentity
  const epoch = reportLoadEpoch
  await loadEchartsRuntime()
  if (
    unmounted ||
    epoch !== reportLoadEpoch ||
    identity !== readReportIdentity() ||
    !collabCompareRef.value
  )
    return
  collabCompareChart = initChart(collabCompareRef.value, collabCompareChart)
  if (!collabCompareChart) return
  if (compareChartType.value === 'radar') {
    collabCompareChart.clear()
    setLibraryChartOption(
      collabCompareChart,
      {
        tooltip: { trigger: 'item' },
        radar: {
          radius: '62%',
          indicator: rows.map((x) => ({ name: x.model, max: 1 })),
          axisName: { color: businessColor('text-secondary'), fontSize: 12 },
        },
        series: [
          {
            type: 'radar',
            areaStyle: { color: businessAlpha('data-primary', 0.2) },
            lineStyle: { color: businessColor('data-primary'), width: 2 },
            data: [
              {
                value: rows.map((x) =>
                  isPresentNumber(x.confidence) ? Number(x.confidence) : null,
                ),
                name: '置信度',
              },
            ],
          },
        ],
      },
      true,
    )
    return
  }
  collabCompareChart.clear()
  setLibraryChartOption(
    collabCompareChart,
    {
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const p = Array.isArray(params) ? params[0] : params
          return `${p.name}<br/>置信度：${Math.round(Number(p.value) * 100)}%`
        },
      },
      xAxis: {
        type: 'category',
        data: rows.map((x) => x.model),
        axisLabel: { rotate: 15, color: businessColor('text-secondary'), fontSize: 12 },
      },
      yAxis: { type: 'value', min: 0, max: 1 },
      series: [
        {
          type: 'bar',
          data: rows.map((x) => (isPresentNumber(x.confidence) ? Number(x.confidence) : null)),
          barWidth: '50%',
          itemStyle: { color: businessColor('data-primary'), borderRadius: [6, 6, 0, 0] },
          emphasis: { itemStyle: { color: businessColor('data-primary') } },
        },
      ],
    },
    true,
  )
}

const updateCollabStep = (payload) => {
  const normalizedModel = normalizeModelName(payload.model)
  if (!normalizedModel) return
  const idx = collabSteps.value.findIndex((x) => x.model === normalizedModel)
  const statusTextMap = {
    queued: '等待中',
    running: '运行中',
    done: '已完成',
    degraded: '降级完成',
    skipped: '已跳过',
    error: '异常',
  }
  const existing = idx >= 0 ? collabSteps.value[idx] : { model: normalizedModel }
  const next = {
    ...existing,
    ...payload,
    model: normalizedModel,
    statusText: statusTextMap[payload.status] || existing.statusText || '处理中',
  }
  if (idx >= 0) collabSteps.value[idx] = next
  else collabSteps.value.push(next)
  renderCollabFlow()
}

const fetchCurrentModelMeta = async () => {
  metadataController?.abort()
  const controller = new AbortController()
  metadataController = controller
  const identity = reportIdentity
  const [model, health] = await Promise.allSettled([
    axios.get('/api/v1/model/current', {
      timeout: 8000,
      signal: controller.signal,
      params: { _t: Date.now() },
      headers: { 'Cache-Control': 'no-cache' },
    }),
    axios.get('/api/v1/report/analysis/collab/health', {
      timeout: 8000,
      signal: controller.signal,
    }),
  ])
  if (unmounted || controller.signal.aborted || identity !== readReportIdentity()) return
  const data = model.status === 'fulfilled' ? model.value?.data?.data || {} : {}
  if (typeof data.model_name === 'string' && data.model_name)
    primaryModelName.value = data.model_name
  if (typeof data.legacy_alias === 'string' && data.legacy_alias)
    legacyPrimaryModelAlias.value = data.legacy_alias
  collabEnabled.value =
    health.status === 'fulfilled' && health.value?.data?.collaboration_enabled === true
}

const startCollaborativeAnalysis = async () => {
  if (!collabEnabled.value || collabRunning.value) return
  clearTimeout(collabFadeTimer)
  clearTimeout(collabCloseTimer)
  collabVisible.value = true
  collabFading.value = false
  collabRunning.value = true
  reportVisible.value = false
  shouldOpenReportAfterCollab.value = false
  collaborativeReport.value = null
  resetCollabState()
  await nextTick()
  renderCollabFlow()
  const token = localStorage.getItem('token')
  if (collabAbort) collabAbort.abort()
  collabAbort = new AbortController()
  try {
    const submitRes = await fetch(axios.getUri({ url: '/api/v1/report/analysis/collab/submit' }), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({}),
      signal: collabAbort.signal,
    })
    if (!submitRes.ok) throw new Error('collab_submit_failed')
    const submitPayload = await submitRes.json()
    collabTaskId.value = submitPayload.taskId

    const streamRes = await fetch(
      axios.getUri({
        url: `/api/v1/report/analysis/collab/stream/${collabTaskId.value}?_t=${Date.now()}`,
      }),
      {
        method: 'GET',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          'Cache-Control': 'no-cache',
        },
        signal: collabAbort.signal,
      },
    )
    if (!streamRes.ok || !streamRes.body) throw new Error('collab_stream_failed')
    const reader = streamRes.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parsed = parseSseBlocks(buf)
      buf = parsed.rest
      for (const unit of parsed.events) {
        const event = unit.event
        const data = unit.data
        if (event === 'step') {
          collabProgress.value = data.progress || collabProgress.value
          collabCurrentModel.value = normalizeModelName(data.model || collabCurrentModel.value)
          collabCurrentStage.value = data.stage || collabCurrentStage.value
          collabEtaSec.value = Number(data.etaSec || 0)
          updateCollabStep(data)
          if (data.summary) {
            collabMiddle.value.unshift({
              model: normalizeModelName(data.model),
              summary: data.summary,
            })
            collabMiddle.value = collabMiddle.value.slice(0, 12)
          }
        } else if (event === 'retry') {
          ElMessage.warning(`${data.model} 正在重试（第${data.attempt}次）`)
        } else if (event === 'done') {
          collabProgress.value = 100
          collabRunning.value = false
          const report = data.report || {}
          const modelResults = (report.modelResults || []).map((x) => ({
            ...x,
            model: normalizeModelName(x.model),
          }))
          collaborativeReport.value = { ...report, modelResults }
          shouldOpenReportAfterCollab.value = true
          if (!selectedModels.value.length) {
            selectedModels.value = modelResults.map((x) => x.model)
          }
          renderModelCompare()
          ElMessage.success('多模型协同分析完成')
          collabFadeTimer = setTimeout(() => {
            if (unmounted) return
            collabFading.value = true
          }, 3000)
          collabCloseTimer = setTimeout(() => {
            if (unmounted) return
            collabVisible.value = false
            collabFading.value = false
          }, 3400)
        } else if (event === 'error') {
          collabRunning.value = false
          shouldOpenReportAfterCollab.value = false
          ElMessage.error(data.message || '协同分析失败')
        }
      }
    }
    collabRunning.value = false
  } catch (error) {
    if (unmounted) return
    collabRunning.value = false
    ElMessage.error('协同分析启动失败')
  }
}

const handleCollabDialogClosed = () => {
  if (shouldOpenReportAfterCollab.value && collaborativeReport.value) {
    reportVisible.value = true
  }
  collabFading.value = false
}

const handleReportDialogClosed = () => {
  // 保留结果数据，方便用户再次打开报告时复用
  if (collabConfidenceChart) {
    collabConfidenceChart.destroy()
    collabConfidenceChart = null
  }
}

const handleResize = () => {
  if (barChart) barChart.resize()
  if (pieChart) pieChart.resize()
  if (heatmapChart) heatmapChart.resize()
  if (trendChart) trendChart.resize()
  if (networkChart) networkChart.resize()
  if (histogramChart) histogramChart.resize()
  if (collabFlowChart) collabFlowChart.resize()
  if (collabConfidenceChart) collabConfidenceChart.resize()
  if (collabCompareChart) collabCompareChart.resize()
}

const handleBeforePrint = () => {
  if (reportIdentity !== readReportIdentity()) {
    handleReportStorageChange({ key: 'user' })
    return
  }
  enterPrintMode()
  // Native beforeprint does not await promises. Export already-rendered charts only.
  buildPrintPayload()
}

const handleAfterPrint = () => {
  exitPrintMode()
}

const waitForFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve()))

const preparePrintPayload = async () => {
  const identity = reportIdentity
  const epoch = reportLoadEpoch
  if (identity !== readReportIdentity() || (!reportData.value && !collaborativeReport.value))
    return false
  await renderCharts()
  await renderModelCompare()
  await nextTick()
  await waitForFrame()
  if (unmounted || epoch !== reportLoadEpoch || identity !== readReportIdentity()) return false
  buildPrintPayload()
  await nextTick()
  await waitForFrame()
  return !unmounted && epoch === reportLoadEpoch && identity === readReportIdentity()
}

const enterPrintMode = () => {
  document.body.classList.add('report-printing')
}

const exitPrintMode = () => {
  document.body.classList.remove('report-printing')
}

const openPrintPreview = async () => {
  if (!(await preparePrintPayload())) return
  printPreviewVisible.value = true
}

const downloadReport = async () => {
  if (!(await preparePrintPayload())) return
  enterPrintMode()
  window.print()
}

const confirmPrintFromPreview = async () => {
  printPreviewVisible.value = false
  await nextTick()
  await downloadReport()
}

const shareReport = async () => {
  try {
    if (navigator.share) {
      await navigator.share({ title: '我的心理报告', text: '查看我的心理报告' })
    } else {
      await navigator.clipboard.writeText(window.location.href)
      ElMessage.success('链接已复制')
    }
  } catch (error) {
    ElMessage.warning('分享已取消')
  }
}

onMounted(async () => {
  window.addEventListener('storage', handleReportStorageChange)
  void fetchCurrentModelMeta()
  await fetchLatest()
  if (unmounted) return
  assistantEventHandler = () => {
    if (!loading.value) fetchLatest()
  }
  window.addEventListener('assistant-message-saved', assistantEventHandler)
  window.addEventListener('resize', handleResize)
  window.addEventListener('beforeprint', handleBeforePrint)
  window.addEventListener('afterprint', handleAfterPrint)
})

watch(
  [modelConfidenceRows, compareChartType],
  async () => {
    await nextTick()
    await renderModelCompare()
  },
  { deep: true },
)

watch(collaborativeReport, async () => {
  await nextTick()
  await renderModelCompare()
})

watch(reportVisible, async (visible) => {
  if (!visible) return
  await nextTick()
  await renderCollabConfidence()
})

const disposeReportCharts = () => {
  for (const chart of [
    barChart,
    pieChart,
    heatmapChart,
    trendChart,
    networkChart,
    histogramChart,
    collabFlowChart,
    collabCompareChart,
  ])
    chart?.dispose()
  collabConfidenceChart?.destroy()
  barChart =
    pieChart =
    heatmapChart =
    trendChart =
    networkChart =
    histogramChart =
    collabFlowChart =
    collabCompareChart =
      null
  collabConfidenceChart = null
}

onBeforeUnmount(() => {
  unmounted = true
  metadataController?.abort()
  reportLoadEpoch += 1
  reportLoadController?.abort()
  reportLoadController = null
  interpretationEpoch += 1
  interpretationController?.abort()
  interpretationController = null
  interpretationLoading.value = false
  clearTimeout(processingRetryTimer)
  clearTimeout(collabFadeTimer)
  clearTimeout(collabCloseTimer)
  if (esAbort) esAbort.abort()
  if (collabAbort) collabAbort.abort()
  if (assistantEventHandler)
    window.removeEventListener('assistant-message-saved', assistantEventHandler)
  window.removeEventListener('storage', handleReportStorageChange)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('beforeprint', handleBeforePrint)
  window.removeEventListener('afterprint', handleAfterPrint)
  exitPrintMode()
  if (realtimeTimer) clearInterval(realtimeTimer)
  disposeReportCharts()
})
</script>

<style scoped>
.report-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.report-empty-copy {
  margin: 0 0 var(--space-4);
  color: var(--text-secondary);
  line-height: 1.6;
}
.report-empty :deep(.el-empty) {
  min-height: 320px;
}
.report-empty .business-actions {
  justify-content: center;
}
.collab-safety-note {
  margin-bottom: 2px;
}
.interpretation-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 4px 0 10px;
}
.interpretation-heading h3 {
  margin: 0;
  font-size: 18px;
}
.interpretation-heading p {
  margin: 5px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
@media (max-width: 600px) {
  .interpretation-heading {
    align-items: stretch;
    flex-direction: column;
  }
  .interpretation-heading :deep(.el-button) {
    min-height: 44px;
    margin: 0;
  }
}
.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: nowrap;
}
.actions :deep(.el-button) {
  min-height: 36px;
  margin: 0;
}
.collab-status {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}
.page-title {
  margin: 0;
  font-size: 24px;
}
.page-desc {
  margin: 6px 0 0;
  color: var(--text-secondary);
}
.summary-card,
.chart-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px 0 color-mix(in srgb, var(--gray-900) 8%, transparent);
}
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(320px, 1fr));
  gap: 12px;
}
.chart-box {
  width: 100%;
  height: 320px;
}
.chart-empty {
  min-height: 180px;
  display: grid;
  place-items: center;
  padding: 18px;
  color: var(--text-secondary);
  text-align: center;
  background: var(--surface-subtle);
  border-radius: 8px;
}
.flow-box {
  height: 160px;
}
.model-compare-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.model-compare-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.chart-ai {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.5;
  font-size: 13px;
  background: var(--surface-subtle);
  border-radius: 8px;
  padding: 8px 10px;
}
.risk-low {
  color: var(--success-text);
}
.risk-medium {
  color: var(--warning-text);
}
.risk-high {
  color: var(--danger-text);
}
.collab-top {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}
.collab-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}
.collab-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.collab-flow-card {
  grid-column: 1 / -1;
}
.collab-step-list {
  max-height: 122px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.collab-step-row {
  display: grid;
  grid-template-columns: 70px 1fr 170px;
  gap: 6px;
  align-items: center;
}
.collab-step-model {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--text-primary);
}
.collab-step-stage {
  font-size: 12px;
  color: var(--text-secondary);
}
.middle-list {
  max-height: 122px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.middle-row {
  background: var(--surface-subtle);
  border-radius: 8px;
  padding: 6px 8px;
}
.middle-row p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}
.collab-dialog {
  transition:
    opacity 0.4s ease,
    transform 0.4s ease;
  opacity: 1;
}
.collab-dialog.is-fading {
  opacity: 0;
  transform: translateY(8px);
}
.report-dialog-body {
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}
.modern-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 16px;
}
.modern-two-col-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.core-stack-grid {
  grid-template-columns: 1fr;
  gap: 20px;
}
.modern-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--brand-500) 8%, transparent);
  padding: 16px;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.modern-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px color-mix(in srgb, var(--brand-500) 12%, transparent);
}
.metric-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 104px;
}
.metric-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}
.metric-time {
  font-size: 16px;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.4;
}
.metric-progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: var(--brand-50);
  overflow: hidden;
}
.metric-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--brand-600), var(--brand-600));
}
.report-section {
  min-height: 220px;
}
.section-title {
  margin: 0 0 12px;
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 600;
}
.summary-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.summary-alert {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
  background: var(--danger-100);
  border: 1px solid var(--danger-100);
  padding: 8px 10px;
  margin-bottom: 12px;
}
.summary-alert-icon {
  font-size: 14px;
}
.summary-alert-text {
  font-size: 13px;
  color: var(--danger-text);
  font-weight: 600;
}
.summary-list li {
  color: var(--text-secondary);
  line-height: 1.65;
  font-size: 14px;
}
.conclusion-highlight {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border-radius: 8px;
  background: var(--warning-100);
  border: 1px solid var(--warning-100);
}
.warn-icon {
  width: 20px;
  height: 20px;
  line-height: 20px;
  text-align: center;
  border-radius: 50%;
  background: var(--warning-text);
  color: var(--surface);
  font-size: 13px;
  flex-shrink: 0;
  margin-top: 1px;
}
.report-paragraph {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.65;
  font-size: 14px;
}
.confidence-canvas-wrap {
  height: 260px;
}
.confidence-canvas {
  width: 100%;
  height: 100%;
}
.core-detail-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.core-detail-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  transition: background-color 0.2s ease;
}
.core-detail-item:hover {
  background: var(--brand-50);
}
.core-detail-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.model-cell {
  color: var(--text-primary);
  font-weight: 500;
  font-size: 13px;
  line-height: 1.4;
}
.summary-cell {
  margin: 0;
  line-height: 1.5;
  white-space: normal;
  word-break: break-word;
  color: var(--text-secondary);
  font-size: 13px;
}
.table-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 150px;
  width: min(420px, 100%);
}
.table-progress-label {
  min-width: 40px;
  color: var(--brand-600);
  font-weight: 600;
}
.table-progress-track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--brand-50);
}
.table-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--brand-600);
}
.diag-section {
  min-height: 170px;
}
.diag-warning-box {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid var(--warning-100);
  background: var(--warning-100);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.diag-warning-icon {
  font-size: 14px;
  line-height: 1.2;
}
.diag-warning-text strong {
  display: block;
  color: var(--warning-text);
  font-size: 13px;
}
.diag-warning-text p {
  margin: 4px 0 0;
  color: var(--warning-text);
  font-size: 12px;
  line-height: 1.5;
}
.diag-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.diag-row {
  display: grid;
  grid-template-columns: 220px 1fr 1fr;
  gap: 12px;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--surface);
  transition: background-color 0.2s ease;
}
.diag-row:hover {
  background: var(--surface-subtle);
}
.diag-model {
  font-size: 12px;
  font-weight: 600;
  color: var(--danger-text);
  background: var(--danger-100);
  border: 1px solid var(--danger-100);
  border-radius: 999px;
  padding: 4px 10px;
  width: fit-content;
}
.diag-reason {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.diag-fix {
  color: var(--brand-600);
  font-size: 12px;
  line-height: 1.5;
}
.diag-empty {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.emotion-tag-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  line-height: 1.6;
}
.emotion-empty {
  color: var(--text-secondary);
  font-size: 12px;
}
.emotion-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid transparent;
}
.emotion-sep {
  color: var(--border);
  font-size: 12px;
}
.chip-neutral {
  background: var(--surface-subtle);
  color: var(--text-secondary);
  border-color: var(--border);
}
.chip-anxiety {
  background: var(--danger-100);
  color: var(--danger-text);
  border-color: var(--danger-100);
}
.chip-sadness {
  background: var(--warning-100);
  color: var(--warning-text);
  border-color: var(--warning-100);
}
.chip-fear {
  background: var(--brand-50);
  color: var(--brand-600);
  border-color: var(--brand-100);
}
.chip-anger {
  background: var(--brand-50);
  color: var(--brand-600);
  border-color: var(--brand-100);
}
.chip-joy {
  background: var(--accent-sage-soft);
  color: var(--success-text);
  border-color: var(--accent-sage-soft);
}
.print-report {
  display: none;
}
.print-header h1 {
  margin: 0;
  font-size: 22px;
  color: var(--text-primary);
  letter-spacing: 0.3px;
}
.print-header p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-primary);
}
.print-section {
  margin-top: 14px;
}
.print-section h2 {
  margin: 0 0 8px;
  padding-left: 8px;
  border-left: 3px solid var(--brand-600);
  color: var(--text-primary);
  font-size: 16px;
}
.print-paragraph {
  margin: 6px 0;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.7;
  text-align: justify;
}
.print-indicator-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, 1fr));
  gap: 6px;
}
.print-indicator-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  background: var(--surface-subtle);
}
.print-indicator-label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
}
.print-indicator-value {
  display: block;
  margin-top: 4px;
  font-size: 14px;
  color: var(--text-primary);
}
.print-chart-card {
  margin-top: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  break-inside: avoid;
  page-break-inside: avoid;
}
.print-chart-card h3 {
  margin: 0;
  font-size: 14px;
  color: var(--text-primary);
}
.print-caption {
  margin: 6px 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.print-chart-image {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 8px;
  object-fit: contain;
  background: var(--surface);
}
.print-chart-missing {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--warning-text);
}
.print-analysis {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: var(--text-primary);
  line-height: 1.65;
  text-align: justify;
}
.preview-shell {
  max-height: calc(88vh - 140px);
  overflow: auto;
  background: var(--border);
  border-radius: 10px;
  padding: 14px;
}
.print-report-preview {
  display: block;
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  padding: 5mm;
  box-sizing: border-box;
  background: var(--surface);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--brand-500) 15%, transparent);
}
.preview-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

:global(body.report-printing *) {
  visibility: hidden !important;
}

:global(body.report-printing .report-container),
:global(body.report-printing .report-container *) {
  visibility: visible !important;
}

:global(body.report-printing .report-container) {
  position: fixed !important;
  inset: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  margin: 0 !important;
  padding: 0 !important;
  background: var(--surface) !important;
  z-index: 2147483647 !important;
}

:deep(.report-dialog .el-dialog) {
  width: min(1200px, 95vw) !important;
  max-height: 90vh;
  margin-top: 5vh;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--surface);
}

:deep(.report-dialog .el-dialog__header) {
  height: 56px;
  min-height: 56px;
  padding: 0 18px;
  margin-right: 0;
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--surface-subtle);
  background: var(--surface);
}

:deep(.report-dialog .el-dialog__title) {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

:deep(.report-dialog .el-dialog__body) {
  padding: 16px 18px 0;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--surface);
  scrollbar-gutter: stable;
}

:deep(.report-dialog .el-dialog__body::-webkit-scrollbar) {
  width: 8px;
}

:deep(.report-dialog .el-dialog__body::-webkit-scrollbar-thumb) {
  border-radius: 999px;
  background: color-mix(in srgb, var(--brand-500) 35%, transparent);
}

:deep(.report-dialog .el-dialog__body::-webkit-scrollbar-track) {
  background: var(--surface-subtle);
}

:deep(.collab-dialog .el-dialog) {
  width: min(960px, 92vw) !important;
  margin-top: 6vh;
  max-height: 80vh;
}

:deep(.collab-dialog .el-dialog__header) {
  padding: 12px 14px 8px;
}

:deep(.collab-dialog .el-dialog__body) {
  padding: 8px 14px 12px;
  max-height: calc(80vh - 84px);
  overflow: hidden;
}

:deep(.collab-dialog .el-card__header) {
  padding: 8px 10px;
}

:deep(.collab-dialog .el-card__body) {
  padding: 8px 10px;
}

@media (max-width: 768px) {
  .header-container {
    align-items: stretch;
    flex-direction: column;
  }
  .actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }
  .actions :deep(.el-button) {
    width: 100%;
    min-height: 44px;
    margin: 0;
  }
  .collab-status {
    grid-column: 1 / -1;
    justify-content: center;
    min-height: 36px;
  }
  .charts-grid {
    grid-template-columns: 1fr;
  }
  .chart-box {
    height: 280px;
  }
  .model-compare-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .model-compare-actions {
    width: 100%;
  }
  .collab-grid {
    grid-template-columns: 1fr;
  }
  .modern-metric-grid {
    grid-template-columns: 1fr;
  }
  .modern-two-col-grid {
    grid-template-columns: 1fr;
  }
  .core-detail-top {
    flex-direction: column;
    align-items: flex-start;
  }
  .table-progress-row {
    width: 100%;
  }
  .diag-row {
    grid-template-columns: 1fr;
  }
  .metric-time {
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .collab-step-row {
    grid-template-columns: 76px 1fr;
  }
  .collab-step-stage {
    grid-column: span 2;
  }
  .confidence-canvas-wrap {
    height: 240px;
  }
  :deep(.collab-dialog .el-dialog__body) {
    max-height: calc(80vh - 84px);
    overflow: auto;
  }
  :deep(.report-dialog .el-dialog__body) {
    padding: 12px 12px 0;
    max-height: calc(90vh - 56px);
    overflow-y: auto;
  }
}

@media (max-width: 390px) {
  .header-container {
    gap: 12px;
  }
  .page-title {
    font-size: 20px;
    overflow-wrap: anywhere;
  }
  .collab-meta {
    flex-direction: column;
    gap: 6px;
  }
}

@media print {
  @page {
    size: A4 portrait;
    margin: 5mm;
  }
  .report-container {
    display: block;
    padding: 0;
    margin: 0;
    color: var(--text-primary);
    background: var(--surface);
  }
  .report-container > *:not(.print-report) {
    display: none !important;
  }
  .print-report {
    display: block;
    width: 100%;
    min-height: 287mm;
    box-sizing: border-box;
    font-size: 12px;
    line-height: 1.6;
  }
  .print-paragraph,
  .print-analysis {
    orphans: 3;
    widows: 3;
  }
  .print-section {
    margin-top: 12px;
    break-inside: avoid;
    page-break-inside: avoid;
  }
  .print-indicator-grid {
    grid-template-columns: repeat(3, minmax(110px, 1fr));
  }
  .print-chart-image {
    max-height: 208mm;
    page-break-inside: avoid;
  }
}
</style>
