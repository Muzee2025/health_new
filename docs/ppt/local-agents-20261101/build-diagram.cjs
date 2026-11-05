/* Original proposal graphic. Uses the project's registered design tokens. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const sharp = require('sharp');

const root = path.resolve(__dirname, '../../..');
const target = path.resolve(__dirname);
const tokenSource = fs.readFileSync(path.join(root, 'src/styles/tokens.css'), 'utf8');
const token = (name) => {
  const found = tokenSource.match(new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})\\s*;`));
  if (!found) throw new Error(`Missing project token: ${name}`);
  return found[1];
};
const colors = {
  purple: token('brand-600'), palePurple: token('brand-50'),
  sage: token('accent-sage-soft'), sageDark: token('gray-700'),
  white: token('gray-0'), text: token('gray-800')
};
colors.gray = token('gray-600');
colors.border = token('gray-200');
const esc = (value) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const parts = [];
const add = (s) => parts.push(s);
const text = (x, y, value, size = 26, fill = colors.text, weight = 400, anchor = 'start') =>
  add(`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}" text-anchor="${anchor}">${esc(value)}</text>`);
const rect = (x, y, w, h, fill, stroke = 'none', radius = 18) =>
  add(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/>`);
const line = (x1, y1, x2, y2, end = true, start = false) =>
  add(`<path d="M${x1},${y1} L${x2},${y2}" stroke="${colors.purple}" stroke-width="2.4" fill="none"${end ? ' marker-end="url(#arrow)"' : ''}${start ? ' marker-start="url(#back-arrow)"' : ''}/>`);

add(`<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" role="img" aria-labelledby="title desc">
<title id="title">本地多智能体协作：三套模型支撑六类专家任务</title>
<desc id="desc">立项候选方案。Windows服务器有两张RTX4070，按每卡12GB规划。Qwen3-8B量化语言模型分时支撑语义、情绪线索、认知线索与风险复核角色。Qwen3-Embedding-0.6B和Qwen3-Reranker-0.6B支撑纵向记录与资料检索。受控证据通过协调器汇总，交授权教师复核后形成摘要、引用、资料缺口和支持草稿。未部署或测得效果。</desc>
<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="${colors.purple}" stroke-width="1.6"/></marker>
<marker id="back-arrow" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M9 1L1 5L9 9" fill="none" stroke="${colors.purple}" stroke-width="1.6"/></marker>
</defs>
<g font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">`);
rect(0, 0, 1920, 1080, colors.white, 'none', 0);
text(80, 73, '本地多智能体协作', 50, colors.purple, 700);
text(80, 119, '三套模型支撑六类专家任务，每项输出都有依据可核对', 28, colors.gray);
rect(1570, 34, 270, 52, colors.palePurple, 'none', 26);
text(1705, 69, '立项方案 · 待验证', 25, colors.purple, 600, 'middle');

text(80, 197, '授权文本 / 本人记录', 28, colors.text, 600);
line(410, 188, 650, 188);
rect(675, 152, 570, 74, colors.palePurple);
text(960, 183, '协调器', 29, colors.purple, 700, 'middle');
text(960, 211, '权限校验 · 最小输入 · 按需调度', 23, colors.gray, 400, 'middle');
text(1325, 178, 'Windows · 2 × RTX 4070', 26, colors.text, 600);
text(1325, 214, '每卡12GB，按两块独立显卡规划', 23, colors.gray);

line(960, 226, 960, 844, false);
const cards = [
  { x: 80, y: 254, title: '01  语义理解专家', model: 'Qwen3-8B · 4bit量化', task: '提取事件、时间、否定和原文片段', output: '结构化事实＋原文引用' },
  { x: 1040, y: 254, title: '02  情绪线索专家', model: 'Qwen3-8B · 独立角色提示', task: '整理压力、睡眠等自述表达', output: '有依据的线索＋未知项' },
  { x: 80, y: 454, title: '03  认知线索专家', model: 'Qwen3-8B · 独立角色提示', task: '识别绝对化等候选表达模式', output: '待核验假设＋对应原文' },
  { x: 1040, y: 454, title: '04  纵向记录专家', model: 'Qwen3-Embedding-0.6B＋时间规则', task: '召回本人授权记录并按时间归并', output: '阶段记录时间线 / 资料不足' },
  { x: 80, y: 654, title: '05  风险复核专家', model: 'Qwen3-8B＋待审规则', task: '核对矛盾、缺失与紧急线索', output: '待人工核查事项，不自动定级' },
  { x: 1040, y: 654, title: '06  资源检索专家', model: 'Qwen3-Embedding-0.6B＋Qwen3-Reranker-0.6B', task: '召回并重排已审核的支持资料', output: '相关资料片段＋来源' }
];
for (const card of cards) {
  rect(card.x, card.y, 800, 170, colors.white, colors.border);
  text(card.x + 28, card.y + 38, card.title, 31, colors.purple, 700);
  text(card.x + 28, card.y + 73, card.model, 23, colors.gray);
  text(card.x + 28, card.y + 112, `任务：${card.task}`, 26);
  text(card.x + 28, card.y + 149, `输出：${card.output}`, 27, colors.text, 600);
  if (card.x < 960) line(884, card.y + 86, 950, card.y + 86, true, true);
  else line(970, card.y + 86, 1035, card.y + 86, true, true);
}
rect(921, 450, 78, 170, colors.palePurple, 'none', 20);
['受', '控', '证', '据'].forEach((s, i) => text(960, 486 + i * 34, s, 27, colors.purple, 600, 'middle'));

line(960, 825, 960, 850);
rect(80, 855, 1760, 62, colors.palePurple, 'none', 16);
text(960, 896, '协调器汇总：核对引用 · 保留分歧 · 标记资料缺口', 29, colors.purple, 600, 'middle');
line(960, 918, 960, 941);
rect(80, 948, 1760, 83, colors.sage, 'none', 18);
text(960, 981, '授权教师复核后输出', 28, colors.sageDark, 700, 'middle');
text(960, 1016, '事实摘要    原文证据    资料缺口    支持草稿', 29, colors.sageDark, 600, 'middle');
text(80, 1064, '“专家”指任务角色；共享语言模型分时调用。紧急线索优先交人工。部署、性能及专业有效性待实测。', 22, colors.gray);
add('</g></svg>');

async function main() {
  const svg = parts.join('\n');
  const svgPath = path.join(target, 'local-agent-collaboration-v1.svg');
  const pngPath = path.join(target, 'local-agent-collaboration-v1.png');
  for (const file of [svgPath, pngPath]) if (fs.existsSync(file)) throw new Error(`Refusing overwrite: ${file}`);
  fs.writeFileSync(svgPath, svg, 'utf8');
  await sharp(Buffer.from(svg)).resize(3840, 2160).png().toFile(pngPath);
  const manifest = {
    owner: 'A / Lead', version: '1.0', updated: '2026-11-01', status: 'candidate-user-review',
    purpose: '立项答辩模型与任务分工配图候选；未修改原PPT，未部署模型',
    method: 'Original deterministic SVG; rendered by sharp. No generative image provider.',
    license: 'LicenseRef-Project-Original',
    visualSource: 'src/styles/tokens.css', reference: 'User supplied six-box sketch, this chat, 2026-11-01',
    hardware: { os: 'Windows', gpu: 'RTX 4070', count: 2, vramPerGpuGiBPlanningAssumption: 12 },
    modelCandidates: [
      { id: 'Qwen/Qwen3-8B-GGUF', quantizationCandidate: 'Q4_K_M', url: 'https://huggingface.co/Qwen/Qwen3-8B-GGUF', status: 'proposed-not-tested' },
      { id: 'Qwen/Qwen3-Embedding-0.6B', url: 'https://huggingface.co/Qwen/Qwen3-Embedding-0.6B', status: 'proposed-not-tested' },
      { id: 'Qwen/Qwen3-Reranker-0.6B', url: 'https://huggingface.co/Qwen/Qwen3-Reranker-0.6B', status: 'proposed-not-tested' }
    ],
    artifacts: [svgPath, pngPath].map(file => ({ path: path.relative(root, file).replaceAll('\\', '/'), bytes: fs.statSync(file).size, sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex') }))
  };
  fs.writeFileSync(path.join(target, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify(manifest, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
