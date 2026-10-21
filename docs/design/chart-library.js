import * as echarts from 'echarts';
import { palette, CHART_FONT, applyChartPalette, createResearchTheme, labelColor } from './chart-style.js';
import { getChartDemoData, CHANNEL_NAMES, WEEKDAYS, TIME_SLOTS } from './chart-demo-data.js';

const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const sum = values => values.reduce((total, value) => total + value, 0);
const format = value => Number(value).toLocaleString('zh-CN');
const percent = (value, total) => `${(value / total * 100).toFixed(1)}%`;
const summaryMarkup = (value, skipFirst = false) => {
  let index = 0;
  return escape(value).replace(/\d[\d,]*(?:\.\d+)?/g, number => skipFirst && index++ === 0 ? number:`<strong>${number}</strong>`);
};
const isNumericColumn = (spec, index) => index > 0 && !({emotion:[1],channel:[1],heatmap:[1]}[spec.id] || []).includes(index);
const USES = { all:'全部', trend:'趋势', compare:'比较', composition:'组成', distribution:'分布', relationship:'关联' };
const SPECS = [
  {id:'trend', use:'trend', title:'支持记录，沿着时间展开', type:'面积折线', unit:'日期 / 支持记录（次）', intro:'每日支持记录次数；同一天的多次记录分别计数。', columns:['日期','支持记录（次）'], rows:data => data.daily.map(day => [day.date, day.support]), summary:data => `${data.range}天共 ${format(sum(data.daily.map(day => day.support)))} 次记录，日均 ${(sum(data.daily.map(day => day.support)) / data.range).toFixed(1)} 次。`},
  {id:'emotion', use:'composition', title:'每一种心情，都有位置', type:'六情绪环形', unit:'情绪记录（条） / 占比（%）', intro:'一条情绪记录对应一个示例分类；保留既有六类字段。', columns:['情绪','字段','记录（条）','占比（%）'], rows:data => data.emotions.map(item => [item.name,item.field,item.value,percent(item.value,sum(data.emotions.map(item => item.value)))]), summary:data => `共 ${format(sum(data.emotions.map(item => item.value)))} 条情绪记录；分类只展示结构。`},
  {id:'risk', use:'compare', title:'分级记录，一眼对照', type:'横向条形', unit:'分级记录（条）', intro:'示例分级字段的计数展示，不提供诊断或个人风险判断。', columns:['分级','记录（条）','占比（%）'], rows:data => data.risks.map(item => [item.name,item.value,percent(item.value,sum(data.risks.map(item => item.value)))]), summary:data => `低、中、高三级合计 ${format(sum(data.risks.map(item => item.value)))} 条示例记录。`},
  {id:'appointment', use:'compare', title:'预约计划与完成，放在一起看', type:'分组柱形', unit:'星期 / 预约（次）', intro:'按星期汇总区间内计划与已完成预约，完成数不超过计划数。', columns:['星期','计划（次）','完成（次）'], rows:data => data.appointments.map(item => [item.name,item.planned,item.completed]), summary:data => `计划 ${format(sum(data.appointments.map(item => item.planned)))} 次，完成 ${format(sum(data.appointments.map(item => item.completed)))} 次。`},
  {id:'channel', use:'composition', title:'支持从哪里来', type:'100%堆叠条形', unit:'支持记录构成（%）', intro:'工作日与周末分别为分母；比例保留一位小数，每组总计100%。', columns:['日期类型','支持渠道','记录（次）','占比（%）'], rows:data => data.channels.flatMap(group => CHANNEL_NAMES.map((name,index) => [group.name,name,group.counts[index],`${group.percentages[index].toFixed(1)}%`])), summary:data => `工作日 ${format(data.channels[0].total)} 次、周末 ${format(data.channels[1].total)} 次；比较渠道占比。`},
  {id:'heatmap', use:'compare', title:'一周里，哪些时段有预约', type:'星期 × 时段热力矩阵', unit:'星期 / 时段 / 计划预约（次）', intro:'每格为所选区间同星期、同时段的计划预约合计；色阶随范围与样例调整。', columns:['星期','时段','计划预约（次）'], rows:data => data.heatmap.map(item => [item.name,item.slot,item.value]), summary:data => `28个星期与时段组合，共 ${format(sum(data.heatmap.map(item => item.value)))} 次计划预约。`},
  {id:'histogram', use:'distribution', title:'会话时长，分布在哪些区间', type:'等宽直方图', unit:'会话时长（分钟） / 会话（次）', intro:'横轴数字是分箱边界；每箱10分钟、左闭右开，如[10,20)包含10，不含20。', columns:['时长区间（分钟）','会话（次）'], rows:data => data.histogram.map(item => [`[${item.min}, ${item.max})`,item.value]), summary:data => `${format(data.durations.length)} 次会话，均值 ${(sum(data.durations) / data.durations.length).toFixed(1)} 分钟；由同一原始样本分箱。`},
  {id:'scatter', use:'relationship', title:'资源被浏览，也被收藏', type:'互动散点', unit:'横轴：浏览（次） / 纵轴：收藏（次）', intro:'仅8份示例资源，每点一份；用于并列读值，不据此推断统计相关、因果或健康影响。', columns:['资源','浏览（次）','收藏（次）'], rows:data => data.resources.map(item => [item.name,item.views,item.saves]), summary:data => `8份资源，共 ${format(sum(data.resources.map(item => item.views)))} 次浏览、${format(sum(data.resources.map(item => item.saves)))} 次收藏。`},
];

const sourceNotes = data => [
  ['支持记录',`${data.range}个日计数，共${format(sum(data.daily.map(day => day.support)))}次；日均分母为${data.range}天。`],
  ['情绪组成',`分母为${format(sum(data.emotions.map(item => item.value)))}条情绪记录；每条归入一个分类。`],
  ['分级记录',`分母为${format(sum(data.risks.map(item => item.value)))}条分级记录；不与情绪记录合并。`],
  ['预约对比',`按星期累计：计划${format(sum(data.appointments.map(item => item.planned)))}次，完成${format(sum(data.appointments.map(item => item.completed)))}次。`],
  ['渠道组成',`工作日${data.daily.filter(day => day.weekday < 5).length}天、分母${format(data.channels[0].total)}次；周末${data.daily.filter(day => day.weekday >= 5).length}天、分母${format(data.channels[1].total)}次。各组分别为100%，比较内部构成，非日均次数。`],
  ['时段矩阵',`28格累计${format(sum(data.heatmap.map(item => item.value)))}次计划预约；为同星期、同时段的累计，非日均。色阶随当前快照最大值调整。`],
  ['时长分布',`${format(data.durations.length)}个会话样本；8个等宽箱完整覆盖[0,80)分钟，均值由原始样本计算。`],
  ['资源散点',`${data.resources.length}份资源各为一个点；浏览与收藏均为区间累计次数，不是收藏率。`],
];

export function initChartLibrary() {
  const gallery = document.querySelector('#chart-gallery');
  if (!gallery) return;
  const workbench = document.querySelector('#charts');
  applyChartPalette(workbench);
  const theme = createResearchTheme();
  echarts.registerTheme('xinyu-charts',theme);
  const tokenRoles = {'surface':'surface','text-primary':'text','text-secondary':'muted','border':'grid','chart-grid':'grid','brand-100':'primarySoft','brand-500':'primary'};
  const token = name => name === 'font-sans' ? CHART_FONT : palette.colors[tokenRoles[name] || name];
  const colors = palette.categorical;
  const text = palette.colors.text;
  const secondary = palette.colors.muted;
  const heatColors = palette.sequential;
  const palettePanel = document.querySelector('#chart-palette');
  const swatch = (name,color) => `<button type="button" class="research-swatch" data-chart-color="${color}" aria-label="复制${name}色值${color}"><i style="background:${color}" aria-hidden="true"></i><span>${name}<small>${color}</small></span><span class="research-copy" aria-hidden="true">复制</span></button>`;
  palettePanel.innerHTML = `<div class="research-palette-heading"><div><h3>清澈相伴</h3><p>蓝绿记录事实，暖杏保留温度。点击色值即可复制。</p></div><a href="./chart-palette.json" download>下载色卡 JSON</a></div><div class="research-palette-grid"><div><h4>分类与比较</h4><div class="research-swatches">${[['主序列',colors[0]],['第二序列',colors[1]],['第三分类',colors[2]]].map(([name,color]) => swatch(name,color)).join('')}</div></div><div class="research-sequential"><h4>数值由浅到深</h4><div class="research-ramp">${heatColors.map((color,index) => `<button type="button" data-chart-color="${color}" style="background:${color};color:${labelColor(color)}" aria-label="复制顺序色${index + 1}色值${color}">${index + 1}</button>`).join('')}</div><p><span>低值</span><span>高值</span></p><small>同一蓝色顺序 · 热力标尺随数据更新</small></div><div><h4>分级与文字同步</h4><div class="research-swatches">${[['低分级',palette.risks.low],['中分级',palette.risks.mid],['高分级',palette.risks.high]].map(([name,color]) => swatch(name,color)).join('')}</div></div></div><p class="research-palette-footnote">分类颜色不表示大小或心情好坏；分级不替代诊断。<a href="./科研色卡与UI方案.md">查看配色与使用规范</a></p><p id="chart-color-status" role="status" aria-live="polite"></p><label class="research-copy-fallback" hidden>自动复制不可用，请手动复制色值<input readonly aria-label="待复制色值" /></label>`;
  let palettePending = false;
  const onPaletteCopy = async event => {
    const button = event.target.closest('[data-chart-color]');
    if (!button || button.disabled || palettePending || disposed) return;
    const color = button.dataset.chartColor;
    const status = palettePanel.querySelector('#chart-color-status');
    const fallback = palettePanel.querySelector('.research-copy-fallback');
    palettePending = true;
    palettePanel.querySelectorAll('[data-chart-color]').forEach(item => { item.disabled = true; });
    palettePanel.setAttribute('aria-busy','true');
    status.textContent = `正在复制 ${color}…`;
    try {
      await navigator.clipboard.writeText(color);
      if (disposed) return;
      status.textContent = `已复制 ${color}`;
      fallback.hidden = true;
    } catch {
      if (disposed) return;
      status.textContent = `色值 ${color}`;
      fallback.hidden = false;
      const input = fallback.querySelector('input'); input.value = color; input.focus(); input.select();
    } finally {
      palettePending = false;
      if (!disposed) {
        palettePanel.querySelectorAll('[data-chart-color]').forEach(item => { item.disabled = false; });
        palettePanel.removeAttribute('aria-busy');
      }
    }
  };
  palettePanel.addEventListener('click',onPaletteCopy);
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const instances = new Map();
  const pending = new Set();
  let current;
  let state;
  let disposed = false;
  const readState = () => {
    const params = new URL(location.href).searchParams;
    return { use:Object.hasOwn(USES,params.get('chart-use')) ? params.get('chart-use'):'all', range:[7,14,30].includes(Number(params.get('chart-range'))) ? Number(params.get('chart-range')):14, sample:params.get('chart-sample') === 'B' ? 'B':'A' };
  };
  gallery.innerHTML = SPECS.map(spec => `<article class="chart-exhibit chart-exhibit-${spec.id}" data-chart-id="${spec.id}" aria-labelledby="chart-title-${spec.id}"><header><span class="chart-kind">${USES[spec.use]}<span aria-hidden="true"> / </span>${spec.type}</span><h3 id="chart-title-${spec.id}">${spec.title}</h3><p class="chart-unit">${spec.unit}</p></header><p class="chart-takeaway" id="chart-summary-${spec.id}"></p><div id="chart-${spec.id}" class="chart-canvas" role="img" aria-describedby="chart-summary-${spec.id} chart-note-${spec.id}"></div><div class="chart-inline-key" id="chart-key-${spec.id}"></div><p class="chart-note" id="chart-note-${spec.id}">${spec.intro}</p><div class="chart-exhibit-footer"><details class="chart-data" id="chart-data-${spec.id}"><summary>查看数据<span class="chart-row-count" data-chart-row-count aria-hidden="true"></span><span class="sr-only">：${spec.title}</span></summary><div class="chart-table-wrap" tabindex="0" role="region" aria-label="${spec.title}数据表"><table><caption></caption><thead><tr>${spec.columns.map((column,index) => `<th scope="col"${isNumericColumn(spec,index) ? ' class="chart-numeric"':''}>${column}</th>`).join('')}</tr></thead><tbody></tbody></table></div>${spec.id === 'histogram' ? '<details class="chart-raw-data"><summary>查看原始会话样本</summary><p></p></details>':''}</details><button type="button" class="chart-export" data-chart-export="${spec.id}">导出 SVG<span class="sr-only">：${spec.title}</span></button></div><p class="chart-source" data-chart-source></p></article>`).join('');
  const cards = new Map(SPECS.map(spec => [spec.id,gallery.querySelector(`[data-chart-id="${spec.id}"]`)]));

  function option(spec, data, exporting = false) {
    const base = { animation:false, animationDuration:0, animationDurationUpdate:0, backgroundColor:'transparent', aria:{enabled:true,label:{description:`${spec.title}。${spec.unit}。${spec.summary(data)} 合成示例 ${data.sample}，${data.period}。详细数值见查看数据。`}}, textStyle:{fontSize:12,fontFamily:token('font-sans')}, tooltip:{show:false}, grid:{left:42,right:22,top:30,bottom:36,containLabel:false}, xAxis:{type:'category',axisLabel:{fontSize:12,color:secondary,margin:12},axisLine:{lineStyle:{color:token('border')}},axisTick:{show:false}}, yAxis:{type:'value',min:0,minInterval:1,axisLabel:{fontSize:12,color:secondary,margin:12},splitLine:{lineStyle:{color:token('chart-grid'),type:'solid',opacity:.65}}} };
    const label = {show:true,color:text,fontSize:12,position:'top'};
    if (spec.id === 'trend') return {...base, grid:{left:40,right:data.range === 7 ? 20:56,top:28,bottom:38}, xAxis:{...base.xAxis,boundaryGap:false,data:data.daily.map(day => day.label),axisLabel:{...base.xAxis.axisLabel,interval:data.range === 30 ? 5 : data.range === 14 ? 2 : 0,showMinLabel:true,showMaxLabel:true}}, yAxis:{...base.yAxis,name:'次',nameTextStyle:{fontSize:12,color:secondary}}, series:[{type:'line',name:'支持记录',data:data.daily.map(day => day.support),symbolSize:6,lineStyle:{color:colors[0],width:2.5},itemStyle:{color:token('surface'),borderColor:colors[0],borderWidth:2},areaStyle:{color:token('brand-100'),opacity:.55},label:{...label,show:data.range === 7},endLabel:{show:data.range !== 7,formatter:'{c} 次',fontSize:12,color:colors[0],fontWeight:600},labelLayout:{hideOverlap:true}}]};
    if (spec.id === 'emotion') return { ...base,xAxis:undefined,yAxis:undefined,graphic:[{type:'text',left:'center',top:'41%',style:{text:format(sum(data.emotions.map(item => item.value))),font:`600 26px ${token('font-sans')}`,fill:text}},{type:'text',left:'center',top:'56%',style:{text:'条情绪记录',font:`12px ${token('font-sans')}`,fill:secondary}}],series:[{type:'pie',radius:['52%','73%'],center:['50%','50%'],silent:true,label:{show:exporting,fontSize:12,color:text,formatter:'{b} {c}条 ({d}%)'},labelLine:{show:exporting},data:data.emotions.map(item => ({name:item.name,value:item.value,itemStyle:{color:theme.xy.emotions[item.field],borderColor:token('surface'),borderWidth:2}}))}] };
    if (spec.id === 'risk') return {...base,grid:{left:58,right:65,top:20,bottom:36},xAxis:{...base.yAxis,name:'条',nameTextStyle:{fontSize:12,color:secondary}},yAxis:{type:'category',inverse:true,data:data.risks.map(item => item.name),axisTick:{show:false},axisLine:{show:false},axisLabel:{color:text,fontSize:12}},series:[{type:'bar',barMaxWidth:26,label:{...label,position:'right',formatter:'{c} 条'},data:data.risks.map(item => ({value:item.value,itemStyle:{color:theme.xy.risks[item.field],borderRadius:[0,2,2,0]}}))}]};
    if (spec.id === 'appointment') return {...base,legend:{data:['计划','完成'],top:0,right:0,textStyle:{fontSize:12,color:secondary}},grid:{left:40,right:14,top:40,bottom:32},xAxis:{...base.xAxis,data:WEEKDAYS,axisLabel:{...base.xAxis.axisLabel,interval:0,formatter:value => value.replace('周','')}} ,series:['planned','completed'].map((field,index) => ({name:['计划','完成'][index],type:'bar',barMaxWidth:23,barGap:'20%',label, itemStyle:{color:index ? colors[1]:palette.colors.primarySoft,borderRadius:[2,2,0,0],borderColor:index ? colors[1]:colors[0],borderWidth:index ? 0:1},data:data.appointments.map(item => item[field])}))};
    if (spec.id === 'channel') return {...base,grid:{left:52,right:18,top:exporting ? 42:22,bottom:36},legend:exporting ? {top:0,textStyle:{fontSize:12,color:secondary}}:undefined,xAxis:{...base.yAxis,max:100,interval:25,axisLabel:{fontSize:12,color:secondary,formatter:'{value}%'}},yAxis:{type:'category',inverse:true,data:data.channels.map(group => group.name),axisLine:{show:false},axisTick:{show:false},axisLabel:{fontSize:12,color:text}},series:CHANNEL_NAMES.map((name,index) => ({name,type:'bar',stack:'total',barMaxWidth:44,label:{show:true,fontSize:12,color:labelColor(colors[index]),formatter:params => `${Number(params.value).toFixed(1)}%`},itemStyle:{color:colors[index],borderColor:token('surface'),borderWidth:1},data:data.channels.map(group => group.percentages[index])}))};
    if (spec.id === 'heatmap') {
      const max = Math.max(...data.heatmap.map(item => item.value));
      return {...base,grid:{left:76,right:15,top:15,bottom:76},visualMap:{type:'continuous',show:true,min:0,max,dimension:2,orient:'horizontal',left:'center',bottom:0,itemWidth:10,itemHeight:100,calculable:false,precision:0,text:[`${max} 次`,'0 次'],textGap:9,textStyle:{fontSize:12,color:secondary},inRange:{color:heatColors}},xAxis:{type:'category',data:WEEKDAYS,axisLabel:{interval:0,fontSize:12,color:secondary,formatter:value => value.replace('周','')},splitArea:{show:false},axisLine:{show:false},axisTick:{show:false}},yAxis:{type:'category',inverse:true,data:TIME_SLOTS,axisLabel:{fontSize:12,color:secondary},axisLine:{show:false},axisTick:{show:false}},series:[{type:'heatmap',data:data.heatmap.map(item => ({value:[item.weekday,item.time,item.value],itemStyle:{borderWidth:2,borderColor:token('surface')}})),label:{show:true,fontSize:12,color:text,backgroundColor:token('surface'),padding:[1,2],borderRadius:2},emphasis:{disabled:true}}]};
    }
    if (spec.id === 'histogram') return {...base,grid:{left:40,right:14,top:25,bottom:36},xAxis:{...base.xAxis,type:'value',min:0,max:80,interval:10,axisLabel:{...base.xAxis.axisLabel,hideOverlap:false,showMinLabel:true,showMaxLabel:true},splitLine:{show:false}},series:[{type:'custom',encode:{x:[0,1],y:2},data:data.histogram.map(item => [item.min,item.max,item.value]),renderItem:(params,api) => {
      const start = api.coord([api.value(0),api.value(2)]);
      const end = api.coord([api.value(1),0]);
      return {type:'group',children:[{type:'rect',shape:{x:start[0] + .75,y:start[1],width:Math.max(0,end[0] - start[0] - 1.5),height:Math.max(0,end[1] - start[1])},style:{fill:colors[1],stroke:token('surface'),lineWidth:1}},{type:'text',style:{text:String(api.value(2)),x:(start[0] + end[0]) / 2,y:start[1] - 8,align:'center',verticalAlign:'bottom',fill:text,fontSize:12,fontFamily:token('font-sans')}}]};
    }}]};
    return {...base,grid:{left:48,right:28,top:35,bottom:48},xAxis:{...base.yAxis,name:'浏览（次）',nameLocation:'middle',nameGap:29,nameTextStyle:{color:secondary,fontSize:12}},yAxis:{...base.yAxis,name:'收藏（次）',nameTextStyle:{color:secondary,fontSize:12}},series:[{type:'scatter',symbolSize:11,itemStyle:{color:colors[0],opacity:1,borderColor:token('surface'),borderWidth:1},label:{show:true,position:'top',distance:7,color:text,fontSize:12,formatter:params => exporting ? params.data.name:String(params.data.rank)},data:data.resources.map((item,index) => ({name:item.name,rank:index + 1,value:[item.views,item.saves]}))}]};
  }
  function draw(spec) {
    const card = cards.get(spec.id);
    if (card.hidden || disposed) return;
    const element = card.querySelector('.chart-canvas');
    if (element.clientWidth <= 0 || element.clientHeight <= 0) return;
    let chart = instances.get(spec.id);
    if (!chart) { chart = echarts.init(element,'xinyu-charts',{renderer:'svg'}); instances.set(spec.id,chart); }
    chart.resize();
    chart.setOption(option(spec,current),{notMerge:true});
    element.dataset.rendered = 'true';
  }
  function render() {
    current = getChartDemoData(state);
    document.querySelector('#chart-range').value = String(state.range);
    document.querySelector('#chart-sample').value = state.sample;
    document.querySelectorAll('[data-chart-use]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.chartUse === state.use)));
    document.querySelector('#chart-state-summary').textContent = `合成示例 ${state.sample} · ${state.range}天 · ${SPECS.filter(spec => state.use === 'all' || spec.use === state.use).length}种图表`;
    document.querySelector('[data-chart-period]').textContent = current.period.replaceAll('-','.');
    const supportTotal = sum(current.daily.map(day => day.support));
    document.querySelector('[data-chart-overview="total"]').textContent = format(supportTotal);
    document.querySelector('[data-chart-overview="average"]').textContent = (supportTotal / current.range).toFixed(1);
    document.querySelector('[data-chart-source-period]').textContent = `${current.period}；按UTC日界线生成，区间含首尾日期。`;
    document.querySelector('[data-chart-source-definitions]').innerHTML = sourceNotes(current).map(([name,note]) => `<div><dt>${escape(name)}</dt><dd>${escape(note)}</dd></div>`).join('');
    for (const spec of SPECS) {
      const card = cards.get(spec.id);
      card.hidden = state.use !== 'all' && state.use !== spec.use;
      card.querySelector('.chart-takeaway').innerHTML = summaryMarkup(spec.summary(current),spec.id === 'trend');
      const context = `合成示例 ${state.sample} / ${current.period}`;
      card.querySelector('.chart-source').textContent = `${context} / 来源：固定合成样本`;
      card.querySelector('.chart-canvas').setAttribute('aria-label',`${spec.title}。${spec.unit}。${spec.summary(current)} ${context}。详细数值见查看数据。`);
      card.querySelector('caption').innerHTML = `<strong>${spec.title}</strong><span>合成示例 ${state.sample} / <span class="chart-caption-period">${escape(current.period)}</span></span>`;
      const rows = spec.rows(current);
      card.querySelector('[data-chart-row-count]').textContent = `${rows.length} 行`;
      card.querySelector('tbody').innerHTML = rows.map((row,rowIndex) => `<tr${['channel','heatmap'].includes(spec.id) && rowIndex > 0 && row[0] !== rows[rowIndex - 1][0] ? ' class="chart-group-start"':''}>${row.map((value,index) => index ? `<td${isNumericColumn(spec,index) ? ' class="chart-numeric"':''}>${escape(value)}</td>`:`<th scope="row">${escape(value)}</th>`).join('')}</tr>`).join('');
      if (spec.id === 'histogram') card.querySelector('.chart-raw-data p').textContent = `单位：分钟。按日期、会话顺序列出${current.durations.length}个合成样本：${current.durations.join('、')}。`;
      const key = card.querySelector('.chart-inline-key');
      if (spec.id === 'emotion') key.innerHTML = current.emotions.map(item => `<span><i style="background:${escape(theme.xy.emotions[item.field])}" aria-hidden="true"></i>${item.name}<b>${percent(item.value,sum(current.emotions.map(item => item.value)))}</b><small>${item.value} 条</small></span>`).join('');
      if (spec.id === 'channel') key.innerHTML = CHANNEL_NAMES.map((name,index) => `<span><i style="background:${escape(colors[index])}" aria-hidden="true"></i>${name}</span>`).join('');
      if (spec.id === 'heatmap') key.textContent = `0–${Math.max(...current.heatmap.map(item => item.value))}次，按数值线性映射；每格直接标值。`;
      if (spec.id === 'scatter') key.innerHTML = current.resources.map((item,index) => `<span><b>${index + 1}</b><span>${item.name}<small>浏览 ${format(item.views)} 次 / 收藏 ${format(item.saves)} 次</small></span></span>`).join('');
      draw(spec);
    }
  }
  function update(next) {
    state = {...state,...next};
    const url = new URL(location.href);
    url.searchParams.set('chart-use',state.use);
    url.searchParams.set('chart-range',state.range);
    url.searchParams.set('chart-sample',state.sample);
    history.pushState(null,'',url);
    render();
  }
  const onUse = event => { const button = event.target.closest('[data-chart-use]'); if (button) update({use:button.dataset.chartUse}); };
  const onRange = event => update({range:Number(event.target.value)});
  const onSample = event => update({sample:event.target.value});
  const onPop = () => { state = readState(); render(); };
  const onMotion = () => render();
  document.querySelector('#chart-use-filters').addEventListener('click',onUse);
  document.querySelector('#chart-range').addEventListener('change',onRange);
  document.querySelector('#chart-sample').addEventListener('change',onSample);
  window.addEventListener('popstate',onPop);
  motion.addEventListener('change',onMotion);

  const resizeObserver = new ResizeObserver(entries => {
    if (!current) return;
    for (const entry of entries) {
      if (entry.contentRect.width <= 0 || entry.contentRect.height <= 0) continue;
      const spec = SPECS.find(item => `chart-${item.id}` === entry.target.id);
      if (spec) draw(spec);
    }
  });
  gallery.querySelectorAll('.chart-canvas').forEach(element => resizeObserver.observe(element));

  function exportSvg(spec, data) {
    const host = document.createElement('div');
    host.style.cssText = 'position:fixed;left:-10000px;top:0;width:880px;height:380px;pointer-events:none';
    document.body.append(host);
    let exportChart;
    try {
      exportChart = echarts.init(host,'xinyu-charts',{renderer:'svg',width:880,height:380});
      exportChart.setOption(option(spec,data,true));
      // Serialize the actual SVG DOM so quoted local font-family names stay XML-safe.
      exportChart.getZr().flush();
      const inner = host.querySelector('svg')?.cloneNode(true);
      if (!inner) throw new Error('SVG renderer did not produce an export');
      inner.setAttribute('x','20'); inner.setAttribute('y','105');
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="920" height="550" viewBox="0 0 920 550" role="img" aria-labelledby="export-title export-description"><title id="export-title">${escape(spec.title)}</title><desc id="export-description">${escape(spec.summary(data))} ${escape(spec.intro)}</desc><rect width="920" height="550" fill="${escape(token('surface'))}"/><g fill="${escape(text)}" font-family="Microsoft YaHei, sans-serif"><text x="36" y="36" font-size="22" font-weight="600">${escape(spec.title)}</text><text x="36" y="64" font-size="14">${escape(spec.unit)} · ${escape(spec.summary(data))}</text><text x="36" y="88" font-size="12">合成示例 ${data.sample} / ${data.period} / ${data.range}天 / UTC日界 / 固定生成规则</text></g>${new XMLSerializer().serializeToString(inner)}<text x="36" y="518" font-size="12" fill="${escape(secondary)}" font-family="Microsoft YaHei, sans-serif">${escape(spec.intro)}</text><text x="36" y="539" font-size="12" fill="${escape(secondary)}" font-family="Microsoft YaHei, sans-serif">心域智链素材库 · 固定合成数据；计数非人数，不代表真实学生、诊断或疗效。</text></svg>`;
      const url = URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}));
      const link = document.createElement('a');
      link.href = url; link.download = `chart-${spec.id}-${data.sample}-${data.range}d.svg`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url),30000);
    } finally { exportChart?.dispose(); host.remove(); }
  }
  const onExport = async event => {
    const button = event.target.closest('[data-chart-export]');
    if (!button || pending.has(button.dataset.chartExport)) return;
    const id = button.dataset.chartExport;
    const snapshot = current;
    pending.add(id); button.disabled = true; button.setAttribute('aria-busy','true');
    const feedback = document.querySelector('#chart-export-status');
    try {
      await new Promise(resolve => requestAnimationFrame(resolve));
      exportSvg(SPECS.find(spec => spec.id === id),snapshot);
      feedback.textContent = `已导出${SPECS.find(spec => spec.id === id).title}，合成示例 ${snapshot.sample}，${snapshot.range}天。`;
    } catch (error) { feedback.textContent = '导出未完成，请重新点击导出 SVG。'; console.error('Chart SVG export failed',error); }
    finally { pending.delete(id); button.disabled = false; button.removeAttribute('aria-busy'); }
  };
  gallery.addEventListener('click',onExport);
  function onPageHide(event) {
    if (!event.persisted) dispose();
  }
  function onPageShow(event) {
    if (event.persisted) { state = readState(); render(); }
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    resizeObserver.disconnect();
    instances.forEach(chart => chart.dispose()); instances.clear();
    window.removeEventListener('popstate',onPop); motion.removeEventListener('change',onMotion);
    window.removeEventListener('pagehide',onPageHide);
    window.removeEventListener('pageshow',onPageShow);
    document.querySelector('#chart-use-filters').removeEventListener('click',onUse);
    document.querySelector('#chart-range').removeEventListener('change',onRange);
    document.querySelector('#chart-sample').removeEventListener('change',onSample);
    gallery.removeEventListener('click',onExport);
    palettePanel.removeEventListener('click',onPaletteCopy);
  }
  window.addEventListener('pagehide',onPageHide);
  window.addEventListener('pageshow',onPageShow);
  state = readState(); render();
  return dispose;
}
