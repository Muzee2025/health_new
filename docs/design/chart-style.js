import palette from './chart-palette.json';

export { palette };
export const CHART_FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif';

export function relativeLuminance(hex) {
  const rgb = hex.replace('#','').match(/.{2}/g).map(part => parseInt(part,16) / 255);
  return rgb.map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
    .reduce((total,value,index) => total + value * [.2126,.7152,.0722][index],0);
}
export function contrastRatio(first, second) {
  const a = relativeLuminance(first), b = relativeLuminance(second);
  return (Math.max(a,b) + .05) / (Math.min(a,b) + .05);
}
export function labelColor(background) {
  return contrastRatio(palette.colors.text,background) >= contrastRatio(palette.colors.surface,background)
    ? palette.colors.text : palette.colors.surface;
}
export function applyChartPalette(element) {
  element.style.setProperty('--research-font',CHART_FONT);
  Object.entries(palette.colors).forEach(([role,color]) => element.style.setProperty(`--research-${role.replace(/[A-Z]/g,letter => `-${letter.toLowerCase()}`)}`,color));
}
export function createResearchTheme() {
  const { colors } = palette;
  const axis = {axisLine:{lineStyle:{color:colors.grid}},axisTick:{show:false},axisLabel:{color:colors.muted,fontSize:12},splitLine:{lineStyle:{color:colors.grid,width:1}}};
  return {color:palette.categorical,backgroundColor:colors.surface,textStyle:{color:colors.text,fontFamily:CHART_FONT,fontSize:12},categoryAxis:axis,valueAxis:axis,legend:{textStyle:{color:colors.muted,fontSize:12}},xy:{emotions:palette.emotions,risks:palette.risks}};
}
