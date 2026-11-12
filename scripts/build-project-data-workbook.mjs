import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const work = path.join(root, 'tmp/data-inventory-20261028')
const bundledRequire = createRequire(path.join(work, 'runtime.cjs'))
const { Workbook, SpreadsheetFile } = await import(
  pathToFileURL(bundledRequire.resolve('@oai/artifact-tool')).href
)
const data = JSON.parse(await fs.readFile(path.join(work, 'inventory.json'), 'utf8'))
const tokenText = await fs.readFile(path.join(root, 'src/styles/tokens.css'), 'utf8')
const token = (name) => tokenText.match(new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})`))[1]
const ink = token('gray-800'),
  purple = token('brand-600'),
  light = token('brand-50')
const sage = token('accent-sage-soft')
const font = 'Microsoft YaHei'
const main = data.databases.find((d) => d.source_id === 'PREVIEW')
const model = data.models

const tableInfo = {
  users: ['账号权限', '用户账号', '一行一个账号'],
  user_access_states: ['账号权限', '账号访问状态', '一行一个账号的撤销状态'],
  teacher_student_assignments: ['账号权限', '教师学生授权关联', '一行一个教师与学生授权关系'],
  operator_account_events: ['账号权限', '操作员账号审计', '一行一个账号操作事件'],
  student_profiles: ['档案', '学生资料', '一行一个学生扩展资料'],
  teacher_profiles: ['档案', '教师资料', '一行一个教师扩展资料'],
  teacher_avatars: ['档案', '教师头像登记', '一行一个教师头像文件'],
  appointments: ['咨询支持', '咨询预约', '一行一次预约'],
  questions: ['咨询支持', '学生求助', '一行一条求助'],
  crisis_warnings: ['咨询支持', '危机提示', '一行一条系统提示'],
  intervention_records: ['咨询支持', '干预记录', '一行一条干预记录'],
  support_workflow_events: ['咨询支持', '求助及预警审计', '一行一个处理事件'],
  support_follow_ups: ['咨询支持', '跟进任务', '一行一项跟进任务'],
  support_follow_up_events: ['咨询支持', '跟进审计', '一行一个跟进事件'],
  test_results: ['测评报告', '测评结果', '一行一次测评'],
  psychological_reports: ['测评报告', '心理分析报告', '一行一个用户一天的报告'],
  report_analysis_cache: ['测评报告', '报告缓存', '一行一个用户一种报告缓存'],
  ai_chat_sessions: ['AI对话', '对话会话', '一行一个会话'],
  ai_chat_messages: ['AI对话', '对话消息', '一行一条消息'],
  chat_history_archive: ['AI对话', '结构化对话归档', '一行一组归档问答'],
  articles: ['内容', '文章与平台指南', '一行一篇文章'],
  knowledge_base: ['内容', '知识库', '一行一条知识内容'],
  treehole_posts: ['树洞', '树洞帖子', '一行一条帖子'],
  treehole_comments: ['树洞', '树洞评论', '一行一条评论'],
  treehole_likes: ['树洞', '树洞点赞', '一行一次点赞关系'],
  treehole_favorites: ['树洞', '树洞收藏', '一行一次收藏关系'],
  treehole_analysis: ['树洞', '树洞分析', '一行一个帖子分析'],
}
const meaning = {
  id: '记录主键',
  user_id: '用户内部ID',
  student_id: '学生账号内部ID',
  teacher_id: '教师账号内部ID',
  username: '登录用户名',
  password_hash: '密码哈希（不导出值）',
  role: '角色代码',
  name: '姓名',
  advisor: '自由填写的辅导员显示信息，不是授权依据',
  class_name: '班级名称',
  real_identity_flag: '真实身份关联标记',
  energy_points: '平台积分',
  created_at: '创建时间',
  updated_at: '更新时间',
  assigned_at: '授权关联创建时间',
  disabled: '是否停用账号',
  auth_epoch: '令牌撤销版本号',
  operator_name: '操作员名称',
  action: '事件动作代码',
  target_user_id: '被操作账号内部ID',
  reason: '处理原因',
  gender: '性别',
  parent_phone: '家长联系电话',
  remarks: '资料备注',
  chat_message_id: '触发消息内部ID',
  trigger_keyword: '触发提示的关键词',
  risk_level: '系统风险等级代码',
  status: '流程状态代码',
  processed_at: '处理时间',
  processed_by: '处理人账号内部ID',
  title: '标题或职称（随表定义）',
  intro: '教师简介',
  location: '咨询地点',
  avatar: '头像地址',
  time_slots: '可预约时段JSON数组',
  consultation_direction: '咨询方向',
  file_name: '头像文件名',
  relative_path: '头像相对路径',
  image_hash: '头像内容哈希',
  file_size: '文件大小，字节',
  time_slot: '预约时段文本',
  test_type: '测评类型代码',
  score: '原始分或总分，单位依测评类型',
  standard_score: '标准分，规则依测评类型',
  result_level: '测评结果等级',
  answers: '作答JSON文本，结构未固定',
  result_json: '测评详细结果JSON文本，兼容字段',
  summary: '摘要',
  content: '正文文本',
  cover_url: '封面地址',
  source: '文章来源名称',
  source_url: '文章来源链接',
  category: '文章分类',
  views: '阅读计数',
  anonymous_id: '匿名展示标识，仍可能关联个人',
  tags: '标签，逗号分隔',
  is_deep: '深度内容标记',
  emotion_keywords: '情绪关键词',
  reply_tip: '回复提示',
  post_id: '帖子内部ID',
  parent_id: '父评论内部ID',
  emotion_category: '情绪分类',
  core_values: '价值观关键词，逗号分隔',
  question_text: '求助问题文本',
  answer_text: '教师答复文本',
  subject_type: '事件对象类型',
  subject_id: '事件对象内部ID',
  actor_id: '操作账号内部ID',
  result_text: '处理结果文本',
  source_type: '跟进来源类型',
  source_id: '跟进来源内部ID',
  created_by: '任务创建人账号内部ID',
  due_at: '跟进到期时间',
  outcome: '跟进结果',
  completed_at: '完成时间',
  cancelled_at: '取消时间',
  follow_up_id: '跟进任务内部ID',
  note: '事件备注',
  record_date: '干预日期文本',
  notes: '干预记录正文',
  report_type: '缓存报告类型',
  payload_json: '报告缓存JSON文本',
  data_fingerprint: '报告输入指纹',
  source_updated_at: '报告来源数据最新时间',
  expires_at: '缓存到期时间',
  report_date: '报告日期文本',
  analysis_json: '心理报告JSON文本',
  mode: '会话模式',
  session_id: '会话内部ID',
  emotion_tags: '六类情绪权重JSON',
  is_crisis: '规则或模型危机提示标记',
  heatmap: '关键词模拟热度JSON，非模型注意力',
  user_message_id: '归档用户消息内部ID',
  ai_message_id: '归档AI消息内部ID',
  user_input: '归档用户输入',
  ai_reply: '归档AI回复',
  context_json: '历史上下文JSON',
  topic_tags: '话题标签，逗号分隔',
  sentiment_score: '规则计算情绪分，0—100，非临床概率',
  semantic_summary: '语义摘要',
}
const override = {
  'users.student_id': '学号文本；与其他表的student_id内部账号ID不同',
  'users.role': '账号角色代码',
  'teacher_profiles.title': '教师职称',
  'support_follow_ups.summary': '跟进任务摘要',
  'ai_chat_messages.role': '消息角色（user / ai / system）',
}
const enums = {
  'users.role': '默认student；注册/权限规则见认证代码',
  'ai_chat_sessions.mode': 'daily / counseling',
  'ai_chat_messages.role': 'user / ai / system',
  'appointments.status': 'pending / approved / cancelled（模型注释）',
  'questions.status': 'pending / answered（模型注释）',
  'crisis_warnings.status': 'pending / processed（模型注释）',
  'crisis_warnings.risk_level': 'low / medium / high（模型注释）',
  'test_results.risk_level': 'green / yellow / red（兼容字段）',
  'user_access_states.disabled': '0 / 1',
  'user_access_states.auth_epoch': '非负整数（代码CHECK约束）',
}
const jsonColumns = new Set([
  'emotion_tags',
  'heatmap',
  'context_json',
  'answers',
  'result_json',
  'payload_json',
  'analysis_json',
  'time_slots',
])
function sensitive(t, c) {
  if (c === 'password_hash') return '认证秘密：禁止导出值'
  if (t === 'articles' || t === 'knowledge_base') return '内容；需核验来源及许可'
  if (
    ['username', 'name', 'student_id', 'parent_phone', 'operator_name', 'anonymous_id'].includes(c)
  )
    return '身份或可关联标识'
  if (
    [
      'id',
      'user_id',
      'teacher_id',
      'actor_id',
      'session_id',
      'post_id',
      'parent_id',
      'follow_up_id',
      'target_user_id',
    ].includes(c) ||
    c.endsWith('_id')
  )
    return '内部关联标识'
  if (['测评报告', 'AI对话', '树洞', '咨询支持'].includes(tableInfo[t][0]))
    return '心理或支持服务敏感信息'
  return '内部资料或运行元数据'
}
function role(t, c) {
  if (c === 'password_hash') return '排除分析'
  if (c === 'id' || c.endsWith('_id')) return '关联键，不能直接作连续数值特征'
  if (c.endsWith('_at') || c.endsWith('_date')) return '时间维度，需统一时区及粒度'
  if (jsonColumns.has(c)) return '需解析的复合字段'
  if (
    ['score', 'standard_score', 'sentiment_score', 'views', 'energy_points', 'file_size'].includes(
      c,
    )
  )
    return '数值指标，需遵守字段口径'
  return '分类、文本或业务标记'
}

const wb = Workbook.create()
const sheetNames = [
  '数据概览',
  '字段字典',
  '数据表与记录量',
  '库间差异',
  'JSON子字段',
  '地区教育数据',
  '文献筛查数据',
]
const sheets = Object.fromEntries(sheetNames.map((n) => [n, wb.worksheets.add(n)]))
const col = (i) => {
  let s = ''
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26))
    s = String.fromCharCode(65 + ((n - 1) % 26)) + s
  return s
}
function heading(sh, title, subtitle, last = 'H') {
  sh.showGridLines = false
  sh.getRange(`A1:${last}45`).format.font = { name: font, size: 10, color: ink }
  sh.getRange(`A1:${last}45`).format.verticalAlignment = 'center'
  const titleLast = last < 'F' ? last : 'F'
  sh.mergeCells(`A2:${titleLast}2`)
  sh.getRange('A2').values = [[title]]
  sh.getRange(`A2:${titleLast}2`).format.font = { name: font, size: 15, bold: true, color: purple }
  sh.getRange('A2').format.rowHeight = 29
  sh.mergeCells(`A3:${titleLast}3`)
  sh.getRange('A3').values = [[subtitle]]
  sh.getRange('A3').format.rowHeight = 28
  sh.getRange(`A4:${last}4`).format.borders = { bottom: { style: 'thin', color: purple } }
}
function grid(sh, headers, rows, { start = 6, name, widths = [], height = 30 } = {}) {
  const end = start + rows.length,
    last = col(headers.length - 1)
  sh.getRange(`A${start}:${last}${end}`).values = [headers, ...rows]
  const r = sh.getRange(`A${start}:${last}${end}`)
  r.format.font = { name: font, size: 10, color: ink }
  r.format.verticalAlignment = 'center'
  r.format.rowHeight = height
  r.format.wrapText = true
  const t = sh.tables.add(`A${start}:${last}${end}`, true, name)
  t.style = 'TableStyleLight1'
  t.showFilterButton = true
  sh.getRange(`A${start}:${last}${start}`).format = {
    fill: purple,
    font: { name: font, size: 10, bold: true, color: '#FFFFFF' },
    wrapText: true,
    rowHeight: 36,
  }
  rows.forEach((_, i) => {
    if (i % 2 === 1) sh.getRange(`A${start + i + 1}:${last}${start + i + 1}`).format.fill = light
  })
  widths.forEach(
    (w, i) => (sh.getRange(`${col(i)}${start}:${col(i)}${end}`).format.columnWidth = w),
  )
  sh.freezePanes.freezeRows(start)
  return { start, end, last }
}

// Full physical-column dictionary: not inferred from model declarations alone.
const fieldRows = []
for (const t of main.tables)
  for (const c of t.columns) {
    const m = model[t.name]?.[c.name]
    const present = data.databases
      .filter((d) =>
        d.tables.some((x) => x.name === t.name && x.columns.some((y) => y.name === c.name)),
      )
      .map((d) => d.source_id)
      .join(', ')
    const nullable = c.notnull
      ? '不允许'
      : c.pk_order && c.sql_type === 'INTEGER'
        ? '整数主键，隐式非空'
        : '允许'
    fieldRows.push([
      tableInfo[t.name][0],
      t.name,
      c.name,
      override[`${t.name}.${c.name}`] || meaning[c.name] || c.name,
      c.sql_type,
      nullable,
      c.pk_order || '',
      c.unique_alone ? '是' : '否',
      c.foreign_keys.join('; ') || '无声明',
      c.sql_default ?? '未声明',
      m?.app_default || '未声明',
      enums[`${t.name}.${c.name}`] || m?.model_comment || '',
      sensitive(t.name, c.name),
      role(t.name, c.name),
      present,
      `${m?.source || '未映射'}:${m?.line || ''}`,
    ])
  }
heading(
  sheets.字段字典,
  '数据库字段字典',
  '198个物理字段。PREVIEW为完整参考结构；字段同名不代表跨表含义相同。',
  'P',
)
grid(
  sheets.字段字典,
  [
    '模块',
    '数据表',
    '字段变量',
    '中文含义',
    'SQLite类型',
    '允许NULL',
    '主键顺序',
    '单列唯一',
    '外键声明',
    '库端默认',
    '应用端默认',
    '代码说明或枚举',
    '数据敏感性',
    '分析用途',
    '存在于哪些库',
    '模型位置',
  ],
  fieldRows,
  {
    name: 'FieldDictionary',
    widths: [13, 31, 24, 55, 17, 22, 11, 11, 55, 23, 23, 54, 32, 41, 64, 33],
    height: 42,
  },
)

const tableRows = []
for (const d of data.databases)
  for (const t of d.tables)
    tableRows.push([
      d.source_id,
      tableInfo[t.name]?.[0] || '未映射',
      t.name,
      tableInfo[t.name]?.[1] || t.name,
      t.column_count,
      t.row_count,
      tableInfo[t.name]?.[2] || '',
      t.indexes
        .filter((i) => i.unique)
        .map((i) => `(${i.columns.join(', ')})`)
        .join('; ') || '无唯一索引',
      d.foreign_key_issues.filter((i) => i.table === t.name).reduce((n, i) => n + i.count, 0),
      d.provenance,
    ])
heading(
  sheets.数据表与记录量,
  '数据表与记录量',
  '各库分别计数，跨表行数与跨库副本不可相加作为用户量。仅导出聚合计数。',
  'J',
)
grid(
  sheets.数据表与记录量,
  [
    '库标识',
    '模块',
    '数据表',
    '用途',
    '字段数',
    '记录数',
    '一行代表什么',
    '唯一约束的字段组合',
    '外键异常条数',
    '来源性质',
  ],
  tableRows,
  { name: 'TableInventory', widths: [23, 14, 32, 26, 12, 12, 40, 57, 18, 66], height: 36 },
)

const differences = []
for (const d of data.databases)
  if (d.source_id !== 'PREVIEW') {
    const found = Object.fromEntries(d.tables.map((t) => [t.name, t]))
    for (const t of main.tables) {
      if (!found[t.name])
        differences.push([
          d.source_id,
          t.name,
          '缺少整张表',
          t.column_count,
          'PREVIEW存在；该库未建此表，不在本轮执行迁移',
        ])
      else
        for (const c of t.columns)
          if (!found[t.name].columns.some((x) => x.name === c.name))
            differences.push([
              d.source_id,
              t.name,
              `缺少字段 ${c.name}`,
              1,
              '物理schema差异；与空表/空值不同',
            ])
    }
    for (const t of d.tables)
      for (const c of t.columns) {
        const reference = main.tables
          .find((x) => x.name === t.name)
          ?.columns.find((x) => x.name === c.name)
        if (!reference)
          differences.push([d.source_id, t.name, `额外字段 ${c.name}`, 1, '仅此来源存在'])
        else if (
          reference.sql_type !== c.sql_type ||
          reference.notnull !== c.notnull ||
          reference.pk_order !== c.pk_order
        )
          differences.push([
            d.source_id,
            t.name,
            `类型/非空/主键差异 ${c.name}`,
            1,
            '详见本轮schema机器记录',
          ])
      }
    for (const issue of d.foreign_key_issues)
      differences.push([
        d.source_id,
        issue.table,
        `外键指向 ${issue.parent} 不匹配`,
        issue.count,
        '仅记录表级计数；原数据未修改',
      ])
  }
heading(
  sheets.库间差异,
  '数据库结构与完整性差异',
  '以PREVIEW的27表198字段作比较。差异是文件间现状，不表示已确认哪个文件由运行服务加载。',
  'E',
)
grid(sheets.库间差异, ['库标识', '数据表', '发现', '涉及字段或异常条数', '说明'], differences, {
  name: 'SchemaDifferences',
  widths: [24, 34, 56, 25, 84],
  height: 34,
})

const jsonRows = []
const addJson = (t, c, k, type, desc, origin) =>
  jsonRows.push([t, c, k, type, desc, '代码已声明/写入；本轮未读取JSON记录值', origin])
for (const k of ['joy', 'sadness', 'neutral', 'fear', 'anxiety', 'anger'])
  addJson(
    'ai_chat_messages',
    'emotion_tags',
    k,
    'number',
    '情绪权重；非经校准的临床概率',
    'backend/app/routers/advanced_chat.py:72',
  )
for (const [k, type, desc] of [
  ['[].token', 'string', '字符或关键词'],
  ['[].weight', 'number', '模拟热度权重，非模型真实注意力'],
  ['[].is_keyword', 'boolean', '是否命中关键词'],
])
  addJson('ai_chat_messages', 'heatmap', k, type, desc, 'backend/app/services/nlp_engine.py:81')
for (const [k, type, desc] of [
  ['turns', 'integer', '最多8条历史消息的数量，代码命名turns'],
  ['messages', 'array', '历史消息快照'],
])
  addJson(
    'chat_history_archive',
    'context_json',
    k,
    type,
    desc,
    'backend/app/routers/advanced_chat.py:197',
  )
addJson(
  'teacher_profiles',
  'time_slots',
  '[]',
  'string',
  '可预约时段字符串数组',
  'backend/app/schemas.py:81',
)
for (const c of ['answers', 'result_json'])
  addJson(
    'test_results',
    c,
    '未固定',
    'JSON文本',
    'API接受字符串；本轮不假定内部键或读取作答值',
    'backend/app/schemas.py:50',
  )
for (const [k, type, desc] of [
  ['source.message_count', 'integer', '所用消息条数'],
  ['source.messages', 'array', '敏感消息明细，禁止本轮导出'],
  ['scores.emotion', 'integer', '生成或规则情绪分'],
  ['scores.cognition', 'integer', '生成或规则认知分'],
  ['scores.behavior', 'integer', '生成或规则行为分'],
  ['risk.risk_level', 'string', 'LOW / MEDIUM / HIGH，系统分级'],
  ['risk.depression_confidence', 'integer', '代码命名confidence，未经校准，不是诊断概率'],
  ['risk.anxiety_confidence', 'integer', '代码命名confidence，未经校准，不是诊断概率'],
  ['risk.suicide_confidence', 'integer', '代码命名confidence，未经校准，不是诊断概率'],
  ['trends.seven_days', 'array', '7天汇总结构'],
  ['trends.thirty_days', 'array', '30天汇总结构'],
  ['trends.heatmap', 'array', '汇总热图结构'],
  ['trends.radar', 'object', '规则雷达维度'],
  ['interventions', 'array', '生成或回退建议'],
  ['chart_insights', 'object', '图表文字说明'],
  ['chart_explanations', 'object', '图表文字说明兼容字段'],
  ['updated_at', 'string', '生成时UTC时间文本'],
  ['generated_mode', 'string', 'full / quick'],
])
  addJson(
    'psychological_reports',
    'analysis_json',
    k,
    type,
    desc,
    'backend/app/services/dialogue_analysis_service.py:278',
  )
for (const [k, type, desc] of [
  ['ai_analysis', 'string', '分析草稿'],
  ['analysis_basis', 'object', '分析依据结构'],
  ['recent_themes', 'array', '最近主题'],
  ['deep_moment', 'object/null', '精选树洞内容'],
  ['score_distribution', 'object', '按SDS/SAS分类的测评分布数组'],
  ['risk_stats', 'object', '风险分布'],
  ['avg_scores', 'object', '平均分结构'],
])
  addJson(
    'report_analysis_cache',
    'payload_json',
    k,
    type,
    `${desc}；仅student_mental_report写入路径，其他类型可不同`,
    'backend/app/routers/student.py:625',
  )
heading(
  sheets.JSON子字段,
  'JSON字段与内部变量',
  '这些是源码中明确使用的键，属于TEXT列内部结构，不计入198个数据库物理字段。',
  'G',
)
grid(
  sheets.JSON子字段,
  ['数据表', '物理字段', '内部变量路径', '代码类型', '含义及限制', '核验范围', '代码来源'],
  jsonRows,
  { name: 'JsonVariables', widths: [33, 23, 40, 17, 86, 54, 66], height: 44 },
)

heading(
  sheets.地区教育数据,
  '2024年地区教育数据',
  '31个大陆地区。学生单位为人，高校单位为所；F列原始合计是D＋E，不含研究生、成人和网络本专科。',
  'L',
)
const regRows = data.regional.map((r) => [
  r.region,
  r.year,
  r.regular_vocational_heis,
  r.academic_bachelor_students,
  r.vocational_normal_short_students,
  r.normal_vocational_undergraduates,
  r.regular_senior_students,
  r.junior_students,
  null,
  null,
  null,
  null,
])
grid(
  sheets.地区教育数据,
  [
    '地区',
    '年份',
    '普通/职业高校数（所）',
    '普通本科在校生（人）',
    '职业本专科在校生（人）',
    '本专科合计（人）',
    '普通高中在校生（人）',
    '初中在校生（人）',
    '本专科占31地比重',
    '每所高校平均本专科生（人/所）',
    '本专科规模排序',
    '合计校验差额（人）',
  ],
  regRows,
  {
    name: 'RegionalEducation',
    widths: [14, 11, 22, 25, 27, 24, 26, 25, 23, 29, 20, 23],
    height: 32,
  },
)
for (let r = 7; r <= 37; r++)
  sheets.地区教育数据.getRange(`I${r}:L${r}`).formulas = [
    [
      `=F${r}/SUM($F$7:$F$37)`,
      `=IF(C${r}=0,"n.a.",F${r}/C${r})`,
      `=RANK(F${r},$F$7:$F$37,0)`,
      `=F${r}-SUM(D${r}:E${r})`,
    ],
  ]
sheets.地区教育数据.getRange('C7:H37').setNumberFormat('#,##0')
sheets.地区教育数据.getRange('I7:I37').setNumberFormat('0.00%')
sheets.地区教育数据.getRange('J7:J37').setNumberFormat('#,##0.0')
const regMeta = JSON.parse(
  await fs.readFile(
    path.join(root, 'docs/plan/ai-application/revision-20261027/regional-education-2024.json'),
    'utf8',
  ),
)
for (let i = 0; i < 5; i++) {
  const [k, v] = Object.entries(regMeta.sources)[i],
    row = i + 41,
    sh = sheets.地区教育数据
  sh.getRange(`A${row}:B${row}`).values = [[k, v.title]]
  sh.mergeCells(`C${row}:H${row}`)
  sh.getRange(`C${row}`).values = [[v.url]]
  sh.mergeCells(`I${row}:L${row}`)
  sh.getRange(`I${row}`).values = [['项目已保存的2024数据；本轮未完整重验官网']]
}
sheets.地区教育数据.getRange('A40:B40').values = [['来源字段', '原网页标题']]
sheets.地区教育数据.mergeCells('C40:H40')
sheets.地区教育数据.getRange('C40').values = [['官方URL']]
sheets.地区教育数据.mergeCells('I40:L40')
sheets.地区教育数据.getRange('I40').values = [['本轮状态']]
sheets.地区教育数据.getRange('A40:D45').format.rowHeight = 32
sheets.地区教育数据.getRange('C41:H45').format.wrapText = false

heading(
  sheets.文献筛查数据,
  '文献中的抑郁症状筛查汇总',
  '同一2024年综述。筛查阳性不等于临床诊断；学段/地区研究亚组的k、n不可跨组相加。',
  'I',
)
const lit = data.literature,
  stageMap = {
    'Primary school': '小学',
    'Middle school': '初中',
    'High school': '高中',
    'Undergraduate school': '本科',
  }
const litRows = [
  [
    '总体',
    '全部纳入研究',
    lit.study.included_studies_total,
    lit.study.included_participants_total,
    lit.study.overall.estimate_percent / 100,
    lit.study.overall.ci95_lower_percent / 100,
    lit.study.overall.ci95_upper_percent / 100,
    lit.study.overall.i2_percent / 100,
    '439项研究；非单一调查年份',
  ],
]
for (const r of lit.study.education_stage_subgroups)
  litRows.push([
    '学段',
    stageMap[r.stage],
    r.studies_k,
    r.sample_n,
    r.estimate_percent / 100,
    r.ci95_lower_percent / 100,
    r.ci95_upper_percent / 100,
    r.i2_percent / 100,
    '学段亚组按原表保留；样本可跨学段覆盖，不能相加',
  ])
for (const r of lit.geographic_subgroups.rows)
  litRows.push([
    '地区研究亚组',
    r.region,
    r.studies_k,
    r.sample_n,
    r.estimate_percent / 100,
    r.ci95_lower_percent / 100,
    r.ci95_upper_percent / 100,
    r.i2_percent / 100,
    '原33个地区条目，含港澳；非代表性省级人群率',
  ])
grid(
  sheets.文献筛查数据,
  [
    '层级',
    '组别',
    '研究数k',
    '样本数n',
    '筛查阳性合并比例',
    '95%CI下限',
    '95%CI上限',
    'I²',
    '口径与限制',
  ],
  litRows,
  { name: 'LiteratureScreening', widths: [22, 28, 16, 17, 25, 19, 19, 15, 85], height: 38 },
)
sheets.文献筛查数据.getRange(`E7:H${6 + litRows.length}`).setNumberFormat('0.00%')
sheets.文献筛查数据.getRange(`C7:D${6 + litRows.length}`).setNumberFormat('#,##0')
let litEnd = 9 + litRows.length
sheets.文献筛查数据.mergeCells(`A${litEnd}:I${litEnd}`)
sheets.文献筛查数据.getRange(`A${litEnd}`).values = [
  ['原文：https://link.springer.com/article/10.1186/s13034-024-00841-w（本轮已在线打开核验摘要）'],
]
sheets.文献筛查数据.mergeCells(`A${litEnd + 1}:I${litEnd + 1}`)
sheets.文献筛查数据.getRange(`A${litEnd + 1}`).values = [
  [
    '补充表S2：https://media.springernature.com/original/springer-static/esm/art%3A10.1186%2Fs13034-024-00841-w/MediaObjects/13034_2024_841_MOESM4_ESM.pdf',
  ],
]
sheets.文献筛查数据.mergeCells(`A${litEnd + 2}:I${litEnd + 2}`)
sheets.文献筛查数据.getRange(`A${litEnd + 2}`).values = [
  [
    '保留原表问题：学段n总和超过总体n；地区k之和与总体439项不符；天津来源多地研究。不能自行纠正或把亚组相加。',
  ],
]
sheets.文献筛查数据.getRange(`A${litEnd}:I${litEnd + 2}`).format.rowHeight = 28

const ov = sheets.数据概览
heading(
  ov,
  '心域智链项目数据与数据库变量',
  '只读盘点日期：2026-10-28（北京时间）。服务当前绑定库未验证，以下分别标识各库。',
  'L',
)
grid(
  ov,
  ['库标识', '数据表数', '字段数', '完整性检查', '外键异常条数', '文件角色'],
  data.databases.map((d) => [
    d.source_id,
    d.table_count,
    d.column_count,
    d.quick_check,
    d.fk_issue_count,
    d.provenance,
  ]),
  { name: 'DatabaseSummary', widths: [24, 15, 15, 18, 22, 65], height: 38 },
)
ov.getRange('A15:F15').values = [['关键事实', '数值或状态', '说明', null, null, null]]
const summaryRows = [
  ['完整参考结构字段数', null, 'PREVIEW物理schema，与当前模型字段集合一致'],
  ['预览账号数', null, 'users为空；真实业务趋势不可计算'],
  ['预览指南文章数', null, '这是平台使用指南；不是医学研究样本'],
  ['31地区本专科总人数', null, '2024年普通本科＋职业本专科，不含研究生、成人及网络本专科'],
  ['前5地区本专科占比', null, '按本专科人数排序后的CR5，反映规模集中程度'],
  ['31地区本专科规模变异系数', null, '总体标准差÷均值；横截面离散程度，不是时间变化'],
  [
    '高中与小学筛查比例差（百分点）',
    null,
    '28.23%－16.97%，为跨研究亚组描述差异，不能解释为年龄因果效应',
  ],
]
ov.getRange('A16:C22').values = summaryRows
ov.getRange('A15:F22').format.rowHeight = 35
ov.getRange('A15:F22').format.font = { name: font, size: 10, color: ink }
ov.getRange('A16:A22').format.wrapText = true
ov.getRange('A15:F15').format.fill = sage
ov.getRange('B16').formulas = [["=COUNTA('字段字典'!C7:C204)"]]
const usersIndex = tableRows.findIndex((r) => r[0] === 'PREVIEW' && r[2] === 'users') + 7
const articlesIndex = tableRows.findIndex((r) => r[0] === 'PREVIEW' && r[2] === 'articles') + 7
ov.getRange('B17').formulas = [[`='数据表与记录量'!F${usersIndex}`]]
ov.getRange('B18').formulas = [[`='数据表与记录量'!F${articlesIndex}`]]
ov.getRange('B19').formulas = [["=SUM('地区教育数据'!F7:F37)"]]
ov.getRange('B20').formulas = [
  [
    "=(LARGE('地区教育数据'!F7:F37,1)+LARGE('地区教育数据'!F7:F37,2)+LARGE('地区教育数据'!F7:F37,3)+LARGE('地区教育数据'!F7:F37,4)+LARGE('地区教育数据'!F7:F37,5))/B19",
  ],
]
ov.getRange('B21').formulas = [["=STDEVP('地区教育数据'!F7:F37)/AVERAGE('地区教育数据'!F7:F37)"]]
ov.getRange('B22').formulas = [["=('文献筛查数据'!E10-'文献筛查数据'!E8)*100"]]
ov.getRange('B16:B19').setNumberFormat('#,##0')
ov.getRange('B20:B21').setNumberFormat('0.00%')
ov.getRange('B22').setNumberFormat('0.00')
ov.getRange('C16:C22').format.wrapText = false
ov.getRange('A25:F25').values = [
  ['类型', '观察到的模式或异常', '可能解释', '对分析的影响', '待核实事项', '处理建议'],
]
const findings = [
  [
    '已观察',
    '预览只有8篇指南，用户/测评/聊天均为空',
    '该副本按指南预览用途准备（项目记录）',
    '无法估计用户增长、测评风险率、干预效果',
    '当前服务是否仍使用此库',
    '先确认分析目标库，再做授权内的聚合分析',
  ],
  [
    '已观察',
    '历史库结构分别17表120字段、21表157字段',
    '历史阶段结构不同；具体迁移经过未核实',
    '不可把源码27表当成历史库既有结构',
    '历史库用途及当前服务绑定',
    '保留原库，按库标识解释字段',
  ],
  [
    '已观察',
    'BACKEND_HEALTH有1条psychological_reports到users的外键异常',
    '可能与历史导入或删除流程有关，未验证原因',
    '相关关联查询可能漏掉这条报告',
    '需由操作员核查归属，未导出记录标识',
    '本轮只记录聚合，不改原库',
  ],
  [
    '已观察',
    '本专科人数分布存在地区差异，CR5/CV见上方',
    '地区人口与教育机构布局可能相关，尚未检验',
    '是教育规模差异，不是心理需求/付费市场估计',
    '需独立人口、资源与采样证据',
    '仅作2024年地区规模比较',
  ],
  [
    '已观察',
    '综述高中28.23%、小学16.97%，I²约99%—100%',
    '量表阈值、抽样及研究时期差异可能影响结果',
    '跨研究差异不证明学段导致风险变化',
    '需可比个体数据与预先定义的混杂因素',
    '不与教育规模相乘推算患者数',
  ],
  [
    '无法判断',
    '项目业务时间趋势与潜在驱动因素',
    '缺少已确认真实纵向样本及相同口径基线',
    '不能从空表、旧库或研究亚组制造时间趋势',
    '有效观察期、去重人数及缺失模式',
    '补足合规聚合样本后再分析',
  ],
  [
    '代码事实',
    'sentiment_score是规则分；heatmap是关键词模拟热度',
    '字段名或图形可能使其看起来像模型概率/注意力',
    '不能当作诊断标签或经过校准的概率',
    '真实模型版本、专业评测及标注',
    '保留计算口径，避免越界解释',
  ],
]
ov.getRange('A26:F32').values = findings
ov.getRange('A25:F32').format.wrapText = true
ov.getRange('A25:F25').format.fill = sage
ov.getRange('A26:F32').format.rowHeight = 86
ov.getRange('B26:E32').format.columnWidth = 34
ov.getRange('F26:F32').format.columnWidth = 48
ov.getRange('A35').values = [['库标识']]
for (let r = 35; r <= 41; r++) {
  ov.mergeCells(`B${r}:D${r}`)
  ov.mergeCells(`E${r}:G${r}`)
}
ov.getRange('B35').values = [['文件路径（相对项目）']]
ov.getRange('E35').values = [['说明']]
data.databases.forEach((d, i) => {
  const r = 36 + i
  ov.getRange(`A${r}`).values = [[d.source_id]]
  ov.getRange(`B${r}`).values = [[d.path]]
  ov.getRange(`E${r}`).values = [[d.provenance]]
})
ov.getRange('A35:F41').format.rowHeight = 32
ov.getRange('B36:C41').format.wrapText = false
ov.getRange('A43').values = [
  [
    'NULL表示缺失；空表的缺失率不可当成0%。应用端default不等于SQLite库端默认。完整字段均可在“字段字典”筛选。',
  ],
]
ov.mergeCells('A43:L43')
ov.getRange('A43:L43').format.rowHeight = 32
ov.getRange('H6:L6').values = [['地区', '2024本专科在校生（人）', null, null, null]]
const sortedRegions = [...data.regional]
  .sort((a, b) => b.normal_vocational_undergraduates - a.normal_vocational_undergraduates)
  .slice(0, 10)
for (let i = 0; i < 10; i++) {
  const rr = data.regional.findIndex((r) => r.region === sortedRegions[i].region) + 7
  ov.getRange(`H${i + 7}:I${i + 7}`).formulas = [
    [`='地区教育数据'!A${rr}`, `='地区教育数据'!F${rr}`],
  ]
}
ov.getRange('H6:I16').format.columnWidth = 25
ov.getRange('I7:I16').setNumberFormat('#,##0')
const chart = ov.charts.add('bar', ov.getRange('H6:I16'))
chart.title = '2024年本专科在校生最多的10个地区'
chart.titleTextStyle.typeface = font
chart.titleTextStyle.fontSize = 13
chart.hasLegend = false
chart.xAxis = { axisType: 'textAxis', textStyle: { typeface: font, fontSize: 11 } }
chart.yAxis = {
  numberFormatCode: '0.0,,"百万"',
  numberFormatSourceLinked: false,
  textStyle: { typeface: font, fontSize: 11 },
}
chart.series.items[0].fill = purple
chart.setPosition('H18', 'O33')
ov.tabColor = purple

wb.recalculate()
const summary = await wb.inspect({
  kind: 'region',
  sheetId: '数据概览',
  range: 'A16:C22',
  maxChars: 2800,
  tableMaxCols: 3,
  tableMaxRows: 7,
})
await fs.writeFile(path.join(work, 'summary-inspection.ndjson'), summary.ndjson)
const errors = await wb.inspect({
  kind: 'match',
  searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',
  options: { useRegex: true, maxResults: 100 },
  maxChars: 2000,
})
await fs.writeFile(path.join(work, 'formula-errors.ndjson'), errors.ndjson)
const output = path.join(root, 'deliverables/心域智链_数据库变量与项目数据_20261028.xlsx')
await (await SpreadsheetFile.exportXlsx(wb)).save(output)
const previews = [
  ['数据概览', 'A1:O33'],
  ['字段字典', 'A1:F15'],
  ['数据表与记录量', 'A1:F15'],
  ['库间差异', 'A1:E14'],
  ['JSON子字段', 'A1:F14'],
  ['地区教育数据', 'A1:F16'],
  ['文献筛查数据', 'A1:I13'],
]
for (const [name, range] of previews) {
  const blob = await wb.render({ sheetName: name, range, scale: 1, format: 'png' })
  await fs.writeFile(path.join(work, `${name}.png`), new Uint8Array(await blob.arrayBuffer()))
}
const profile = {
  as_of: data.as_of,
  source_database_unchanged: data.databases.every((d) => d.file_unchanged_during_read),
  field_count: fieldRows.length,
  table_inventory_rows: tableRows.length,
  delta_rows: differences.length,
  json_rows: jsonRows.length,
  region_rows: regRows.length,
  literature_rows: litRows.length,
  output,
  summary: summary.ndjson,
  formula_errors: errors.ndjson,
  sheet_names: sheetNames,
}
await fs.writeFile(path.join(work, 'workbook-verification.json'), JSON.stringify(profile, null, 2))
console.log(
  JSON.stringify({
    output,
    fields: fieldRows.length,
    sheets: sheetNames.length,
    formulaErrors: errors.ndjson,
    summary: summary.ndjson,
  }),
)
