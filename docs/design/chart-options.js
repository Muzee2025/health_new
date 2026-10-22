import { palette, CHART_FONT, createResearchTheme } from './chart-style.js';

// Extracted from chart-library.js: presentation only, never imports demo data.
export const LIBRARY_CHART_STYLE = Object.freeze({
  fontSize: 12, headingSize: 18, valueSize: 26, lineWidth: 2.5,
  symbolSize: 6, barRadius: 2, areaOpacity: .55, pieBorderWidth: 2,
});

export function libraryChartFont(weight = 400, size = LIBRARY_CHART_STYLE.fontSize) {
  return `${weight} ${size}px ${CHART_FONT}`;
}

export function createLibraryChartBase({ description = '' } = {}) {
  const { colors } = palette;
  return {
    animation: false, animationDuration: 0, animationDurationUpdate: 0,
    backgroundColor: 'transparent', aria: { enabled: true, label: { description } },
    textStyle: { fontSize: LIBRARY_CHART_STYLE.fontSize, fontFamily: CHART_FONT },
    tooltip: { show: false }, grid: { left: 42, right: 22, top: 30, bottom: 36, containLabel: false },
    xAxis: { type: 'category', axisLabel: { fontSize: 12, color: colors.muted, margin: 12 }, axisLine: { lineStyle: { color: colors.grid } }, axisTick: { show: false } },
    yAxis: { type: 'value', min: 0, minInterval: 1, axisLabel: { fontSize: 12, color: colors.muted, margin: 12 }, splitLine: { lineStyle: { color: colors.grid, type: 'solid', opacity: .65 } } },
  };
}

const appearance = () => ({ fontFamily: CHART_FONT, fontSize: LIBRARY_CHART_STYLE.fontSize });
const styledLabel = label => label && ({ ...label, fontFamily: CHART_FONT, fontSize: LIBRARY_CHART_STYLE.fontSize });

function styleAxis(axis) {
  if (Array.isArray(axis)) return axis.map(styleAxis);
  if (!axis) return axis;
  const theme = createResearchTheme().valueAxis;
  return { ...theme, ...axis,
    axisLabel: { ...theme.axisLabel, ...axis.axisLabel, ...appearance(), color: palette.colors.muted },
    nameTextStyle: { ...axis.nameTextStyle, ...appearance(), color: palette.colors.muted },
    axisLine: { ...theme.axisLine, ...axis.axisLine, lineStyle: { ...axis.axisLine?.lineStyle, color: palette.colors.grid } },
    axisTick: { ...axis.axisTick, show: false },
    splitLine: { ...axis.splitLine, lineStyle: { ...axis.splitLine?.lineStyle, color: palette.colors.grid, type: 'solid', width: 1, opacity: .65 } },
  };
}

function styleSeries(series, horizontal) {
  let itemStyle = { ...series.itemStyle };
  const next = { ...series, label: styledLabel(series.label), endLabel: styledLabel(series.endLabel) };
  if (series.type === 'line' || series.type === 'radar') {
    next.lineStyle = { ...series.lineStyle, width: LIBRARY_CHART_STYLE.lineWidth };
    if (series.type === 'line') next.symbolSize = series.symbol === 'none' || series.symbolSize === 0 ? 0 : LIBRARY_CHART_STYLE.symbolSize;
    if (series.areaStyle) next.areaStyle = { ...series.areaStyle, opacity: LIBRARY_CHART_STYLE.areaOpacity };
  }
  if (series.type === 'bar') {
    const radius = series.stack ? 0 : horizontal ? [0, LIBRARY_CHART_STYLE.barRadius, LIBRARY_CHART_STYLE.barRadius, 0] : [LIBRARY_CHART_STYLE.barRadius, LIBRARY_CHART_STYLE.barRadius, 0, 0];
    itemStyle.borderRadius = radius;
    // Per-datum semantic colors stay intact; shape still comes from the library.
    if (series.data) next.data = series.data.map(item => item && typeof item === 'object' && !Array.isArray(item) && item.itemStyle
      ? { ...item, itemStyle: { ...item.itemStyle, borderRadius: radius } } : item);
  }
  if (series.type === 'pie') itemStyle = { ...itemStyle, borderColor: palette.colors.surface, borderWidth: LIBRARY_CHART_STYLE.pieBorderWidth };
  if (series.type === 'graph' && series.lineStyle) next.lineStyle = { ...series.lineStyle, width: LIBRARY_CHART_STYLE.lineWidth };
  if (series.type !== 'bar' && series.data) next.data = series.data.map(item => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
    return { ...item,
      ...(item.lineStyle ? { lineStyle: { ...item.lineStyle, width: LIBRARY_CHART_STYLE.lineWidth } } : {}),
      ...(item.areaStyle ? { areaStyle: { ...item.areaStyle, opacity: LIBRARY_CHART_STYLE.areaOpacity } } : {}),
      ...(item.label ? { label: styledLabel(item.label) } : {}),
    };
  });
  next.itemStyle = itemStyle;
  return next;
}

function styleGraphic(graphic) {
  if (Array.isArray(graphic)) return graphic.map(styleGraphic);
  if (!graphic) return graphic;
  if (graphic.elements) return { ...graphic, elements: graphic.elements.map(styleGraphic) };
  if (graphic.type !== 'text' || !graphic.style) return graphic;
  const size = graphic.style.fontSize || Number(String(graphic.style.font || '').match(/(\d+(?:\.\d+)?)px/)?.[1]) || LIBRARY_CHART_STYLE.fontSize;
  const valueRole = size >= LIBRARY_CHART_STYLE.headingSize;
  const fontSize = valueRole ? LIBRARY_CHART_STYLE.valueSize : LIBRARY_CHART_STYLE.fontSize;
  const fontWeight = valueRole ? 600 : 400;
  return { ...graphic, style: { ...graphic.style, font: libraryChartFont(fontWeight, fontSize), fontFamily: CHART_FONT, fontSize, fontWeight,
    fill: valueRole ? palette.colors.text : palette.colors.muted,
  } };
}

/** Preserves data, scales, units, formatters, encodings and per-view geometry. */
export function createLibraryChartOption(option) {
  const next = { ...option, animation: false, animationDuration: 0, animationDurationUpdate: 0,
    color: option.color || palette.categorical,
    textStyle: { ...option.textStyle, ...appearance(), color: palette.colors.text },
  };
  if (option.tooltip) next.tooltip = { ...option.tooltip, backgroundColor: palette.colors.surface, borderColor: palette.colors.grid, textStyle: { ...option.tooltip.textStyle, ...appearance(), color: palette.colors.text } };
  if (option.legend) next.legend = { ...option.legend, textStyle: { ...option.legend.textStyle, ...appearance(), color: palette.colors.muted } };
  if (option.title) next.title = { ...option.title, textStyle: { ...option.title.textStyle, ...appearance(), fontSize: LIBRARY_CHART_STYLE.headingSize, color: palette.colors.text } };
  if (option.visualMap) next.visualMap = { ...option.visualMap, textStyle: { ...option.visualMap.textStyle, ...appearance(), color: palette.colors.muted } };
  if (option.graphic) next.graphic = styleGraphic(option.graphic);
  for (const key of ['xAxis', 'yAxis']) if (Object.hasOwn(option, key)) next[key] = styleAxis(option[key]);
  if (option.radar) next.radar = { ...option.radar, axisName: { ...option.radar.axisName, ...appearance(), color: palette.colors.muted }, splitLine: { ...option.radar.splitLine, lineStyle: { ...option.radar.splitLine?.lineStyle, color: palette.colors.grid } } };
  const horizontal = (Array.isArray(option.yAxis) ? option.yAxis[0] : option.yAxis)?.type === 'category' && (Array.isArray(option.xAxis) ? option.xAxis[0] : option.xAxis)?.type === 'value';
  if (option.series) next.series = option.series.map(series => styleSeries(series, horizontal));
  return next;
}

export function setLibraryChartOption(chart, option, ...args) {
  chart.setOption(createLibraryChartOption(option), ...args);
}

/** Chart.js confidence view uses the same library fonts, colors and bar geometry. */
export function createLibraryChartJsConfig(config) {
  const scales = Object.fromEntries(Object.entries(config.options?.scales || {}).map(([key, scale]) => [key, {
    ...scale, ticks: { ...scale.ticks, color: palette.colors.muted, font: { ...scale.ticks?.font, family: CHART_FONT, size: 12 } },
  }]));
  return { ...config, data: { ...config.data, datasets: config.data.datasets.map(dataset => ({ ...dataset, borderRadius: LIBRARY_CHART_STYLE.barRadius })) }, options: {
    ...config.options, animation: false, scales,
    font: { family: CHART_FONT, size: 12 },
  } };
}
