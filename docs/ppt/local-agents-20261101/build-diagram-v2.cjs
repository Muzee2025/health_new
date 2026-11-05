/* V2: uniform typography, centered cards, plain final output label. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const sharp = require('sharp');

const dir = __dirname;
const root = path.resolve(dir, '../../..');
const tokens = fs.readFileSync(path.join(root, 'src/styles/tokens.css'), 'utf8');
const color = name => {
  const match = tokens.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`));
  if (!match) throw new Error(`Missing token: ${name}`);
  return match[1];
};
const c = { purple: color('brand-600'), pale: color('brand-50'), sage: color('accent-sage-soft'), white: color('gray-0'), text: color('gray-800'), border: color('gray-200') };
const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const svg = [];
const text = (x, y, value) => svg.push(`<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-family="Microsoft YaHei, sans-serif" font-size="28" font-weight="400" fill="${c.text}">${escape(value)}</text>`);
const rect = (x, y, width, height, fill, stroke = 'none') => svg.push(`<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="16" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/>`);
const line = (x1, y1, x2, y2, marker = '') => svg.push(`<path d="M${x1} ${y1}L${x2} ${y2}" fill="none" stroke="${c.purple}" stroke-width="2"${marker}/>`);
const arrow = ' marker-end="url(#arrow)"';
const both = `${arrow} marker-start="url(#arrow)"`;
svg.push(`<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" role="img" aria-labelledby="title desc">
<title id="title">本地多智能体协作，统一字体居中版</title>
<desc id="desc">立项拟建方案。三套本地候选模型支撑六类任务角色，复用语言模型并按需调度。六个格子的文字统一为微软雅黑28像素、常规字重、水平居中且整组垂直居中。底部仅显示输出结果。模型未经本轮部署或效果验证。</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="${c.purple}" stroke-width="1.5"/></marker></defs>`);
svg.push(`<rect x="0" y="0" width="1920" height="1080" fill="${c.white}"/>`);
text(960, 60, '本地多智能体协作（拟建）');
text(960, 106, 'Windows · 双RTX 4070（每卡12GB）');
text(275, 190, '授权文本 / 本人记录');
line(480, 190, 715, 190, arrow);
rect(740, 155, 440, 70, c.pale);
text(960, 190, '协调器');
text(1540, 190, '3套模型 · 6类专家任务');
line(960, 225, 960, 910, arrow);

const cards = [
  { x: 80, y: 270, lines: ['语义理解专家', 'Qwen3-8B · 4bit量化', '任务：提取事件、时间、否定和原文片段', '输出：结构化事实＋原文引用'] },
  { x: 1040, y: 270, lines: ['情绪线索专家', 'Qwen3-8B · 独立角色提示', '任务：整理压力、睡眠等自述表达', '输出：有依据的线索＋未知项'] },
  { x: 80, y: 470, lines: ['认知线索专家', 'Qwen3-8B · 独立角色提示', '任务：识别绝对化等候选表达模式', '输出：待核验假设＋对应原文'] },
  { x: 1040, y: 470, lines: ['纵向记录专家', 'Qwen3-Embedding-0.6B＋时间规则', '任务：召回本人授权记录并按时间归并', '输出：阶段记录时间线 / 资料不足'] },
  { x: 80, y: 670, lines: ['风险复核专家', 'Qwen3-8B＋待审规则', '任务：核对矛盾、缺失与紧急线索', '输出：待人工核查事项，不自动定级'] },
  { x: 1040, y: 670, lines: ['资源检索专家', 'Qwen3-Embedding-0.6B＋Qwen3-Reranker-0.6B', '任务：召回并重排已审核的支持资料', '输出：相关资料片段＋来源'] }
];
for (const card of cards) {
  svg.push(`<g data-role-card="true" data-x="${card.x}" data-y="${card.y}" data-width="800" data-height="170">`);
  rect(card.x, card.y, 800, 170, c.white, c.border);
  card.lines.forEach((value, i) => text(card.x + 400, card.y + 34 + i * 34, value));
  svg.push('</g>');
  if (card.x < 960) line(885, card.y + 85, 950, card.y + 85, both);
  else line(970, card.y + 85, 1035, card.y + 85, both);
}
svg.push('<g data-final-output="true">');
rect(660, 930, 600, 80, c.sage);
text(960, 970, '输出结果');
svg.push('</g></svg>');

async function main() {
  const svgPath = path.join(dir, 'local-agent-collaboration-v2.svg');
  const pngPath = path.join(dir, 'local-agent-collaboration-v2.png');
  const manifestPath = path.join(dir, 'manifest-v2.json');
  for (const file of [svgPath, pngPath, manifestPath]) {
    if (fs.existsSync(file) && !process.argv.includes('--replace-generated-v2')) throw new Error(`Refusing overwrite: ${file}`);
  }
  const content = svg.join('\n');
  fs.writeFileSync(svgPath, content, 'utf8');
  await sharp(Buffer.from(content)).resize(3840, 2160).png().toFile(pngPath);
  const original = JSON.parse(fs.readFileSync(path.join(dir, 'manifest.json'), 'utf8'));
  const manifest = {
    ...original, version: '2.0',
    purpose: '用户要求统一字体/字号/字重，六格文字居中，底部仅写输出结果；保留v1和原PPT',
    typography: { fontFamily: 'Microsoft YaHei, sans-serif', fontSizePx: 28, fontWeight: 400, textAnchor: 'middle' },
    finalOutputText: '输出结果',
    artifacts: [svgPath, pngPath].map(file => ({ path: path.relative(root, file).replaceAll('\\', '/'), bytes: fs.statSync(file).size, sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex') }))
  };
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify({status: manifest.status, version: manifest.version, typography: manifest.typography, artifacts: manifest.artifacts}, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
