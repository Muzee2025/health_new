import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const assetRoot = path.join(root, 'src/assets')
const require = createRequire(import.meta.url)
let sharp
try {
  sharp = require(process.env.SHARP_MODULE_PATH || 'sharp')
} catch {
  for (const moduleRoot of (process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean)) {
    try {
      sharp = require(path.join(moduleRoot, 'sharp'))
      break
    } catch {
      /* Try next configured module root. */
    }
  }
}
if (!sharp)
  throw new Error(
    'sharp is required. Set SHARP_MODULE_PATH to an existing sharp module, or NODE_PATH to its node_modules directory. No install is performed.',
  )
const date = '2026-10-21'
// Digests must not depend on the checkout's line endings: Windows autocrlf writes
// CRLF while a Linux CI checkout writes LF. Text inputs are digested after
// CRLF->LF normalisation, binary inputs byte-for-byte. This must stay identical to
// hashFile() in scripts/check-assets.mjs, which verifies what is written here.
const TEXT_ASSET = /\.(?:svg|txt|md|json|css|js|mjs)$/i
const digestFor = (relative, bytes) =>
  crypto
    .createHash('sha256')
    .update(
      TEXT_ASSET.test(relative)
        ? Buffer.from(bytes.toString('utf8').replace(/\r\n/g, '\n'), 'utf8')
        : bytes,
    )
    .digest('hex')
const css = await fs.readFile(path.join(root, 'src/styles/tokens.css'), 'utf8')
const tokens = Object.fromEntries(
  [...css.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]),
)
function t(key, seen = []) {
  if (!tokens[key] || seen.includes(key)) throw new Error(`Invalid token: ${key}`)
  return tokens[key].replace(/var\(--([\w-]+)\)/g, (_, name) => t(name, [...seen, key]))
}
const c = {
  brand: t('brand-500'),
  deep: t('brand-600'),
  pale: t('brand-100'),
  ink: t('gray-800'),
  paper: t('gray-0'),
  muted: t('gray-600'),
  line: t('gray-300'),
  blue: t('info'),
  sky: t('info-100'),
  yellow: t('warning-100'),
  green: t('success-100'),
  apricot: t('accent-apricot'),
  apricotSoft: t('accent-apricot-soft'),
  sage: t('accent-sage'),
  sageSoft: t('accent-sage-soft'),
  warm: t('surface-warm'),
}
const svg = (w, h, body, title = '心域智链项目自制素材') =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img"><title>${title}</title>${body}</svg>`
const entries = []
async function save(relative, contents, size, usage, status = 'approved') {
  const target = path.join(assetRoot, relative)
  await fs.mkdir(path.dirname(target), { recursive: true })
  const output = Buffer.isBuffer(contents) ? contents : Buffer.from(contents)
  let previous
  try {
    previous = await fs.readFile(target)
  } catch (error) {
    if (error.code !== 'ENOENT') throw error
  }
  if (!previous?.equals(output)) await fs.writeFile(target, output)
  const data = await fs.readFile(target)
  entries.push({
    id: path.basename(relative).replace(/\./g, '-'),
    path: relative.replaceAll('\\', '/'),
    type: path.extname(relative).slice(1),
    size,
    usage,
    license: status === 'approved' ? 'LicenseRef-Project-Original' : 'unverified',
    source:
      status === 'approved'
        ? '项目自制：scripts/build-design-assets.mjs 原创贝塞尔矢量源'
        : '仓库既有文件；原始来源与授权待核实',
    owner:
      status === 'approved'
        ? relative.startsWith('avatars/')
          ? '心域智链项目组（B / E03 原作；R1 品牌色适配）'
          : relative.startsWith('icons/icon-domain')
            ? '心域智链项目组（B / E03 原作）'
            : '心域智链项目组（B / R1 制作）'
        : '原作者待核实',
    status,
    sha256: digestFor(relative, data),
  })
}
// The paired folios are unequal in width. A continuous open path remains between them.
// No heart, head, medical cross, network nodes, or infinite loop is used.
function mark(color = c.deep, secondary = c.apricot, compact = false) {
  return compact
    ? `<path d="M15 20C33 20 45 31 45 49V79C26 74 15 61 15 43Z" fill="${color}"/><path d="M55 79V49C55 31 67 20 83 18V41C83 62 73 74 55 79Z" fill="${secondary}"/>`
    : `<path d="M14 19C31 19 45 30 45 49V79C28 75 14 62 14 44Z" fill="${color}"/><path d="M54 79V49C54 31 67 20 82 17V41C82 61 72 74 54 79Z" fill="${secondary}"/>${color === secondary ? '' : `<path d="M26 35C33 40 36 47 36 57" fill="none" stroke="${c.paper}" stroke-opacity=".5" stroke-width="2" stroke-linecap="round"/>`}`
}
function shelter(color = c.deep, secondary = c.apricot) {
  return `<path d="M20 77V44C20 25 32 14 48 14C64 14 76 25 76 44V55" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round"/><path d="M38 70C38 57 48 48 61 48C61 61 51 70 38 70Z" fill="${secondary}"/><path d="M36 82H76" fill="none" stroke="${color}" stroke-width="8" stroke-linecap="round"/>`
}
function response(color = c.deep, secondary = c.apricot) {
  return `<path d="M15 31C15 22 22 16 31 16H43V49C43 65 34 75 20 80V66C27 62 30 56 30 50H15Z" fill="${color}"/><path d="M81 65C81 74 74 80 65 80H53V47C53 31 62 21 76 16V30C69 34 66 40 66 46H81Z" fill="${secondary}"/>`
}
const concepts = [
  {
    key: 'xiangban',
    label: '相伴',
    sub: '同页同行',
    desc: '两页之间，留一条向前的路。',
    draw: mark,
  },
  {
    key: 'yongguang',
    label: '拥光',
    sub: '安心停留',
    desc: '开放的门廊，托住一束暖光。',
    draw: shelter,
  },
  {
    key: 'zhiyin',
    label: '知音',
    sub: '倾听回应',
    desc: '你说的话，在这里获得回应。',
    draw: response,
  },
]
for (const concept of concepts) {
  await save(
    `brand/concepts/brand-concept-${concept.key}.svg`,
    svg(96, 96, concept.draw(), `心域智链候选 ${concept.label}：${concept.sub}`),
    [96, 96],
    `品牌比较候选 ${concept.label}；${concept.key === 'xiangban' ? '推荐默认，正式引用使用brand-logo或brand-mark' : '仅供比较，不作为当前默认品牌'}`,
  )
  if (concept.key !== 'xiangban')
    for (const variant of ['mono', 'reverse']) {
      const color = variant === 'mono' ? c.deep : c.paper
      await save(
        `brand/concepts/brand-concept-${concept.key}-${variant}.svg`,
        svg(96, 96, concept.draw(color, color), `${concept.label}候选${variant}`),
        [96, 96],
        `${concept.label}候选真实矢量${variant}导出；反白需置深色底`,
      )
    }
}
const comparison = svg(
  1200,
  650,
  `<rect width="1200" height="650" fill="${c.warm}"/><text x="64" y="76" font-family="Microsoft YaHei,sans-serif" font-size="29" font-weight="600" fill="${c.ink}">心域智链 · 温暖、有陪伴感、偏人文</text><text x="64" y="111" font-family="Microsoft YaHei,sans-serif" font-size="15" fill="${c.muted}">校园心理支持的三种表达</text>${concepts.map((item, i) => `<g transform="translate(${64 + i * 376} 170)"><rect width="344" height="404" rx="16" fill="${c.paper}" stroke="${i ? c.line : c.deep}" stroke-width="${i ? 1 : 2}"/><g transform="translate(92 42) scale(1.65)">${item.draw()}</g><text x="28" y="253" font-family="Microsoft YaHei,sans-serif" font-size="25" font-weight="600" fill="${c.deep}">${item.label}</text><text x="28" y="287" font-family="Microsoft YaHei,sans-serif" font-size="17" fill="${c.ink}">${item.sub}</text><text x="28" y="320" font-family="Microsoft YaHei,sans-serif" font-size="14" fill="${c.muted}">${item.desc}</text><text x="28" y="373" font-family="Microsoft YaHei,sans-serif" font-size="13" fill="${c.deep}">${i ? '可比较候选' : '推荐 · 书页与道路兼具校园识别'}</text></g>`).join('')}`,
  '品牌三候选比较：推荐相伴，候选拥光、知音',
)
await save(
  'brand/concepts/brand-concepts-comparison.svg',
  comparison,
  [1200, 650],
  '品牌比较画板；自制矢量，推荐相伴',
)
await save(
  'brand/concepts/brand-concepts-comparison-1200.png',
  await sharp(Buffer.from(comparison)).png().toBuffer(),
  [1200, 650],
  '品牌比较画板PNG',
)
// Four brand arrangements. Text is live system text; no font binary is embedded.
for (const variant of ['horizontal', 'vertical', 'mono', 'reverse']) {
  const vertical = variant === 'vertical',
    reverse = variant === 'reverse'
  const w = vertical ? 180 : 300,
    h = vertical ? 190 : 96
  const color = reverse ? c.paper : variant === 'mono' ? c.ink : c.deep
  const body = `${reverse ? `<rect width="${w}" height="${h}" rx="12" fill="${c.deep}"/>` : ''}<g transform="${vertical ? 'translate(42 0)' : 'translate(2 0)'}">${mark(color, reverse || variant === 'mono' ? color : c.apricot)}</g><text x="${vertical ? 90 : 110}" y="${vertical ? 133 : 48}" text-anchor="${vertical ? 'middle' : 'start'}" font-family="Microsoft YaHei, sans-serif" font-size="${vertical ? 25 : 28}" font-weight="600" letter-spacing="2" fill="${color}">心域智链</text><text x="${vertical ? 90 : 111}" y="${vertical ? 160 : 73}" text-anchor="${vertical ? 'middle' : 'start'}" font-family="Microsoft YaHei,sans-serif" font-size="${vertical ? 11 : 12}" letter-spacing="1" fill="${color}">让每一份心事，有处安放</text>`
  await save(
    `brand/brand-logo-${variant}.svg`,
    svg(w, h, body, `心域智链${variant}标志`),
    [w, h],
    '品牌标志 / 文档 / PPT',
  )
}
const logoSvg = await fs.readFile(path.join(assetRoot, 'brand/brand-logo-vertical.svg'))
for (const size of [512, 1024])
  await save(
    `brand/brand-logo-vertical-${size}.png`,
    await sharp(logoSvg)
      .resize(size, size, { fit: 'contain', background: { r: 255, g: 255, b: 255, alpha: 0 } })
      .png()
      .toBuffer(),
    [size, size],
    '竖版品牌位图导出',
  )
for (const [name, body] of [
  ['color', mark()],
  ['mono', mark(c.deep, c.deep)],
  ['reverse', mark(c.paper, c.paper)],
]) {
  await save(
    `brand/brand-mark-${name}.svg`,
    svg(96, 96, body, `相伴标记 ${name}`),
    [96, 96],
    `推荐标志独立符号 ${name}；反白版本需置于品牌深色底`,
  )
}
for (const size of [16, 24, 32]) {
  const body = `<g transform="scale(${size / 96})">${mark(c.deep, c.apricot, true)}</g>`
  await save(
    `brand/brand-mark-small-${size}.svg`,
    svg(size, size, body, `相伴标记 ${size}px光学校正`),
    [size, size],
    `${size}px光学校正：去掉纸页高光并加宽中缝；建议按原生尺寸展示`,
  )
  await save(
    `brand/brand-mark-small-${size}.png`,
    await sharp(Buffer.from(svg(size, size, body)))
      .png()
      .toBuffer(),
    [size, size],
    `${size}px光学校正PNG`,
  )
}
const favicon = svg(
  96,
  96,
  `<rect width="96" height="96" rx="22" fill="${c.pale}"/>${mark(c.deep, c.apricot, true)}`,
  '心域智链应用图标：同页同行',
)
await save('brand/brand-favicon-source.svg', favicon, [96, 96], '应用图标矢量源')
for (const size of [16, 24, 32, 180, 512])
  await save(
    `brand/brand-favicon-${size}.png`,
    await sharp(Buffer.from(favicon)).resize(size, size).png().toBuffer(),
    [size, size],
    'favicon / 应用图标；小尺寸简化曲线',
  )

// A small editorial scene, grounded by one quiet baseline. Fine curves echo the folios.
const common = `<path d="M45 154H275" fill="none" stroke="${c.line}" stroke-width="1.5" stroke-linecap="round"/>`
const illus = {
  'empty-report': `<path d="M66 151V74C66 44 88 28 116 28H204C231 28 254 45 254 74V151" fill="${c.sageSoft}"/><path d="M83 153C84 124 78 115 65 105C61 125 67 140 83 144M83 132C92 114 100 108 112 107C112 122 103 131 83 135" fill="${c.sage}"/><path d="M120 46L209 54L201 145L112 137Z" fill="${c.apricotSoft}" stroke="${c.apricot}" stroke-width="1.8"/><path d="M104 54C124 49 144 52 158 62C173 53 194 52 216 59V145C194 138 176 141 158 149C140 139 124 137 104 142Z" fill="${c.paper}" stroke="${c.deep}" stroke-width="2.4" stroke-linejoin="round"/><path d="M158 63V148M116 76C127 73 139 76 147 80M116 91C128 89 137 92 147 96M170 78C180 74 192 74 204 77M170 93C181 89 192 90 201 92M116 109C127 107 135 109 143 112" fill="none" stroke="${c.brand}" stroke-width="2" stroke-linecap="round"/><path d="M181 57V93L189 87L197 92V56" fill="${c.apricot}"/><path d="M240 115V151M230 127C234 113 240 109 249 109C249 120 243 127 230 127" fill="${c.sage}" stroke="${c.sage}" stroke-width="2"/>`,
  'empty-list': `<path d="M63 153V62C63 43 77 31 97 31H220C242 31 256 46 256 66V153" fill="${c.pale}"/><path d="M81 75H122L134 87H235V141C235 147 231 151 225 151H90C84 151 81 147 81 141Z" fill="${c.deep}"/><path d="M105 48L186 38L198 129L117 140Z" fill="${c.apricotSoft}" stroke="${c.apricot}" stroke-width="1.6"/><path d="M134 45H213V136H134Z" fill="${c.paper}" stroke="${c.brand}" stroke-width="2"/><path d="M147 65H199M147 78H189M147 91H196" fill="none" stroke="${c.line}" stroke-width="2" stroke-linecap="round"/><path d="M82 105H235L225 151H91Z" fill="${c.sageSoft}" stroke="${c.deep}" stroke-width="2.3" stroke-linejoin="round"/><path d="M144 124H173" stroke="${c.sage}" stroke-width="4" stroke-linecap="round"/><path d="M246 153V125M245 137C236 132 232 126 232 119C242 120 247 126 245 137" fill="${c.sage}" stroke="${c.sage}" stroke-width="2"/>`,
  'not-found': `<path d="M72 150C96 126 109 109 96 91C79 69 111 52 141 47C173 42 199 53 213 32" fill="none" stroke="${c.apricotSoft}" stroke-width="22" stroke-linecap="round"/><path d="M72 150C96 126 109 109 96 91C79 69 111 52 141 47C173 42 199 53 213 32" fill="none" stroke="${c.apricot}" stroke-width="1.6" stroke-dasharray="4 6"/><path d="M182 78V153" stroke="${c.deep}" stroke-width="4" stroke-linecap="round"/><path d="M148 69H217L230 83L217 97H148Z" fill="${c.pale}" stroke="${c.deep}" stroke-width="2.4" stroke-linejoin="round"/><text x="183" y="89" text-anchor="middle" font-family="sans-serif" font-size="17" font-weight="600" fill="${c.deep}">404</text><path d="M245 152V124C245 113 251 104 260 99C263 114 259 126 245 133M245 141C235 134 231 126 231 117C241 122 247 131 245 141" fill="${c.sage}"/><path d="M126 149L139 128L151 149" fill="${c.sageSoft}" stroke="${c.sage}" stroke-width="1.5"/>`,
  'network-error': `<path d="M76 152V67C76 43 94 27 118 27H202C226 27 244 44 244 67V152" fill="${c.sageSoft}"/><path d="M111 114L99 85L145 70L132 112Z" fill="${c.paper}" stroke="${c.deep}" stroke-width="2.4" stroke-linejoin="round"/><path d="M99 85L132 88L145 70M132 88L111 114" fill="none" stroke="${c.deep}" stroke-width="1.7" stroke-linejoin="round"/><path d="M180 68L225 82L194 110L193 88Z" fill="${c.apricotSoft}" stroke="${c.brand}" stroke-width="2.4" stroke-linejoin="round"/><path d="M180 68L193 88L225 82" fill="none" stroke="${c.brand}" stroke-width="1.7"/><path d="M126 119C135 128 142 130 149 130M172 130C181 129 187 123 190 116" fill="none" stroke="${c.brand}" stroke-width="2.3" stroke-linecap="round"/><path d="M157 127L154 134M165 127L162 134" stroke="${c.apricot}" stroke-width="2" stroke-linecap="round"/><path d="M65 152V124M65 139C54 132 51 125 52 116C62 119 67 126 65 139" fill="${c.sage}" stroke="${c.sage}" stroke-width="2"/>`,
  'crisis-banner': `<path d="M66 153V73C66 41 87 23 119 23H201C233 23 254 42 254 73V153" fill="${c.apricotSoft}"/><path d="M161 24V46" stroke="${c.deep}" stroke-width="2.3"/><path d="M145 47C146 36 176 36 178 47L185 56H137Z" fill="${c.deep}"/><path d="M144 59L121 116H199L178 59" fill="${c.warm}"/><path d="M92 144L94 106C94 96 103 89 114 90L130 92C139 93 143 100 142 108L139 143" fill="${c.pale}" stroke="${c.deep}" stroke-width="2.2"/><path d="M90 126L142 131L140 143L89 138ZM91 140L87 153M137 143L141 153" fill="${c.deep}" stroke="${c.deep}" stroke-width="2.2" stroke-linecap="round"/><path d="M178 143L176 108C175 99 182 92 191 91L208 90C218 90 225 98 226 107L228 144" fill="${c.sageSoft}" stroke="${c.deep}" stroke-width="2.2"/><path d="M177 131L229 126L230 138L179 143ZM180 143L176 153M226 140L231 153" fill="${c.deep}" stroke="${c.deep}" stroke-width="2.2" stroke-linecap="round"/><path d="M151 141H169M160 142V153" stroke="${c.sage}" stroke-width="3" stroke-linecap="round"/><path d="M158 130H165L164 140H159Z" fill="${c.apricot}"/>`,
}
for (const [name, body] of Object.entries(illus))
  await save(
    `illustrations/illu-${name}-320.svg`,
    svg(
      320,
      180,
      common + body,
      {
        'empty-report': '暂无报告：完成测评后生成报告',
        'empty-list': '列表为空：尝试调整筛选',
        'not-found': '页面未找到：返回可用入口',
        'network-error': '网络连接中断：检查连接后重试',
        'crisis-banner': '你可以寻求支持：联系校内支持人员；紧急时联系当地紧急服务',
      }[name],
    ),
    [320, 180],
    `状态插画：${name}；行动说明须由页面可访问文字承载`,
  )

const moods = ['joy', 'sadness', 'neutral', 'fear', 'anxiety', 'anger']
function face(mood, index) {
  const mouth = {
    joy: 'M218 267Q256 303 294 267',
    sadness: 'M226 287Q256 261 286 287',
    neutral: 'M232 280H280',
    fear: 'M246 274Q256 264 266 274V295Q256 305 246 295Z',
    anxiety: 'M227 283Q242 270 256 283T285 283',
    anger: 'M229 286Q256 272 283 286',
  }[mood]
  const eyes =
    mood === 'joy' ? 'M207 236Q221 221 235 236M277 236Q291 221 305 236' : 'M216 234V246M296 234V246'
  const brows =
    mood === 'anger'
      ? '<path d="M204 213L236 225M276 225L308 213"/>'
      : mood === 'anxiety' || mood === 'fear'
        ? '<path d="M204 218L234 209M278 209L308 218"/>'
        : ''
  return `<g fill="none" stroke="${c.ink}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"><path d="${eyes}"/><path d="${mouth}"/>${brows}</g>${mood === 'anxiety' ? `<path d="M324 236Q345 260 329 264Q314 261 324 236" fill="${c.blue}"/>` : ''}${index === 1 ? `<path d="M190 224H242V255H190ZM270 224H322V255H270ZM242 236H270" fill="none" stroke="${c.deep}" stroke-width="6"/>` : ''}`
}
const avatars = [
  ...Array.from({ length: 3 }, (_, i) => ({
    group: 'teachers',
    name: `teacher-0${i + 1}`,
    mood: ['neutral', 'joy', 'neutral'][i],
    i,
  })),
  ...Array.from({ length: 4 }, (_, i) => ({
    group: 'students',
    name: `student-0${i + 1}`,
    mood: 'neutral',
    i: i + 3,
  })),
  ...moods.map((mood, i) => ({ group: 'emotions', name: `emotion-${mood}`, mood, i: i + 7 })),
]
for (const { group, name, mood, i } of avatars) {
  const background = [c.pale, c.sky, c.green, c.yellow][i % 4]
  const shirt = [c.deep, c.blue, t('success-text'), c.ink][i % 4]
  const hair =
    i % 3 === 0
      ? `<path d="M167 217V182Q170 99 256 107Q345 107 345 190V220L316 174Q252 212 193 172Z" fill="${c.ink}"/>`
      : i % 3 === 1
        ? `<path d="M164 225Q137 124 221 116Q304 77 344 172L349 224L323 185Q246 176 189 202Z" fill="${c.muted}"/>`
        : `<path d="M175 216Q158 122 256 119Q355 118 337 216L312 173Q262 192 201 171Z" fill="${c.ink}"/>`
  const body = `<rect width="512" height="512" rx="128" fill="${background}"/><circle cx="410" cy="105" r="18" fill="${c.paper}"/><path d="M93 512V439Q108 351 216 345H296Q404 351 419 439V512Z" fill="${shirt}"/><path d="M229 321V356Q256 380 283 356V321" fill="${c.paper}"/><ellipse cx="256" cy="234" rx="85" ry="109" fill="${c.paper}"/>${hair}${face(mood, i)}${group === 'teachers' ? `<path d="M216 365L256 407L296 365M256 407V512" fill="none" stroke="${background}" stroke-width="10"/><circle cx="312" cy="419" r="12" fill="${background}"/>` : `<path d="M190 375Q256 416 322 375" fill="none" stroke="${background}" stroke-width="12"/>`}<path d="M52 328Q67 303 82 328T112 328" fill="none" stroke="${shirt}" stroke-width="8" stroke-linecap="round"/>`
  const source = svg(
    512,
    512,
    body,
    `${group === 'teachers' ? '原创教师角色' : group === 'students' ? '原创中性学生角色' : `原创情绪表情 ${mood}`}，不指代真人`,
  )
  const base = `avatars/${group}/avatar-${name}`
  await save(`${base}-source.svg`, source, [512, 512], '原创几何头像矢量源；不指代真人')
  await save(
    `${base}-source-512.png`,
    await sharp(Buffer.from(source)).png().toBuffer(),
    [512, 512],
    '头像PNG源导出，制作工具复用',
  )
  for (const size of [48, 96, 256, 512])
    await save(
      `${base}-${size}.webp`,
      await sharp(Buffer.from(source)).resize(size, size).webp({ quality: 86 }).toBuffer(),
      [size, size],
      `原创头像 ${name}；建议展示不超过${size}px`,
    )
}
const icons = {
  assessment: 'M6 3H18V21H6ZM9 7H15M9 11H15M9 15H12',
  report: 'M5 3H15L19 7V21H5ZM14 3V8H19M8 17V13M12 17V10M16 17V12',
  treehole: 'M12 3C6 3 3 7 3 11C3 16 7 19 12 19H18L21 22V12C21 7 18 3 12 3ZM8 10H16M8 14H13',
  alert: 'M12 3L22 21H2ZM12 9V14M12 17V18',
  support:
    'M3 12L8 9L12 12L16 9L21 12M3 12V17L10 21L12 19L14 21L21 17V12M8 9L12 5L16 9M8 15L12 19L16 15',
  audit: 'M12 2L21 6V12C21 17 16 21 12 23C8 21 3 17 3 12V6ZM8 12L11 15L17 9',
  appointment: 'M4 5H20V21H4ZM8 2V8M16 2V8M4 10H20M8 14H10M14 14H16M8 18H10',
  knowledge:
    'M12 5C8 2 4 3 2 4V20C6 18 9 19 12 21C15 19 18 18 22 20V4C18 3 15 2 12 5ZM12 5V21M5 8L9 9M15 9L19 8',
}
const symbols = Object.entries(icons)
  .map(
    ([name, d]) =>
      `<symbol id="${name}" viewBox="0 0 24 24"><path d="${d}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>`,
  )
  .join('')
await save(
  'icons/icon-domain-sprite-24.svg',
  `<svg xmlns="http://www.w3.org/2000/svg" width="192" height="24" viewBox="0 0 192 24"><title>心域智链八个领域图标</title>${symbols}</svg>`,
  [192, 24],
  '领域symbol sprite；24×24 viewBox；currentColor继承；使用#assessment等符号id',
)
for (const name of ['login', 'dashboard']) {
  const dark = name === 'dashboard'
  const body = `<rect width="1440" height="900" fill="${dark ? c.ink : c.warm}"/><path d="M900 140C1040 140 1150 230 1150 392V794C1010 755 900 648 900 497Z" fill="${dark ? t('gray-700') : c.pale}"/><path d="M1204 794V392C1204 235 1310 147 1450 120V474C1450 632 1350 748 1204 794Z" fill="${dark ? c.deep : c.apricotSoft}"/><path d="M1012 276C1052 309 1080 361 1080 427M1270 432C1270 334 1327 264 1390 234" fill="none" stroke="${dark ? c.sage : c.paper}" stroke-width="2" stroke-linecap="round"/><path d="M916 818C1050 851 1267 851 1408 808" fill="none" stroke="${dark ? c.sage : c.sage}" stroke-width="2"/><g transform="translate(1142 70) scale(.8)">${mark(dark ? c.pale : c.deep, dark ? c.pale : c.apricot)}</g>`
  const source = svg(
    1440,
    900,
    body,
    dark ? '教师大屏背景：右侧同页同行，左侧信息留白' : '登录页背景：右侧舒展书页，左侧留给表单',
  )
  await save(
    `backgrounds/bg-${name}-1440.svg`,
    source,
    [1440, 900],
    `${name}背景；文字需单独渲染在空白/实色区域`,
  )
  await save(
    `backgrounds/bg-${name}-1440.webp`,
    await sharp(Buffer.from(source)).webp({ quality: 88 }).toBuffer(),
    [1440, 900],
    `${name}背景WebP`,
  )
}
// Source bytes are archived as text inputs; no network is required to rebuild.
const externalAssets = [
  [
    'phosphor-heart',
    'icons/phosphor/icon-phosphor-heart.svg',
    'Phosphor Icons',
    'MIT',
    '312dee73d1d969631d5498012f619ccf4edbdf31e1be3e65af4f4f1b3ac1b2dd',
  ],
  [
    'phosphor-hand-heart',
    'icons/phosphor/icon-phosphor-hand-heart.svg',
    'Phosphor Icons',
    'MIT',
    '8797f9ca2bc8620c56c9dead90c047724176a611d52e613c6412aa16745bf93e',
  ],
  [
    'phosphor-chat-circle-dots',
    'icons/phosphor/icon-phosphor-chat-circle-dots.svg',
    'Phosphor Icons',
    'MIT',
    '2af44e36757c90c999e070065ae61c495c66c8e88f43c5f07964dc3367cad60d',
  ],
  [
    'phosphor-book-open',
    'icons/phosphor/icon-phosphor-book-open.svg',
    'Phosphor Icons',
    'MIT',
    'b38cdb3a15dcf00cfa4811e318b021e25c6a87b47acbb11888e16d107a5642da',
  ],
  [
    'open-doodles-loving',
    'illustrations/open-doodles/illu-open-doodles-loving.svg',
    'Pablo Stanley',
    'CC0-1.0',
    'ec2530045eace13aa9d9f10ffc091cab561233ec57564f04f045e6ec53bbd62a',
  ],
  [
    'open-doodles-reading-side',
    'illustrations/open-doodles/illu-open-doodles-reading-side.svg',
    'Pablo Stanley',
    'CC0-1.0',
    'bc98d93429c03fe206050649841d0cecab51c928fcb6f7e842ff4af6a5585593',
  ],
]
const phosphorLicense = await fs.readFile(
  path.join(root, 'docs/design/ppt-kit/upstream/PHOSPHOR-LICENSE.txt'),
  'utf8',
)
for (const [key, output, author, license, sourceSha256] of externalAssets) {
  const input = `docs/design/ppt-kit/upstream/${key}.svg.txt`
  const raw = await fs.readFile(path.join(root, input))
  if (digestFor(input, raw) !== sourceSha256) throw new Error(`Upstream hash mismatch: ${input}`)
  const doodle = key.startsWith('open-doodles-')
  let adapted = raw.toString('utf8')
  if (doodle)
    adapted = adapted
      .replace(/-?\d+\.\d{3,}/g, (n) => String(Math.round(Number(n) * 100) / 100))
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/>\s+</g, '><')
      .replaceAll('#FF5678', c.apricot)
      .replaceAll('#000000', c.ink)
      .replace(/<\?xml[^>]*\?>\s*/, '')
  else
    adapted = adapted.replace(
      /(<svg\b[^>]*>)/,
      (_, opening) => `${opening}<!--\n${phosphorLicense}\n-->`,
    )
  await save(
    output,
    adapted,
    doodle ? [1024, 768] : [256, 256],
    doodle
      ? '第三方阅读 / 自我关怀插画；品牌色适配，独立场景使用，不作品牌标志'
      : '第三方通用线性图标；收藏 / 支持 / 交谈 / 阅读，保留上游路径',
  )
  Object.assign(entries.at(-1), {
    license,
    owner: author,
    sourceSha256,
    sourceInput: input,
    source: doodle
      ? `https://opendoodles.s3-us-west-1.amazonaws.com/${key.replace('open-doodles-', '')}.svg`
      : `https://raw.githubusercontent.com/phosphor-icons/core/2b75f3ad12b420c9504ef05df8d2564a28f8500e/assets/regular/${key.replace('phosphor-', '')}.svg`,
    sourceRevision: doodle
      ? 'official source URL; retrieved 2026-10-21; SHA-256 pinned'
      : '2b75f3ad12b420c9504ef05df8d2564a28f8500e',
    modifications: doodle
      ? '坐标精度两位小数；移除XML声明与标签间空白；粉色替换accent-apricot，黑色替换gray-800；保留角色姿态和主要轮廓'
      : '仅添加版权许可注释；矢量路径不变',
    notice: 'src/assets/LICENSES.md',
  })
}
// Original files are only read. They remain outside the approved kit.
for (const relative of [
  'avatars/psych-teacher-cartoon.svg',
  'avatars/psych-teacher-cartoon-48.png',
  'avatars/psych-teacher-cartoon-96.png',
  'avatars/psych-teacher-cartoon-192.png',
  ...[1, 2, 3].map((n) => `avatars/teachers/psych-teacher-${n}.png`),
]) {
  const data = await fs.readFile(path.join(assetRoot, relative))
  const meta = await sharp(data).metadata()
  entries.push({
    id: `legacy-${path.basename(relative).replace(/\./g, '-')}`,
    path: relative,
    type: path.extname(relative).slice(1),
    size: [meta.width, meta.height],
    usage: '既有引用保留，禁止新增使用；不纳入approved素材包',
    license: 'unverified',
    source: '仓库既有文件；原始来源与授权待核实',
    owner: '原作者待核实',
    status: 'legacy-unverified',
    sha256: digestFor(relative, data),
  })
}
await fs.writeFile(
  path.join(assetRoot, 'manifest.json'),
  JSON.stringify({ version: '2.0.0', updated: date, assets: entries }, null, 2) + '\n',
)
const licenses =
  `# 心域智链素材来源与许可\n\n> owner: B / R1 ｜ version: 2.0 ｜ status: 定稿 ｜ updated: ${date}\n\nLicenseRef-Project-Original 素材由本项目通过原创贝塞尔矢量代码制作，无第三方字体文件；作者为心域智链项目组：品牌与状态场景由 B / R1 制作；原W1几何头像与领域图标由 B / E03 原作，R1 按品牌色适配头像。日期 ${date}。该许可表示项目自制，允许项目内部复用；正式对外授权前由负责人确认权属，本文不冒充第三方法律授权证明。字标使用系统字体文字，不分发字体。旧七个头像来源与许可待核实，禁止新增使用，不包含在 approved 素材包；保留仅为兼容已有业务。\n\n下表逐项列出全部id与路径；所有导出与对应source SVG同属一个系列。第三方条目单独标注作者、上游来源与真实许可，不被视作项目原创。\n\n| 素材id | 文件（相对src/assets） | 来源 / 许可 | 可商用 |\n| --- | --- | --- | --- |\n` +
  entries
    .map(
      (e) =>
        `| ${e.id} | ${e.path} | ${e.status !== 'approved' ? '来源待核实 / unverified' : e.license === 'LicenseRef-Project-Original' ? '项目自制 / LicenseRef-Project-Original' : `${e.owner} / ${e.license}；[原始来源](${e.source})`} | ${e.status !== 'approved' ? '待核实，禁止新增使用' : e.license === 'LicenseRef-Project-Original' ? '仅内部复用；对外授权/商用由负责人确认' : e.license === 'MIT' ? 'MIT允许；随分发保留版权与许可全文' : 'CC0允许；其他不受许可影响的权利仍适用'} |`,
    )
    .join('\n') +
  '\n'
const thirdPartyNotices =
  '\n## 第三方许可全文与衍生记录\n\nPhosphor Icons：Copyright (c) 2023 Phosphor Icons；4个Regular图标仅添加完整MIT版权许可注释，矢量路径不变；单文件下载随附许可。固定commit、原始sourceSha256与更新后的成品sha256见manifest。\n\n```text\n' +
  (await fs.readFile(
    path.join(root, 'docs/design/ppt-kit/upstream/PHOSPHOR-LICENSE.txt'),
    'utf8',
  )) +
  '\n```\n\nOpen Doodles：Pablo Stanley，CC0 1.0 Universal；使用loving、reading-side。坐标精度保留两位小数，去掉XML声明、生成器注释与标签间空白；粉色映射accent-apricot，黑色映射gray-800。原始与优化后SHA均记录manifest。\n\n```text\n' +
  (await fs.readFile(
    path.join(root, 'docs/design/ppt-kit/upstream/CC0-1.0-legalcode.txt'),
    'utf8',
  )) +
  '\n```\n'
await fs.writeFile(path.join(assetRoot, 'LICENSES.md'), licenses + thirdPartyNotices)

const pptRoot = path.join(root, 'docs/design/ppt-kit')
await fs.mkdir(path.join(pptRoot, 'screenshot-frames'), { recursive: true })
const { PALETTE_TOKENS, EMOTION_FIELDS } = await import('../src/styles/echarts-theme.js')
const palette = {
  version: '2.0.0',
  updated: date,
  source: 'src/styles/tokens.css',
  order: [...PALETTE_TOKENS],
  colors: PALETTE_TOKENS.map((key) => t(key)),
  emotions: Object.fromEntries(EMOTION_FIELDS.map((key) => [key, t(`emo-${key}`)])),
  risks: Object.fromEntries(['low', 'mid', 'high'].map((key) => [key, t(`risk-${key}`)])),
  brand: Object.fromEntries(
    ['brand-500', 'brand-600', 'brand-100', 'accent-apricot', 'accent-sage', 'surface-warm'].map(
      (key) => [key, t(key)],
    ),
  ),
}
await fs.writeFile(
  path.join(pptRoot, 'chart-palette.json'),
  JSON.stringify(palette, null, 2) + '\n',
)
const cover = svg(
  1600,
  900,
  `<rect width="1600" height="900" fill="${c.warm}"/><path d="M1030 150C1160 150 1244 235 1244 379V781C1109 743 1030 650 1030 510Z" fill="${c.pale}"/><path d="M1296 781V379C1296 229 1393 154 1527 122V504C1527 641 1431 744 1296 781Z" fill="${c.apricotSoft}"/><path d="M1100 290C1147 329 1170 376 1170 440" fill="none" stroke="${c.paper}" stroke-width="3" stroke-linecap="round"/><g transform="translate(102 100) scale(1.2)">${mark()}</g><path d="M116 731H870" stroke="${c.line}" stroke-width="2"/>`,
  'PPT封面底板：左侧标题，右侧同页同行；文字另行编辑',
)
await fs.writeFile(path.join(pptRoot, 'cover-bg.svg'), cover)
await fs.writeFile(
  path.join(pptRoot, 'section-divider.svg'),
  svg(
    1600,
    900,
    `<rect width="1600" height="900" fill="${c.deep}"/><g transform="translate(800 46) scale(8)">${mark(c.brand, c.apricot)}</g><path d="M104 674H760" stroke="${c.pale}" stroke-width="2"/><g transform="translate(102 100)">${mark(c.paper, c.paper)}</g>`,
    'PPT章节底板：白色标题置于左侧，书页留白引向下一页',
  ),
)
await fs.writeFile(
  path.join(pptRoot, 'icon-sheet.svg'),
  svg(
    960,
    180,
    `<defs>${symbols}</defs>` +
      Object.keys(icons)
        .map(
          (name, i) =>
            `<g transform="translate(${28 + i * 118} 38)" color="${c.deep}"><use href="#${name}" width="48" height="48"/><text x="24" y="79" text-anchor="middle" font-size="12" fill="${c.ink}" font-family="sans-serif">${name}</text></g>`,
        )
        .join(''),
    'PPT领域图标参考，源码与sprite同源',
  ),
)
await fs.writeFile(
  path.join(pptRoot, 'screenshot-frames/screenshot-frame-16x9.svg'),
  svg(
    1600,
    900,
    `<rect x="1" y="1" width="1598" height="898" rx="16" fill="${c.paper}" stroke="${c.line}" stroke-width="2"/><path d="M0 56H1600" stroke="${c.line}" stroke-width="2"/><circle cx="28" cy="28" r="7" fill="${c.brand}"/><circle cx="52" cy="28" r="7" fill="${c.line}"/><circle cx="76" cy="28" r="7" fill="${c.line}"/><rect x="24" y="80" width="1552" height="796" rx="4" fill="${t('gray-50')}"/><text x="800" y="472" text-anchor="middle" font-family="Microsoft YaHei,sans-serif" font-size="24" fill="${c.muted}">替换为已脱敏或合成数据截图</text>`,
    'PPT截图框；内窗x24 y80 w1552 h796',
  ),
)
const approved = entries.filter((e) => e.status === 'approved')
console.log(
  JSON.stringify(
    {
      approved: approved.length,
      legacy: entries.length - approved.length,
      total: entries.length,
      generatedPptFiles: 5,
      maxBytes: Math.max(
        ...(await Promise.all(
          approved.map((e) => fs.stat(path.join(assetRoot, e.path)).then((s) => s.size)),
        )),
      ),
    },
    null,
    2,
  ),
)
