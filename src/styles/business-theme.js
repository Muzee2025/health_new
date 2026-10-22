import palette from '../../docs/design/chart-palette.json'

/** W2 business charts share the approved research palette, without gallery CSS. */
export function installBusinessCharts(echarts) {
  const { colors } = palette
  const root = document.documentElement
  Object.entries(colors).forEach(([name, value]) => root.style.setProperty(`--data-${name}`, value))
  Object.entries(palette.risks).forEach(([name, value]) => root.style.setProperty(`--data-risk-${name}`, value))
  const axis = {
    axisLine: { lineStyle: { color: colors.grid } }, axisTick: { show: false },
    axisLabel: { color: colors.muted, fontSize: 12 },
    splitLine: { lineStyle: { color: colors.grid, type: 'dashed' } },
  }
  echarts.registerTheme('xinyu-business', {
    color: palette.categorical, backgroundColor: colors.surface,
    textStyle: { fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', fontSize: 12, color: colors.text },
    legend: { textStyle: { color: colors.muted, fontSize: 12 } },
    tooltip: { backgroundColor: colors.surface, borderColor: colors.grid, textStyle: { color: colors.text, fontSize: 12 } },
    categoryAxis: axis, valueAxis: axis,
    line: { symbol: 'circle', symbolSize: 6, lineStyle: { width: 2 } },
    bar: { itemStyle: { borderRadius: [4, 4, 0, 0] } },
    pie: { itemStyle: { borderColor: colors.surface, borderWidth: 2 }, label: { color: colors.text, fontSize: 12 } },
  })
}

export function businessColor(name) {
  const root = document.querySelector('.xy-business') || document.documentElement
  return getComputedStyle(root).getPropertyValue(`--${name}`).trim()
}

export function businessAlpha(name, opacity) {
  const alpha = Math.round(Math.min(1, Math.max(0, opacity)) * 255).toString(16).padStart(2, '0')
  return `${businessColor(name)}${alpha}`
}

export const businessPalette = palette
