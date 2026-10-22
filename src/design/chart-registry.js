import { palette, applyChartPalette, createResearchTheme } from '../../docs/design/chart-style.js'

/** Business adapter to the actual library implementation, with no second theme. */
export function installBusinessCharts(echarts) {
  const root = document.documentElement
  applyChartPalette(root)
  Object.entries(palette.colors).forEach(([name, value]) => root.style.setProperty(`--data-${name}`, value))
  Object.entries(palette.risks).forEach(([name, value]) => root.style.setProperty(`--data-risk-${name}`, value))
  echarts.registerTheme('xinyu-business', createResearchTheme())
}

export function businessColor(name) {
  const root = document.querySelector('.xy-business') || document.documentElement
  return getComputedStyle(root).getPropertyValue(`--${name}`).trim()
}

export function businessAlpha(name, opacity) {
  const alpha = Math.round(Math.min(1, Math.max(0, opacity)) * 255).toString(16).padStart(2, '0')
  return `${businessColor(name)}${alpha}`
}

export { palette as businessPalette }
export { setLibraryChartOption, createLibraryChartOption, createLibraryChartJsConfig, libraryChartFont, LIBRARY_CHART_STYLE } from '../../docs/design/chart-options.js'
