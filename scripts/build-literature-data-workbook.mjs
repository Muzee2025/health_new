import fs from 'node:fs/promises'
import path from 'node:path'
import { createRequire } from 'node:module'
import { pathToFileURL, fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const work = path.join(root, 'tmp/literature-data-20261028')
const req = createRequire(path.join(work, 'runtime.cjs'))
const { Workbook, SpreadsheetFile } = await import(
  pathToFileURL(req.resolve('@oai/artifact-tool')).href
)
const data = JSON.parse(
  await fs.readFile(
    path.join(root, 'docs/plan/research-data-20261028/processed-data.json'),
    'utf8',
  ),
)
const d = data.datasets
const tokens = await fs.readFile(path.join(root, 'src/styles/tokens.css'), 'utf8')
const color = (name) => tokens.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`))[1]
const purple = color('brand-600'),
  ink = color('gray-800'),
  pale = color('brand-50')
const font = 'Microsoft YaHei'
const wb = Workbook.create()
const names = [
  '分析概览',
  '文献与下载来源',
  '调查波次',
  '筛查汇总',
  '发表年分组',
  '相关因素',
  '原始变量字典',
  '原始数据质量',
  'AI干预效果',
  'AI试验特征',
  'Woebot终点',
  '来源问题',
]
const sh = Object.fromEntries(names.map((n) => [n, wb.worksheets.add(n)]))
const letter = (n) => {
  let r = ''
  for (let x = n + 1; x; x = Math.floor((x - 1) / 26))
    r = String.fromCharCode(65 + ((x - 1) % 26)) + r
  return r
}
const ranges = {}
function title(s, text, note) {
  s.showGridLines = false
  s.getRange('A1:P50').format.font = { name: font, size: 10, color: ink }
  s.getRange('A1:P50').format.verticalAlignment = 'center'
  s.mergeCells('A2:F2')
  s.getRange('A2').values = [[text]]
  s.getRange('A2:F2').format.font = { name: font, size: 15, bold: true, color: purple }
  s.getRange('A2').format.rowHeight = 29
  s.mergeCells('A3:F3')
  s.getRange('A3').values = [[note]]
  s.getRange('A3:F3').format.wrapText = true
  s.getRange('A3').format.rowHeight = 34
  s.getRange('A4:P4').format.borders = { bottom: { style: 'thin', color: purple } }
}
function table(s, tableName, headers, rows, widths, { start = 6, height = 44 } = {}) {
  const last = letter(headers.length - 1),
    end = start + rows.length,
    r = s.getRange(`A${start}:${last}${end}`)
  r.values = [headers, ...rows]
  r.format.font = { name: font, size: 10, color: ink }
  r.format.wrapText = true
  r.format.verticalAlignment = 'center'
  r.format.rowHeight = height
  const t = s.tables.add(`A${start}:${last}${end}`, true, tableName)
  t.style = 'TableStyleLight1'
  t.showFilterButton = true
  for (let i = 0; i < rows.length; i++)
    if (i % 2) s.getRange(`A${start + i + 1}:${last}${start + i + 1}`).format.fill = pale
  s.getRange(`A${start}:${last}${start}`).format = {
    fill: purple,
    font: { name: font, size: 10, bold: true, color: '#FFFFFF' },
    rowHeight: 38,
    wrapText: true,
  }
  widths.forEach(
    (w, i) => (s.getRange(`${letter(i)}${start}:${letter(i)}${end}`).format.columnWidth = w),
  )
  s.freezePanes.freezeRows(6)
  ranges[tableName] = { sheet: s.name, start, end, last, rows: rows.length }
  return { start, end, last }
}
const rows = (key, keys) => d[key].map((x) => keys.map((k) => x[k] ?? null))
title(
  sh.文献与下载来源,
  '文献与下载来源',
  '2026-10-28定向检索并下载6篇相关论文；不是系统综述或全部文献覆盖。',
)
table(
  sh.文献与下载来源,
  'LiteratureSources',
  [
    '来源ID',
    '论文题名',
    '作者',
    '期刊',
    '发表年',
    '研究设计',
    '观察时期',
    '人群与样本说明',
    '原文主要样本量',
    '量表或单位',
    'DOI',
    '原文网址',
    '许可',
    '获取状态',
  ],
  rows('sources', [
    'source_id',
    'title',
    'authors',
    'journal',
    'publication_year',
    'design',
    'observation_period',
    'population',
    'headline_sample_n',
    'instruments_or_units',
    'doi',
    'article_url',
    'license',
    'access',
  ]),
  [20, 78, 64, 39, 14, 40, 60, 70, 23, 65, 40, 90, 62, 74],
  { height: 98 },
)
sh.文献与下载来源.mergeCells('A16:F16')
sh.文献与下载来源.getRange('A16').values = [
  ['逐文件下载凭证：去重后26份，其中1份个体XLSX仅保留本地，其余25份进入研究资料包。'],
]
table(
  sh.文献与下载来源,
  'DownloadedResearchFiles',
  ['来源ID', '原文件名', 'SHA256', '字节数', '下载时间（北京时间）', '交付范围', '许可', '下载URL'],
  rows('downloaded_files', [
    'source_id',
    'file',
    'sha256',
    'bytes',
    'downloaded_at',
    'delivery',
    'license',
    'url',
  ]),
  [20, 78, 72, 39, 41, 40, 72, 115],
  { start: 18, height: 48 },
)
sh.文献与下载来源.getRange('D19:D44').setNumberFormat('#,##0')

title(
  sh.调查波次,
  '同一研究的两次独立调查',
  '两次样本分别n=9554、3886；第二次排除重复参加者。比例差不表示同一人的变化。',
)
const waveRows = d.survey_waves.map((r) => [
  r.source_id,
  r.survey_wave,
  new Date(r.start_date + 'T00:00:00Z'),
  new Date(r.end_date + 'T00:00:00Z'),
  r.sample_n,
  r.outcome,
  r.instrument,
  r.cutoff,
  r.estimate,
  r.ci95_lower,
  r.ci95_upper,
  null,
  r.limitation,
  r.source_location,
])
table(
  sh.调查波次,
  'SurveyWaves',
  [
    '来源ID',
    '波次',
    '调查开始',
    '调查结束',
    '样本n',
    '结局',
    '量表',
    '阈值',
    '筛查阳性比例',
    '95%CI下限',
    '95%CI上限',
    '较第一波差（百分点）',
    '解释限制',
    '来源位置',
  ],
  waveRows,
  [20, 12, 18, 18, 16, 20, 17, 13, 22, 22, 22, 28, 90, 55],
  { height: 50 },
)
sh.调查波次.getRange('C7:D10').setNumberFormat('yyyy-mm-dd')
sh.调查波次.getRange('I7:K10').setNumberFormat('0.0%')
sh.调查波次.getRange('L7:L8').values = [['n.a.'], ['n.a.']]
sh.调查波次.getRange('L9:L10').formulas = [['=(I9-I7)*100'], ['=(I10-I8)*100']]
sh.调查波次.getRange('L9:L10').setNumberFormat('0.0')

title(
  sh.筛查汇总,
  '已发表筛查比例与亚组',
  '保留来源、量表与阈值；同一综述的总体/性别/学段/地区样本有重叠，不可相加。',
)
const screening = table(
  sh.筛查汇总,
  'ScreeningAggregates',
  [
    '来源ID',
    '亚组类型',
    '组别',
    '研究数k',
    '样本n',
    '筛查阳性比例',
    '95%CI下限',
    '95%CI上限',
    'I²',
    '量表',
    '阈值',
    '来源位置',
    '解释限制',
  ],
  rows('screening_aggregates', [
    'source_id',
    'subgroup_type',
    'group',
    'studies_k',
    'sample_n',
    'estimate',
    'ci95_lower',
    'ci95_upper',
    'i2',
    'instrument',
    'cutoff',
    'source_location',
    'limitation',
  ]),
  [20, 23, 32, 16, 20, 23, 22, 22, 17, 35, 23, 65, 88],
)
sh.筛查汇总.getRange(`D7:E${screening.end}`).setNumberFormat('#,##0')
sh.筛查汇总.getRange(`F7:I${screening.end}`).setNumberFormat('0.00%')

title(
  sh.发表年分组,
  '按发表年份整理的文献亚组',
  'Year在原文Methods中明确为发表年份；这些值不是中国学生逐年人群患病率或纵向追踪。',
)
const years = table(
  sh.发表年分组,
  'PublicationYearGroups',
  [
    '来源ID',
    '发表年',
    '研究数k',
    '样本n',
    '合并筛查比例',
    '95%CI下限',
    '95%CI上限',
    'I²',
    '年份定义',
    '来源位置',
    'CI宽度（百分点）',
    '研究数量提示',
  ],
  d.publication_year_groups.map((r) => [
    r.source_id,
    r.publication_year,
    r.studies_k,
    r.sample_n,
    r.estimate,
    r.ci95_lower,
    r.ci95_upper,
    r.i2,
    r.year_type,
    r.source_location,
    null,
    null,
  ]),
  [20, 15, 16, 20, 23, 22, 22, 16, 40, 62, 28, 41],
  { height: 38 },
)
sh.发表年分组.getRange(`C7:D${years.end}`).setNumberFormat('#,##0')
sh.发表年分组.getRange(`E7:H${years.end}`).setNumberFormat('0.00%')
for (let r = 7; r <= years.end; r++)
  sh.发表年分组.getRange(`K${r}:L${r}`).formulas = [
    [`=(G${r}-F${r})*100`, `=IF(C${r}<3,"仅1—2项研究，估计不稳定","保留CI及异质性")`],
  ]
sh.发表年分组.getRange(`K7:K${years.end}`).setNumberFormat('0.00')

title(
  sh.相关因素,
  '相关因素与调整后的优势比',
  'OR是优势比，不能解释为风险增加倍数。CHEN2023结局是抑郁或焦虑任一筛查阳性。',
)
const factors = table(
  sh.相关因素,
  'AdjustedAssociations',
  [
    '来源ID',
    '原表',
    '分析人群',
    '结局定义',
    '相关因素',
    '比较组',
    '参考组',
    '调整后OR',
    '95%CI下限',
    '95%CI上限',
    '原文P值',
    '解释范围',
    '原单元格文本',
  ],
  rows('adjusted_associations', [
    'source_id',
    'table',
    'population',
    'outcome',
    'factor',
    'comparison',
    'reference',
    'adjusted_or',
    'ci95_lower',
    'ci95_upper',
    'p_reported',
    'causal_status',
    'source_cell',
  ]),
  [20, 15, 31, 58, 42, 49, 45, 20, 21, 21, 20, 62, 105],
)
sh.相关因素.getRange(`H7:J${factors.end}`).setNumberFormat('0.00')

title(
  sh.原始变量字典,
  '已下载原始数据的74个变量',
  'YANG2023公开补充XLSX含926条分层访谈记录。这里只输出字段与缺失聚合，不输出个人行。',
)
const dict = table(
  sh.原始变量字典,
  'MicrodataVariables',
  [
    '来源ID',
    '原始变量名',
    '含义或代码本限制',
    '观察类型',
    '记录数',
    '非缺失数',
    '缺失数',
    '缺失比例',
    '分析范围',
    '原始位置',
  ],
  rows('microdata_dictionary', [
    'source_id',
    'variable',
    'description',
    'observed_type',
    'sample_rows',
    'nonmissing_n',
    'missing_n',
    'missing_rate',
    'analysis_policy',
    'source_location',
  ]),
  [20, 43, 90, 22, 16, 18, 18, 21, 70, 64],
)
for (let r = 7; r <= dict.end; r++)
  sh.原始变量字典.getRange(`G${r}:H${r}`).formulas = [
    [`=E${r}-F${r}`, `=IF(E${r}=0,"n.a.",G${r}/E${r})`],
  ]
sh.原始变量字典.getRange(`E7:G${dict.end}`).setNumberFormat('#,##0')
sh.原始变量字典.getRange(`H7:H${dict.end}`).setNumberFormat('0.00%')

title(
  sh.原始数据质量,
  '原始补充数据的质量与权重',
  '未拟合临床预测模型，未重估诊断患病率。权重和、样本数与Kish近似有效样本量分别列示。',
)
table(
  sh.原始数据质量,
  'MicrodataQuality',
  ['来源ID', '检查指标', '聚合结果', '单位', '解释与限制'],
  rows('microdata_quality', ['source_id', 'metric', 'value', 'unit', 'interpretation']),
  [20, 55, 25, 24, 108],
  { height: 42 },
)
d.microdata_quality.forEach((r, i) =>
  sh.原始数据质量
    .getRange(`C${i + 7}`)
    .setNumberFormat(
      r.unit === '条' || r.unit === '列' || (r.unit === '人' && !r.metric.includes('近似'))
        ? '#,##0'
        : '#,##0.00',
    ),
)

title(
  sh.AI干预效果,
  'AI聊天干预的短期效果',
  'Hedges g正值有利干预；效应与95%CI同时保留。综述数据不能当成本项目已有疗效。',
)
const effect = table(
  sh.AI干预效果,
  'AiEffects',
  [
    '来源ID',
    '结局',
    '分析版本',
    '原文试验数k',
    'Hedges g',
    '95%CI下限',
    '95%CI上限',
    'I²',
    '原文P值',
    'CI是否跨0',
    '原文位置',
    '限制与异常',
  ],
  d.ai_effects.map((r) => [
    r.source_id,
    r.outcome,
    r.analysis,
    r.trials_k_reported,
    r.hedges_g,
    r.ci95_lower,
    r.ci95_upper,
    r.i2,
    r.p_reported,
    null,
    r.source_location,
    r.limitation,
  ]),
  [20, 22, 46, 23, 20, 22, 22, 18, 20, 27, 70, 110],
  { height: 54 },
)
sh.AI干预效果.getRange(`E7:G${effect.end}`).setNumberFormat('0.000')
sh.AI干预效果.getRange(`H7:H${effect.end}`).setNumberFormat('0.0%')
for (let r = 7; r <= effect.end; r++)
  sh.AI干预效果.getRange(`J${r}`).formulas = [[`=IF(OR(F${r}>0,G${r}<0),"CI不跨0","CI跨0")`]]
sh.AI干预效果.mergeCells('A21:F21')
sh.AI干预效果.getRange('A21').values = [
  ['抑郁症状的跨研究亚组分析：关联不等于某特征造成疗效改变。'],
]
const mod = table(
  sh.AI干预效果,
  'AiModerators',
  [
    '来源ID',
    '分组因素',
    '类别',
    '研究数k',
    'Hedges g',
    '95%CI下限',
    '95%CI上限',
    '来源位置',
    '解释范围',
  ],
  rows('ai_moderators', [
    'source_id',
    'moderator',
    'category',
    'trials_k',
    'hedges_g',
    'ci95_lower',
    'ci95_upper',
    'source_location',
    'limitation',
  ]),
  [20, 32, 48, 22, 20, 22, 22, 28, 102],
  { start: 23, height: 44 },
)
sh.AI干预效果.getRange(`E24:G${mod.end}`).setNumberFormat('0.00')

title(
  sh.AI试验特征,
  '15项AI干预试验的原表特征',
  '来自FENG2025补充表S2，原表样本合计1901；与摘要1974不一致，未擅自统一。',
)
const trials = table(
  sh.AI试验特征,
  'AiTrialCharacteristics',
  [
    '来源ID',
    '研究',
    '样本类型',
    '原表样本n',
    '女性比例',
    '平均年龄',
    '对话代理',
    '平台',
    '交互模式',
    '治疗框架',
    '干预时长',
    '对照类型',
    '测量工具',
    '来源位置',
    '解释限制',
  ],
  rows('ai_trial_characteristics', [
    'source_id',
    'study',
    'sample_type',
    'reported_n',
    'female_fraction',
    'mean_age',
    'agent_name',
    'platform',
    'mode',
    'therapy',
    'duration',
    'control',
    'outcomes',
    'source_location',
    'limitation',
  ]),
  [20, 38, 28, 20, 19, 18, 30, 45, 30, 49, 30, 38, 65, 68, 90],
  { height: 63 },
)
sh.AI试验特征.getRange(`E7:E${trials.end}`).setNumberFormat('0.0%')
sh.AI试验特征.getRange(`F7:F${trials.end}`).setNumberFormat('0.00')
sh.AI试验特征.getRange('C24').values = [['原表样本合计']]
sh.AI试验特征.getRange('D24').formulas = [[`=SUM(D7:D${trials.end})`]]

title(
  sh.Woebot终点,
  'Woebot试验的T2结果',
  '70人随机分组，58人提供T2；原文ITT表的括号是SE，不是SD。保留原文疑似统计冲突。',
)
const endpoints = table(
  sh.Woebot终点,
  'WoebotEndpoints',
  [
    '来源ID',
    '结局',
    '组别',
    '分析时点',
    '原文均值',
    '标准误SE',
    '95%CI下限',
    '95%CI上限',
    '原文F',
    '原文P',
    '原文Cohen d',
    '原表/脚注',
    '限制',
  ],
  rows('woebot_endpoints', [
    'source_id',
    'outcome',
    'arm',
    'endpoint',
    'mean',
    'standard_error',
    'ci95_lower',
    'ci95_upper',
    'f_reported',
    'p_reported',
    'cohen_d_reported',
    'source_location',
    'limitation',
  ]),
  [20, 35, 25, 31, 21, 22, 23, 23, 18, 18, 24, 72, 114],
  { height: 57 },
)
sh.Woebot终点.getRange(`E7:K${endpoints.end}`).setNumberFormat('0.000')

title(
  sh.来源问题,
  '原文冲突、数据限制与处理记录',
  '原文中的冲突按原值保留并标注，相关行不用于强结论；没有用猜测填补缺失或替作者改数。',
)
table(
  sh.来源问题,
  'SourceAudits',
  ['来源ID', '问题', '实际观察到的证据', '本次处理'],
  rows('source_audits', ['source_id', 'issue', 'observed_evidence', 'handling']),
  [20, 57, 105, 111],
  { height: 68 },
)

const out = sh.分析概览
title(
  out,
  '心域智链文献数据下载与分析',
  '公开研究数据，检索与处理日期2026-10-28。各研究人群、量表、阈值和观察期保持分开。',
)
out.getRange('A6:D6').values = [['已获取内容', '数量或结果', '单位', '范围与解释']]
out.getRange('A6:D6').format = {
  fill: purple,
  font: { name: font, size: 10, bold: true, color: '#FFFFFF' },
  rowHeight: 36,
}
const headline = [
  ['原文研究来源', 6, '篇', '定向检索；不代表系统综述或全部证据'],
  ['去重下载文件', 26, '份', '含1份只在本地处理的个体XLSX；资料包不含个人行'],
  ['原始访谈记录', 926, '人', '来自YANG2023分层访谈；筛查总体为6818'],
  ['原始变量', 74, '列', '字段字典含缺失率；ID/日期不导出值'],
  ['抑郁筛查比例差', null, '百分点', '2020年2月36.6%到4月57.0%；独立样本比较'],
  ['焦虑筛查比例差', null, '百分点', '2020年2月19.0%到4月36.7%；GAD-7>4'],
  ['BDI-II总分缺失', null, '人', '访谈数据918/926有值；缺失不填0'],
  ['发表年份组', 31, '组', '1988—2024发表年；不能当作调查年度趋势'],
  ['调整后关联指标', 73, '条', '来自公开回归表；同一研究不同分层/结局分开'],
  ['AI试验特征原表', 15, '行', '补充表S2合计1901；原文总数存在冲突'],
]
out.getRange('A7:D16').values = headline
out.getRange('A7:D16').format.rowHeight = 38
out.getRange('B11').formulas = [["='调查波次'!L9"]]
out.getRange('B12').formulas = [["='调查波次'!L10"]]
const bdiRow = d.microdata_dictionary.findIndex((r) => r.variable === 'BDI_II_Total') + 7
out.getRange('B13').formulas = [[`='原始变量字典'!G${bdiRow}`]]
out.getRange('B11:B12').setNumberFormat('0.0')
out.getRange('B7:B10').setNumberFormat('#,##0')
out.getRange('B13:B16').setNumberFormat('#,##0')
const findings = [
  [
    '观察',
    '同一研究两波筛查比例上升',
    '抑郁+20.4、焦虑+17.7个百分点',
    '可能与疫情期间学习/生活变化及样本构成有关，不能确认原因',
    '两次独立横断样本；阈值为CES-D>15、GAD-7>4',
  ],
  [
    '观察',
    '睡眠困扰与心理困扰存在调整后关联',
    'CHEN2023总样本OR6.99，95%CI6.69—7.30',
    '睡眠与情绪可能双向影响，存在残余混杂',
    'OR不是风险比；结局是抑郁或焦虑任一筛查阳性',
  ],
  [
    '观察',
    'AI聊天干预的结果因结局而异',
    '抑郁原始g0.50（0.18—0.82）；焦虑g0.42（−0.04—0.87）',
    '样本人群、对照、干预实现和随访可能造成差异',
    'AI综述异质性高；不能当成本项目已验证疗效',
  ],
  [
    '数据限制',
    '访谈样本不能直接代表筛查总体',
    '926分层访谈，sampling权重Kish近似n356.32',
    '不同层抽样概率影响估计；性别校准版本有待澄清',
    '不输出个人行，不自行重估诊断患病率',
  ],
  [
    '原文冲突',
    '研究数、样本量及部分统计量不一致',
    'FENG2025正文15/1901、摘要1974、讨论16/1974',
    '可能是版本/录入差异，实际原因未核实',
    '不覆盖原文；消极情感冲突行不用于疗效判断',
  ],
  [
    '无法判断',
    '本项目真实用户趋势及个体预测效果',
    '这些都是外部公开研究，未接入平台业务库',
    '需要本项目授权数据、有效观察窗和独立专业评测',
    '本次只提供研究数据整理、聚合与可复算资料',
  ],
]
table(
  out,
  'ResearchFindings',
  ['证据类型', '结论范围', '实际观察', '可能解释或驱动因素', '影响结论的限制'],
  findings,
  [20, 52, 85, 90, 94],
  { start: 20, height: 88 },
)
// Override compact upper summary widths only through shared columns; widths are consistent across rows.
out.getRange('A6:A16').format.columnWidth = 24
out.getRange('B6:B16').format.columnWidth = 33
out.getRange('C6:C16').format.columnWidth = 34
out.getRange('D6:D16').format.columnWidth = 76
out.getRange('A7:D16').format.wrapText = true
out.getRange('A20:E20').format.rowHeight = 38
out.getRange('A21:E26').format.rowHeight = 88
out.getRange('A28:E28').merge()
out.getRange('A28').values = [
  ['使用提示：跨研究比例不可直接排名；不能将全国教育人数乘以筛查率推算患者数。'],
]
out.getRange('A28').format.rowHeight = 34
out.getRange('G6:I6').values = [['调查期别', '抑郁症状', '焦虑症状']]
out.getRange('G7').values = [['2020年2月（n=9554）']]
out.getRange('G8').values = [['2020年4月（n=3886）']]
out.getRange('H7:I8').formulas = [
  ["='调查波次'!I7", "='调查波次'!I8"],
  ["='调查波次'!I9", "='调查波次'!I10"],
]
out.getRange('G6:G8').format.columnWidth = 33
out.getRange('H6:I8').format.columnWidth = 21
out.getRange('H7:I8').setNumberFormat('0.0%')
const chart = out.charts.add('line', out.getRange('G6:I8'))
chart.title = '两次独立调查的筛查阳性比例'
chart.titleTextStyle.typeface = font
chart.titleTextStyle.fontSize = 14
chart.legend = { position: 'top', textStyle: { typeface: font, fontSize: 11 } }
chart.xAxis = { axisType: 'textAxis', textStyle: { typeface: font, fontSize: 11 } }
chart.yAxis = {
  numberFormatCode: '0%',
  numberFormatSourceLinked: false,
  textStyle: { typeface: font, fontSize: 11 },
}
chart.series.items[0].line = { fill: purple, style: 'solid', width: 2 }
chart.series.items[1].line = { fill: color('accent-sage'), style: 'solid', width: 2 }
chart.setPosition('G11', 'N25')
out.mergeCells('G27:N27')
out.getRange('G27').values = [
  ['CHEN2021，CES-D>15与GAD-7>4；样本组成变化可能影响差异，不能推定个体病情加重。'],
]
out.getRange('G27:N27').format.wrapText = true
out.getRange('G27').format.rowHeight = 40
out.tabColor = purple

wb.recalculate()
const errors = await wb.inspect({
  kind: 'match',
  searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
  options: { useRegex: true, maxResults: 100 },
  maxChars: 2000,
})
await fs.writeFile(path.join(work, 'workbook-formula-errors.ndjson'), errors.ndjson)
const summary = await wb.inspect({
  kind: 'region',
  sheetId: '分析概览',
  range: 'A7:D16',
  maxChars: 3500,
  tableMaxRows: 10,
  tableMaxCols: 4,
})
await fs.writeFile(path.join(work, 'workbook-summary.ndjson'), summary.ndjson)
const output = path.join(root, 'deliverables/心域智链_文献数据下载与分析_20261028.xlsx')
await (await SpreadsheetFile.exportXlsx(wb)).save(output)
for (const name of names) {
  const range =
    name === '分析概览'
      ? 'A1:N28'
      : name === '文献与下载来源'
        ? 'A1:F12'
        : name === '调查波次'
          ? 'A1:K10'
          : name === 'AI干预效果'
            ? 'A1:J17'
            : name === '原始数据质量'
              ? 'A1:F17'
              : name === '来源问题'
                ? 'A1:F13'
                : 'A1:F14'
  const image = await wb.render({ sheetName: name, range, format: 'png', scale: 1 })
  await fs.writeFile(
    path.join(work, `preview-${name}.png`),
    new Uint8Array(await image.arrayBuffer()),
  )
}
await fs.writeFile(
  path.join(work, 'workbook-structure.json'),
  JSON.stringify({ output, sheets: names, ranges, formula_errors: errors.ndjson }, null, 2),
)
console.log(JSON.stringify({ output, sheets: names.length, formula_errors: errors.ndjson }))
