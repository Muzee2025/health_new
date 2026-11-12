/** All chart values resolve from tokens.css at runtime; load CSS before calling. */
export const EMOTION_FIELDS = Object.freeze([
  'joy',
  'sadness',
  'neutral',
  'fear',
  'anxiety',
  'anger',
])
export const PALETTE_TOKENS = Object.freeze([
  'brand-500',
  'brand-600',
  'success',
  'warning',
  'danger',
  'info',
  'risk-low',
  'risk-mid',
  'risk-high',
  ...EMOTION_FIELDS.map((field) => `emo-${field}`),
])
export function readDesignToken(name, root = document.documentElement) {
  const value = getComputedStyle(root).getPropertyValue(`--${name}`).trim()
  if (!value) throw new Error(`Missing design token: --${name}. Load tokens.css first.`)
  return value
}
export function createChartTheme(root = document.documentElement) {
  const token = (name) => readDesignToken(name, root)
  const emotions = Object.fromEntries(EMOTION_FIELDS.map((field) => [field, token(`emo-${field}`)]))
  const risks = { low: token('risk-low'), mid: token('risk-mid'), high: token('risk-high') }
  const color = PALETTE_TOKENS.map(token)
  const axis = {
    axisLine: { lineStyle: { color: token('gray-300') } },
    axisTick: { show: false },
    axisLabel: { color: token('text-secondary'), fontSize: Number.parseFloat(token('text-sm')) },
    splitLine: { lineStyle: { color: token('chart-grid') } },
  }
  return {
    color,
    backgroundColor: token('surface'),
    textStyle: { fontFamily: token('font-sans'), color: token('text-primary') },
    title: {
      textStyle: { color: token('text-primary'), fontSize: Number.parseFloat(token('text-h4')) },
    },
    legend: { textStyle: { color: token('text-secondary') } },
    tooltip: {
      backgroundColor: token('surface'),
      borderColor: token('border'),
      textStyle: { color: token('text-primary') },
    },
    categoryAxis: axis,
    valueAxis: axis,
    line: { symbol: 'circle', symbolSize: 7, lineStyle: { width: 3 } },
    bar: { itemStyle: { borderRadius: [4, 4, 0, 0] } },
    pie: {
      label: { color: token('text-primary') },
      itemStyle: { borderColor: token('surface'), borderWidth: 2 },
    },
    xy: { emotions, risks, tokens: [...PALETTE_TOKENS] },
  }
}
export function registerChartTheme(echarts, root = document.documentElement) {
  const theme = createChartTheme(root)
  echarts.registerTheme('xinyu', theme)
  return theme
}
