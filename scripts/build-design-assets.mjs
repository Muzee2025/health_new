import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const assetRoot = path.join(root, 'src/assets');
const require = createRequire(import.meta.url);
let sharp;
try {
  sharp = require(process.env.SHARP_MODULE_PATH || 'sharp');
} catch {
  for (const moduleRoot of (process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean)) {
    try { sharp = require(path.join(moduleRoot, 'sharp')); break; } catch { /* Try next configured module root. */ }
  }
}
if (!sharp) throw new Error('sharp is required. Set SHARP_MODULE_PATH to an existing sharp module, or NODE_PATH to its node_modules directory. No install is performed.');
const date = '2026-10-20';
const css = await fs.readFile(path.join(root, 'src/styles/tokens.css'), 'utf8');
const tokens = Object.fromEntries([...css.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)].map(m => [m[1], m[2].trim()]));
function t(key, seen = []) {
  if (!tokens[key] || seen.includes(key)) throw new Error(`Invalid token: ${key}`);
  return tokens[key].replace(/var\(--([\w-]+)\)/g, (_, name) => t(name, [...seen, key]));
}
const c = { brand: t('brand-500'), deep: t('brand-600'), pale: t('brand-100'), ink: t('gray-800'), paper: t('gray-0'), muted: t('gray-600'), line: t('gray-300'), blue: t('info'), sky: t('info-100'), yellow: t('warning-100'), green: t('success-100') };
const svg = (w, h, body, title = '心域智链项目自制素材') => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img"><title>${title}</title>${body}</svg>`;
const entries = [];
async function save(relative, contents, size, usage, status = 'approved') {
  const target = path.join(assetRoot, relative);
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, contents);
  const data = await fs.readFile(target);
  entries.push({ id: path.basename(relative).replace(/\./g, '-'), path: relative.replaceAll('\\', '/'), type: path.extname(relative).slice(1), size, usage, license: status === 'approved' ? 'LicenseRef-Project-Original' : 'unverified', source: status === 'approved' ? '项目自制：scripts/build-design-assets.mjs 几何矢量源' : '仓库既有文件；原始来源与授权待核实', owner: status === 'approved' ? '心域智链项目组（B / E03 制作）' : '原作者待核实', status, sha256: crypto.createHash('sha256').update(data).digest('hex') });
}
function mark(color = c.deep, backing = 'none') {
  return `<circle cx="48" cy="48" r="45" fill="${backing}"/><path d="M48 70C36 61 22 52 22 39C22 26 40 22 48 35C56 22 74 26 74 39C74 52 60 61 48 70Z" fill="none" stroke="${color}" stroke-width="7" stroke-linejoin="round"/><path d="M14 61Q48 91 82 61" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round"/><circle cx="14" cy="61" r="5" fill="${color}"/><circle cx="82" cy="61" r="5" fill="${color}"/>`;
}
// Four brand arrangements. Text is live system text; no font binary is embedded.
for (const variant of ['horizontal', 'vertical', 'mono', 'reverse']) {
  const vertical = variant === 'vertical', reverse = variant === 'reverse';
  const w = vertical ? 180 : 300, h = vertical ? 190 : 96;
  const color = reverse ? c.paper : variant === 'mono' ? c.ink : c.deep;
  const body = `${reverse ? `<rect width="${w}" height="${h}" rx="12" fill="${c.deep}"/>` : ''}<g transform="${vertical ? 'translate(42 0)' : 'translate(2 0)'}">${mark(color)}</g><text x="${vertical ? 90 : 110}" y="${vertical ? 137 : 49}" text-anchor="${vertical ? 'middle' : 'start'}" font-family="Microsoft YaHei, sans-serif" font-size="${vertical ? 25 : 28}" font-weight="600" fill="${color}">心域智链</text><text x="${vertical ? 90 : 111}" y="${vertical ? 161 : 72}" text-anchor="${vertical ? 'middle' : 'start'}" font-family="sans-serif" font-size="${vertical ? 12 : 13}" fill="${color}">连接 · 理解 · 支持</text>`;
  await save(`brand/brand-logo-${variant}.svg`, svg(w, h, body, `心域智链${variant}标志`), [w, h], '品牌标志 / 文档 / PPT');
}
const logoSvg = await fs.readFile(path.join(assetRoot, 'brand/brand-logo-vertical.svg'));
for (const size of [512, 1024]) await save(`brand/brand-logo-vertical-${size}.png`, await sharp(logoSvg).resize(size, size, { fit: 'contain', background: { r: 255, g: 255, b: 255, alpha: 0 } }).png().toBuffer(), [size, size], '竖版品牌位图导出');
const favicon = svg(96, 96, `<rect width="96" height="96" rx="22" fill="${c.pale}"/>${mark(c.deep)}`, '心域智链应用图标');
await save('brand/brand-favicon-source.svg', favicon, [96, 96], '应用图标矢量源');
for (const size of [16, 32, 180, 512]) await save(`brand/brand-favicon-${size}.png`, await sharp(Buffer.from(favicon)).resize(size, size).png().toBuffer(), [size, size], 'favicon / 应用图标');

const common = `<ellipse cx="160" cy="155" rx="112" ry="9" fill="${c.pale}"/>`;
const illus = {
  'empty-report': `<rect x="92" y="25" width="124" height="130" rx="12" fill="${c.sky}"/><path d="M116 59H190M116 80H176M116 101H153" stroke="${c.blue}" stroke-width="7" stroke-linecap="round"/><circle cx="218" cy="125" r="28" fill="${c.paper}" stroke="${c.deep}" stroke-width="5"/><path d="M207 125H229M218 114V136" stroke="${c.deep}" stroke-width="5"/>`,
  'empty-list': `<path d="M72 70L104 34H215L248 70V148H72Z" fill="${c.pale}"/><path d="M72 70H125L138 88H181L194 70H248" fill="none" stroke="${c.deep}" stroke-width="6" stroke-linejoin="round"/><circle cx="160" cy="46" r="19" fill="${c.paper}"/><path d="M151 46H169M160 37V55" stroke="${c.deep}" stroke-width="4"/>`,
  'not-found': `<path d="M66 131Q92 68 136 113T253 67" fill="none" stroke="${c.line}" stroke-width="7" stroke-dasharray="9 9"/><path d="M113 56L160 36L207 56V111L160 136L113 111Z" fill="${c.pale}" stroke="${c.deep}" stroke-width="4"/><text x="160" y="100" text-anchor="middle" font-size="36" font-family="sans-serif" font-weight="600" fill="${c.deep}">404</text><circle cx="66" cy="131" r="8" fill="${c.brand}"/>`,
  'network-error': `<path d="M77 69Q160 3 243 69M105 94Q160 49 215 94M132 120Q160 97 188 120" fill="none" stroke="${c.deep}" stroke-width="9" stroke-linecap="round"/><circle cx="160" cy="143" r="8" fill="${c.deep}"/><circle cx="237" cy="125" r="24" fill="${c.yellow}"/><path d="M237 111V128M237 135V138" stroke="${t('warning-text')}" stroke-width="5" stroke-linecap="round"/>`,
  'crisis-banner': `<path d="M60 137C70 95 113 95 137 119L160 139L183 119C207 95 250 95 260 137" fill="${c.pale}" stroke="${c.deep}" stroke-width="5" stroke-linecap="round"/><path d="M160 108C142 95 121 78 121 60C121 39 149 34 160 53C171 34 199 39 199 60C199 78 178 95 160 108Z" fill="${c.sky}" stroke="${c.blue}" stroke-width="5"/><circle cx="63" cy="72" r="10" fill="${c.brand}"/><circle cx="257" cy="72" r="10" fill="${c.brand}"/><path d="M74 76L105 88M246 76L215 88" stroke="${c.line}" stroke-width="4"/>`,
};
for (const [name, body] of Object.entries(illus)) await save(`illustrations/illu-${name}-320.svg`, svg(320, 180, common + body, { 'empty-report': '暂无报告：完成测评后生成报告', 'empty-list': '列表为空：尝试调整筛选', 'not-found': '页面未找到：返回可用入口', 'network-error': '网络连接中断：检查连接后重试', 'crisis-banner': '你可以寻求支持：联系校内支持人员；紧急时联系当地紧急服务' }[name]), [320, 180], `状态插画：${name}；行动说明须由页面可访问文字承载`);

const moods = ['joy', 'sadness', 'neutral', 'fear', 'anxiety', 'anger'];
function face(mood, index) {
  const mouth = { joy: 'M218 267Q256 303 294 267', sadness: 'M226 287Q256 261 286 287', neutral: 'M232 280H280', fear: 'M246 274Q256 264 266 274V295Q256 305 246 295Z', anxiety: 'M227 283Q242 270 256 283T285 283', anger: 'M229 286Q256 272 283 286' }[mood];
  const eyes = mood === 'joy' ? 'M207 236Q221 221 235 236M277 236Q291 221 305 236' : 'M216 234V246M296 234V246';
  const brows = mood === 'anger' ? '<path d="M204 213L236 225M276 225L308 213"/>' : mood === 'anxiety' || mood === 'fear' ? '<path d="M204 218L234 209M278 209L308 218"/>' : '';
  return `<g fill="none" stroke="${c.ink}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"><path d="${eyes}"/><path d="${mouth}"/>${brows}</g>${mood === 'anxiety' ? `<path d="M324 236Q345 260 329 264Q314 261 324 236" fill="${c.blue}"/>` : ''}${index === 1 ? `<path d="M190 224H242V255H190ZM270 224H322V255H270ZM242 236H270" fill="none" stroke="${c.deep}" stroke-width="6"/>` : ''}`;
}
const avatars = [ ...Array.from({ length: 3 }, (_, i) => ({ group: 'teachers', name: `teacher-0${i + 1}`, mood: ['neutral', 'joy', 'neutral'][i], i })), ...Array.from({ length: 4 }, (_, i) => ({ group: 'students', name: `student-0${i + 1}`, mood: 'neutral', i: i + 3 })), ...moods.map((mood, i) => ({ group: 'emotions', name: `emotion-${mood}`, mood, i: i + 7 })) ];
for (const { group, name, mood, i } of avatars) {
  const background = [c.pale, c.sky, c.green, c.yellow][i % 4];
  const shirt = [c.deep, c.blue, t('success-text'), c.ink][i % 4];
  const hair = i % 3 === 0 ? `<path d="M167 217V182Q170 99 256 107Q345 107 345 190V220L316 174Q252 212 193 172Z" fill="${c.ink}"/>` : i % 3 === 1 ? `<path d="M164 225Q137 124 221 116Q304 77 344 172L349 224L323 185Q246 176 189 202Z" fill="${c.muted}"/>` : `<path d="M175 216Q158 122 256 119Q355 118 337 216L312 173Q262 192 201 171Z" fill="${c.ink}"/>`;
  const body = `<rect width="512" height="512" rx="128" fill="${background}"/><circle cx="410" cy="105" r="18" fill="${c.paper}"/><path d="M93 512V439Q108 351 216 345H296Q404 351 419 439V512Z" fill="${shirt}"/><path d="M229 321V356Q256 380 283 356V321" fill="${c.paper}"/><ellipse cx="256" cy="234" rx="85" ry="109" fill="${c.paper}"/>${hair}${face(mood, i)}${group === 'teachers' ? `<path d="M216 365L256 407L296 365M256 407V512" fill="none" stroke="${background}" stroke-width="10"/><circle cx="312" cy="419" r="12" fill="${background}"/>` : `<path d="M190 375Q256 416 322 375" fill="none" stroke="${background}" stroke-width="12"/>`}<path d="M52 328Q67 303 82 328T112 328" fill="none" stroke="${shirt}" stroke-width="8" stroke-linecap="round"/>`;
  const source = svg(512, 512, body, `${group === 'teachers' ? '原创教师角色' : group === 'students' ? '原创中性学生角色' : `原创情绪表情 ${mood}`}，不指代真人`);
  const base = `avatars/${group}/avatar-${name}`;
  await save(`${base}-source.svg`, source, [512, 512], '原创几何头像矢量源；不指代真人');
  await save(`${base}-source-512.png`, await sharp(Buffer.from(source)).png().toBuffer(), [512, 512], '头像PNG源导出，制作工具复用');
  for (const size of [48, 96, 256, 512]) await save(`${base}-${size}.webp`, await sharp(Buffer.from(source)).resize(size, size).webp({ quality: 86 }).toBuffer(), [size, size], `原创头像 ${name}；建议展示不超过${size}px`);
}
const icons = {
  assessment: 'M6 3H18V21H6ZM9 7H15M9 11H15M9 15H12',
  report: 'M5 3H15L19 7V21H5ZM14 3V8H19M8 17V13M12 17V10M16 17V12',
  treehole: 'M12 3C6 3 3 7 3 11C3 16 7 19 12 19H18L21 22V12C21 7 18 3 12 3ZM8 10H16M8 14H13',
  alert: 'M12 3L22 21H2ZM12 9V14M12 17V18',
  support: 'M3 12L8 9L12 12L16 9L21 12M3 12V17L10 21L12 19L14 21L21 17V12M8 9L12 5L16 9M8 15L12 19L16 15',
  audit: 'M12 2L21 6V12C21 17 16 21 12 23C8 21 3 17 3 12V6ZM8 12L11 15L17 9',
  appointment: 'M4 5H20V21H4ZM8 2V8M16 2V8M4 10H20M8 14H10M14 14H16M8 18H10',
  knowledge: 'M12 5C8 2 4 3 2 4V20C6 18 9 19 12 21C15 19 18 18 22 20V4C18 3 15 2 12 5ZM12 5V21M5 8L9 9M15 9L19 8',
};
const symbols = Object.entries(icons).map(([name, d]) => `<symbol id="${name}" viewBox="0 0 24 24"><path d="${d}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></symbol>`).join('');
await save('icons/icon-domain-sprite-24.svg', `<svg xmlns="http://www.w3.org/2000/svg" width="192" height="24" viewBox="0 0 192 24"><title>心域智链八个领域图标</title>${symbols}</svg>`, [192, 24], '领域symbol sprite；24×24 viewBox；currentColor继承；使用#assessment等符号id');
for (const name of ['login', 'dashboard']) {
  const dark = name === 'dashboard';
  const body = `<rect width="1440" height="900" fill="${dark ? c.ink : c.paper}"/><path d="M720 900C720 620 1340 610 1340 260C1340 85 1130 0 1010 0" fill="none" stroke="${dark ? c.muted : c.pale}" stroke-width="100"/><path d="M980 900C820 630 1410 470 1190 120" fill="none" stroke="${dark ? c.brand : c.sky}" stroke-width="3"/><g fill="${dark ? c.pale : c.deep}"><circle cx="1190" cy="120" r="12"/><circle cx="1117" cy="665" r="18"/><circle cx="980" cy="849" r="10"/></g><g transform="translate(1050 270) scale(2.3)">${mark(dark ? c.pale : c.deep)}</g>`;
  const source = svg(1440, 900, body, dark ? '教师大屏背景：右侧支持节点' : '登录页背景：右侧围合支持路径，左侧留给表单');
  await save(`backgrounds/bg-${name}-1440.svg`, source, [1440, 900], `${name}背景；文字需单独渲染在空白/实色区域`);
  await save(`backgrounds/bg-${name}-1440.webp`, await sharp(Buffer.from(source)).webp({ quality: 88 }).toBuffer(), [1440, 900], `${name}背景WebP`);
}
// Original files are only read. They remain outside the approved kit.
for (const relative of ['avatars/psych-teacher-cartoon.svg', 'avatars/psych-teacher-cartoon-48.png', 'avatars/psych-teacher-cartoon-96.png', 'avatars/psych-teacher-cartoon-192.png', ...[1, 2, 3].map(n => `avatars/teachers/psych-teacher-${n}.png`)]) {
  const data = await fs.readFile(path.join(assetRoot, relative));
  const meta = await sharp(data).metadata();
  entries.push({ id: `legacy-${path.basename(relative).replace(/\./g, '-')}`, path: relative, type: path.extname(relative).slice(1), size: [meta.width, meta.height], usage: '既有引用保留，禁止新增使用；不纳入approved素材包', license: 'unverified', source: '仓库既有文件；原始来源与授权待核实', owner: '原作者待核实', status: 'legacy-unverified', sha256: crypto.createHash('sha256').update(data).digest('hex') });
}
await fs.writeFile(path.join(assetRoot, 'manifest.json'), JSON.stringify({ version: '1.0.0', updated: date, assets: entries }, null, 2) + '\n');
const licenses = `# 心域智链素材来源与许可\n\n> owner: B / E03 ｜ version: 1.0 ｜ status: 定稿 ｜ updated: ${date}\n\n新素材全部由本项目以几何矢量代码制作，无第三方照片、角色、字体文件或生成站点素材。作者为心域智链项目组（B / E03 制作）；日期均为 ${date}。LicenseRef-Project-Original 表示项目自制，允许项目内部复用；正式对外授权前由负责人确认权属，本文不冒充第三方法律授权证明。字标使用系统字体文字，不分发字体。旧七个头像来源与许可待核实，禁止新增使用，不包含在 approved 素材包；保留仅为兼容已有业务。\n\n下表逐项列出全部id与路径；来源、作者、日期由上述系列规则映射，legacy条目作者/日期/商业许可均待核实。所有导出与对应source SVG同属一个原创系列。\n\n| 素材id | 文件（相对src/assets） | 来源 / 许可 | 可商用 |\n| --- | --- | --- | --- |\n` + entries.map(e => `| ${e.id} | ${e.path} | ${e.status === 'approved' ? '项目自制 / LicenseRef-Project-Original' : '来源待核实 / unverified'} | ${e.status === 'approved' ? '仅内部复用；对外授权/商用由负责人确认' : '待核实，禁止新增使用'} |`).join('\n') + '\n';
await fs.writeFile(path.join(assetRoot, 'LICENSES.md'), licenses);

const pptRoot = path.join(root, 'docs/design/ppt-kit');
await fs.mkdir(path.join(pptRoot, 'screenshot-frames'), { recursive: true });
const { PALETTE_TOKENS, EMOTION_FIELDS } = await import('../src/styles/echarts-theme.js');
const palette = { version: '1.0.0', updated: date, source: 'src/styles/tokens.css', order: [...PALETTE_TOKENS], colors: PALETTE_TOKENS.map(key => t(key)), emotions: Object.fromEntries(EMOTION_FIELDS.map(key => [key, t(`emo-${key}`)])), risks: Object.fromEntries(['low', 'mid', 'high'].map(key => [key, t(`risk-${key}`)])) };
await fs.writeFile(path.join(pptRoot, 'chart-palette.json'), JSON.stringify(palette, null, 2) + '\n');
const cover = svg(1600, 900, `<rect width="1600" height="900" fill="${c.paper}"/><path d="M900 900Q1450 760 1380 320T1600 0" fill="none" stroke="${c.pale}" stroke-width="100"/><g transform="translate(1100 280) scale(3)">${mark(c.deep)}</g><path d="M104 204V700" stroke="${c.deep}" stroke-width="8"/>`, 'PPT封面底板：左侧留给标题，右侧支持符号');
await fs.writeFile(path.join(pptRoot, 'cover-bg.svg'), cover);
await fs.writeFile(path.join(pptRoot, 'section-divider.svg'), svg(1600, 900, `<rect width="1600" height="900" fill="${c.deep}"/><path d="M900 900Q1180 300 1600 250" fill="none" stroke="${c.brand}" stroke-width="120"/><g transform="translate(1220 570) scale(2.3)">${mark(c.paper)}</g><path d="M104 200H400" stroke="${c.paper}" stroke-width="5"/>`, 'PPT章节底板：白色标题置于左侧'));
await fs.writeFile(path.join(pptRoot, 'icon-sheet.svg'), svg(960, 180, `<defs>${symbols}</defs>` + Object.keys(icons).map((name, i) => `<g transform="translate(${28 + i * 118} 38)" color="${c.deep}"><use href="#${name}" width="48" height="48"/><text x="24" y="79" text-anchor="middle" font-size="12" fill="${c.ink}" font-family="sans-serif">${name}</text></g>`).join(''), 'PPT领域图标参考，源码与sprite同源'));
await fs.writeFile(path.join(pptRoot, 'screenshot-frames/screenshot-frame-16x9.svg'), svg(1600, 900, `<rect x="1" y="1" width="1598" height="898" rx="16" fill="${c.paper}" stroke="${c.line}" stroke-width="2"/><path d="M0 56H1600" stroke="${c.line}" stroke-width="2"/><circle cx="28" cy="28" r="7" fill="${c.brand}"/><circle cx="52" cy="28" r="7" fill="${c.line}"/><circle cx="76" cy="28" r="7" fill="${c.line}"/><rect x="24" y="80" width="1552" height="796" rx="4" fill="${t('gray-50')}"/><text x="800" y="472" text-anchor="middle" font-family="Microsoft YaHei,sans-serif" font-size="24" fill="${c.muted}">替换为已脱敏或合成数据截图</text>`, 'PPT截图框；内窗x24 y80 w1552 h796'));
const approved = entries.filter(e => e.status === 'approved');
console.log(JSON.stringify({ approved: approved.length, legacy: entries.length - approved.length, total: entries.length, generatedPptFiles: 5, maxBytes: Math.max(...await Promise.all(approved.map(e => fs.stat(path.join(assetRoot, e.path)).then(s => s.size)))) }, null, 2));
