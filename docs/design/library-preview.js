import { readDesignToken, EMOTION_FIELDS } from '../../src/styles/echarts-theme.js';
import { initChartLibrary } from './chart-library.js';
import manifest from '../../src/assets/manifest.json';

const $ = selector => document.querySelector(selector);
const approved = manifest.assets.filter(asset => asset.status === 'approved');
const assetUrl = path => `/src/assets/${String(path).split('/').map(segment => encodeURIComponent(segment)).join('/')}`;
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char]));
const emotionNames = { joy:'喜悦', sadness:'悲伤', neutral:'平静', fear:'恐惧', anxiety:'焦虑', anger:'愤怒' };
const categoryNames = { all:'全部', brand:'品牌', illustrations:'插画', teachers:'教师', students:'学生', emotions:'情绪', icons:'图标', backgrounds:'背景', other:'其他' };
const iconIds = ['assessment','report','treehole','alert','support','audit','appointment','knowledge'];
const titles = { 'brand-logo-horizontal':'品牌横版标志', 'brand-logo-vertical':'品牌竖版标志', 'brand-logo-mono':'品牌单色标志', 'brand-logo-reverse':'品牌反白标志', 'brand-mark-color':'相伴品牌符号', 'brand-mark-mono':'相伴单色符号', 'brand-mark-reverse':'相伴反白符号', 'brand-mark-small':'小尺寸品牌符号', 'brand-favicon':'应用图标', 'brand-favicon-source':'应用图标矢量源', 'illu-empty-report':'暂无报告', 'illu-empty-list':'列表为空', 'illu-not-found':'页面未找到', 'illu-network-error':'网络连接中断', 'illu-crisis-banner':'寻求支持', 'icon-domain-sprite':'校园支持图标组', 'bg-login':'登录页面背景', 'bg-dashboard':'教师大屏背景', 'brand-concept-xiangban':'相伴 / 同页同行', 'brand-concept-yongguang':'拥光 / 温柔门廊', 'brand-concept-zhiyin':'知音 / 相向回应', 'brand-concepts-comparison':'三个品牌方向比较' };
Object.assign(titles, { 'illu-open-doodles-loving':'给自己一个拥抱', 'illu-open-doodles-reading-side':'安静阅读', 'icon-phosphor-heart':'心意 / 收藏', 'icon-phosphor-hand-heart':'托住一份心意', 'icon-phosphor-chat-circle-dots':'开启交谈', 'icon-phosphor-book-open':'阅读与了解' });
const concepts = [
  { id:'xiangban', name:'相伴', subtitle:'同页同行', description:'两片书页相向舒展，留出一条同行的路。', recommended:true },
  { id:'yongguang', name:'拥光', subtitle:'温柔门廊', description:'像一处可以停靠的门廊，稳稳接住一束光。' },
  { id:'zhiyin', name:'知音', subtitle:'相向回应', description:'彼此靠近的回应，让说出口的心情有回声。' },
];
function category(asset) {
  if (asset.path.startsWith('avatars/')) return asset.path.split('/')[1];
  const dir = asset.path.split('/')[0];
  return categoryNames[dir] ? dir : 'other';
}
function groupKey(asset) {
  const base = asset.path.replace(/\.[^.]+$/, '');
  return /-source(?:-\d+)?$/.test(base) ? base.replace(/-source(?:-\d+)?$/, '') : base.replace(/-\d+(?:x\d+)?$/, '');
}
function labelFor(key) {
  const base = key.split('/').pop();
  const mood = EMOTION_FIELDS.find(field => base.includes(`emotion-${field}`));
  if (mood) return `${emotionNames[mood]} / ${mood}`;
  if (/avatar-teacher-/.test(base)) return `教师角色 ${Number(base.match(/(\d+)$/)?.[1])}`;
  if (/avatar-student-/.test(base)) return `学生角色 ${Number(base.match(/(\d+)$/)?.[1])}`;
  if (/^brand-concept-.*-(mono|reverse)$/.test(base)) return `${titles[base.replace(/-(mono|reverse)$/, '')]} / ${base.endsWith('mono') ? '单色' : '反白'}`;
  return titles[base] || base.replace(/^(illu|icon|bg)-/, '').replaceAll('-', ' ');
}
const groups = Array.from(approved.reduce((map, asset) => {
  const key = groupKey(asset);
  if (!map.has(key)) map.set(key, { key, name:labelFor(key), category:category(asset), assets:[] });
  map.get(key).assets.push(asset);
  return map;
}, new Map()).values());
const categoryOrder = ['brand','illustrations','teachers','students','emotions','icons','backgrounds','other'];
groups.sort((a,b) => categoryOrder.indexOf(a.category) - categoryOrder.indexOf(b.category));
const state = { category:'all', query:'', format:'all', group:null, asset:null, opener:null, concept:'xiangban', variant:'horizontal' };
let toastTimer;
let copyRequest = 0;
let clipboardPending = false;
function toast(message, persistent = false) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  if (!persistent) toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3000);
}
function preferred(assets) {
  return assets.find(a => a.type === 'webp' && a.size[0] === 96) || assets.find(a => a.type === 'svg') || assets[0];
}
function previewMarkup(asset, name, lazy = true) {
  if (asset.path.includes('sprite')) return `<span class="sprite-preview" role="img" aria-label="测评、报告、树洞、预警、支持、审计、预约、知识库八个图标">${iconIds.map(id => `<svg aria-hidden="true" width="24" height="24"><use href="${escapeHtml(assetUrl(asset.path))}#${id}"></use></svg>`).join('')}</span>`;
  return `<img src="${escapeHtml(assetUrl(asset.path))}" width="${asset.size[0]}" height="${asset.size[1]}" alt="${escapeHtml(name)}" ${lazy ? 'loading="lazy"' : ''} decoding="async" />`;
}
function renderCategories() {
  $('#category-filters').innerHTML = Object.entries(categoryNames).filter(([key]) => key === 'all' || groups.some(g => g.category === key)).map(([key,name]) => `<button type="button" data-category="${key}" aria-pressed="${state.category === key}">${name}<span>${key === 'all' ? groups.length : groups.filter(g => g.category === key).length}</span></button>`).join('');
}
function renderLibrary() {
  const query = state.query.trim().toLocaleLowerCase();
  const visible = groups.filter(group => (state.category === 'all' || group.category === state.category) && (state.format === 'all' || group.assets.some(a => a.type === state.format)) && `${group.name} ${categoryNames[group.category]} ${group.key} ${group.assets.map(a => `${a.id} ${a.usage}`).join(' ')}`.toLocaleLowerCase().includes(query));
  $('#results-count').textContent = `找到 ${visible.length} 组素材${state.format !== 'all' ? ` / ${state.format.toUpperCase()}` : ''}`;
  $('#library-total').textContent = `${groups.length} 组可选素材`;
  $('#clear-filters').hidden = !state.query && state.category === 'all' && state.format === 'all';
  $('#empty-results').hidden = visible.length > 0;
  $('#asset-grid').innerHTML = visible.map(group => {
    const choices = state.format === 'all' ? group.assets : group.assets.filter(a => a.type === state.format);
    const asset = preferred(choices);
    return `<button class="asset-card" type="button" data-key="${escapeHtml(group.key)}" aria-label="查看${escapeHtml(group.name)}的详情与下载"><span class="asset-art ${['teachers','students','emotions'].includes(group.category) ? 'avatar' : ''} ${asset.path.includes('reverse') ? 'reverse' : ''}">${previewMarkup(asset,group.name)}</span><span class="asset-name">${escapeHtml(group.name)}<span class="asset-open" aria-hidden="true">↗</span></span><span class="asset-caption">${[...new Set(choices.map(a => a.type.toUpperCase()))].join(' / ')}${choices.length > 1 ? ` · ${choices.length} 个规格` : ` · ${asset.size.join(' × ')}`}</span></button>`;
  }).join('');
  renderCategories();
}
function resetFilters() {
  Object.assign(state, { query:'', category:'all', format:'all' });
  $('#asset-search').value = '';
  $('#format-filter').value = 'all';
  renderLibrary();
  $('#asset-search').focus();
}
$('#category-filters').addEventListener('click', event => {
  const button = event.target.closest('[data-category]');
  if (!button) return;
  state.category = button.dataset.category;
  renderLibrary();
  $(`[data-category="${state.category}"]`).focus();
});
$('#asset-search').addEventListener('input', event => { state.query = event.target.value; renderLibrary(); });
$('#format-filter').addEventListener('change', event => { state.format = event.target.value; renderLibrary(); });
$('#clear-filters').addEventListener('click', resetFilters);
$('#empty-reset').addEventListener('click', resetFilters);
$('#asset-grid').addEventListener('click', event => {
  const button = event.target.closest('[data-key]');
  if (button) openDetail(groups.find(group => group.key === button.dataset.key), button);
});
const dialog = $('#asset-dialog');
function sizeOptions(format, selectAssetId) {
  const options = state.group.assets.filter(asset => asset.type === format).sort((a,b) => a.size[0] - b.size[0]);
  $('#detail-size').innerHTML = options.map(asset => `<option value="${escapeHtml(asset.id)}">${asset.size.join(' × ')} px${asset.type === 'svg' ? ' · 可缩放' : ''}</option>`).join('');
  if (options.some(a => a.id === selectAssetId)) $('#detail-size').value = selectAssetId;
  updateDetail();
}
function openDetail(group, opener) {
  state.group = group;
  state.opener = opener;
  const first = preferred(state.format === 'all' ? group.assets : group.assets.filter(a => a.type === state.format));
  $('#detail-title').textContent = group.name;
  $('#detail-category').textContent = categoryNames[group.category];
  $('#detail-usage').textContent = first.usage;
  $('#detail-format').innerHTML = [...new Set(group.assets.map(a => a.type))].map(type => `<option value="${type}">${type.toUpperCase()}${type === 'svg' ? ' · 矢量源' : ''}</option>`).join('');
  $('#detail-format').value = first.type;
  sizeOptions(first.type,first.id);
  dialog.showModal();
  $('#dialog-close').focus();
}
function updateDetail() {
  const asset = state.group.assets.find(a => a.id === $('#detail-size').value);
  if (!asset) return;
  state.asset = asset;
  copyRequest += 1;
  $('#copy-path').disabled = clipboardPending;
  $('#detail-preview').classList.toggle('reverse', asset.path.includes('reverse'));
  $('#detail-preview').innerHTML = previewMarkup(asset,state.group.name,false);
  $('#detail-file').textContent = `${asset.type.toUpperCase()} / ${asset.size.join(' × ')} px`;
  $('#download-asset').href = assetUrl(asset.path);
  $('#download-asset').download = asset.path.split('/').pop();
  $('#download-asset').textContent = `下载 ${asset.type.toUpperCase()}`;
  $('#detail-feedback').textContent = clipboardPending ? '正在等待浏览器剪贴板许可，请先完成当前复制请求。' : '';
  $('#copy-fallback').hidden = true;
  $('#detail-license').textContent = asset.license === 'LicenseRef-Project-Original' ? '项目自制 · 可在项目内部复用。对外授权及商业使用需负责人确认。' : `外部开源素材 · ${asset.license}。使用前请阅读来源与许可记录，保留要求的许可声明。`;
  $('#detail-meta').innerHTML = [['文件编号',asset.id],['项目路径',`src/assets/${asset.path}`],['用途',asset.usage],['来源',asset.source],['许可',asset.license],['制作/登记',asset.owner],['SHA-256',asset.sha256]].map(([key,value]) => `<dt>${key}</dt><dd>${escapeHtml(value)}</dd>`).join('');
}
$('#detail-format').addEventListener('change', event => sizeOptions(event.target.value));
$('#detail-size').addEventListener('change', updateDetail);
$('#dialog-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
dialog.addEventListener('close', () => { copyRequest += 1; $('#copy-path').disabled = clipboardPending; state.opener?.focus(); });
function setClipboardPending(pending) {
  clipboardPending = pending;
  if (pending) toast('正在等待浏览器剪贴板许可，请先完成当前复制请求。',true);
  else $('#toast').classList.remove('visible');
  document.querySelectorAll('#copy-path, [data-token]').forEach(button => {
    button.disabled = pending;
    button.setAttribute('aria-busy',String(pending));
    if (pending) button.title = '正在等待浏览器剪贴板许可';
    else button.removeAttribute('title');
  });
}
async function copyText(text, onWaiting) {
  if (clipboardPending) return 'busy';
  // Try the synchronous user-gesture copy first. Never race an uncancellable write.
  const input = document.createElement('textarea');
  const previousFocus = document.activeElement;
  input.value = text;
  input.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0';
  (dialog.open ? dialog : document.body).append(input);
  input.select();
  let success = false;
  try { success = document.execCommand('copy'); } catch { success = false; }
  input.remove();
  previousFocus?.focus();
  if (success) return 'copied';
  if (!navigator.clipboard?.writeText) return 'failed';
  setClipboardPending(true);
  onWaiting?.();
  try {
    await navigator.clipboard.writeText(text);
    return 'copied';
  } catch {
    return 'failed';
  } finally {
    setClipboardPending(false);
  }
}
$('#copy-path').addEventListener('click', async () => {
  const path = `src/assets/${state.asset.path}`;
  const request = ++copyRequest;
  $('#copy-path').disabled = true;
  $('#detail-feedback').textContent = '正在复制…';
  const copied = await copyText(path, () => { $('#detail-feedback').textContent = '正在等待浏览器剪贴板许可，请在浏览器提示中选择。'; });
  if (request !== copyRequest || !dialog.open) return;
  if (copied === 'copied') {
    $('#detail-feedback').textContent = '已复制项目引用路径';
  } else if (copied === 'busy') {
    $('#detail-feedback').textContent = '正在等待浏览器剪贴板许可，请先完成当前复制请求。';
    return;
  } else {
    $('#detail-feedback').textContent = '浏览器未允许自动复制。请手动复制下方路径。';
    $('#copy-fallback').hidden = false;
    $('#fallback-path').value = path;
    $('#fallback-path').focus();
    $('#fallback-path').select();
  }
  $('#copy-path').disabled = false;
  if ($('#copy-fallback').hidden) $('#copy-path').focus();
});
$('#download-asset').addEventListener('click', () => { $('#detail-feedback').textContent = `已请求下载 ${state.asset.path.split('/').pop()}；请查看浏览器下载列表。`; });

function renderConcepts() {
  $('#concepts').innerHTML = concepts.map(concept => { const asset = approved.find(a => a.path === `brand/concepts/brand-concept-${concept.id}.svg`); return `<button type="button" class="concept" data-concept="${concept.id}" aria-pressed="${state.concept === concept.id}"><span class="concept-art"><img src="${assetUrl(`brand/concepts/brand-concept-${concept.id}.svg`)}" width="${asset?.size[0] || 96}" height="${asset?.size[1] || 96}" alt="${concept.name}概念标志" loading="lazy" /></span><span class="concept-info"><span class="concept-title">${concept.name}<span class="concept-state">${state.concept === concept.id ? '预览中' : concept.recommended ? '推荐' : '查看'}</span></span><span class="concept-description">${concept.subtitle}。${concept.description}</span></span></button>`; }).join('');
}
function renderBrand() {
  const concept = concepts.find(c => c.id === state.concept);
  const preview = $('#logo-preview');
  const variantPath = `brand/concepts/brand-concept-${state.concept}-${state.variant}.svg`;
  const customVariant = approved.find(a => a.path === variantPath);
  const path = state.concept === 'xiangban' ? `brand/brand-logo-${state.variant}.svg` : customVariant?.path || `brand/concepts/brand-concept-${state.concept}.svg`;
  const asset = approved.find(a => a.path === path);
  preview.src = assetUrl(path);
  preview.width = asset?.size[0] || 96;
  preview.height = asset?.size[1] || 96;
  preview.alt = `${concept.name}${{horizontal:'标准',mono:'单色',reverse:'反白'}[state.variant]}标志预览`;
  $('#logo-stage').className = `logo-stage ${state.variant}`;
  $('#brand-lab-title').textContent = `${concept.name} / 标志应用预览`;
  $('#brand-concept-description').textContent = concept.description;
  document.querySelectorAll('[data-variant]').forEach(button => {
    const available = state.concept === 'xiangban' || button.dataset.variant === 'horizontal' || approved.some(a => a.path === `brand/concepts/brand-concept-${state.concept}-${button.dataset.variant}.svg`);
    button.disabled = !available;
    button.setAttribute('aria-pressed',String(button.dataset.variant === state.variant));
  });
  renderConcepts();
}
$('#concepts').addEventListener('click', event => { const button = event.target.closest('[data-concept]'); if (!button) return; state.concept = button.dataset.concept; state.variant = 'horizontal'; renderBrand(); $(`[data-concept="${state.concept}"]`).focus(); });
$('#brand-variants').addEventListener('click', event => { const button = event.target.closest('[data-variant]'); if (button) { state.variant = button.dataset.variant; renderBrand(); } });
$('#logo-scale').addEventListener('input', event => { $('#logo-preview').style.width = `${event.target.value}px`; $('#logo-scale-value').value = `${event.target.value} px`; });
const swatches = [['brand-500','相伴紫','品牌识别'],['brand-600','深相伴紫','交互与重点'],['brand-100','轻柔紫','安静的衬底'],['accent-apricot','杏光','温暖的点缀'],['accent-sage','鼠尾草','陪伴的辅助色'],['gray-800','苔墨','正文与标题']];
function tokenHex(token) {
  let value = getComputedStyle(document.documentElement).getPropertyValue(`--${token}`).trim() || readDesignToken('brand-500');
  while (value.startsWith('var(')) value = readDesignToken(value.slice(6,-1));
  return value;
}
function renderPalette() {
  $('#palette').innerHTML = swatches.map(([token,label,description]) => { const hex = tokenHex(token); return `<button type="button" data-token="${token}" aria-label="复制${label}色值${hex}"><span class="swatch-color" style="background:var(--${token})"></span><span class="swatch-name">${label}</span><span class="swatch-value">${hex}</span><span class="swatch-value">${description}</span></button>`; }).join('');
}
$('#palette').addEventListener('click', async event => { const button = event.target.closest('[data-token]'); if (!button) return; const hex = tokenHex(button.dataset.token); const result = await copyText(hex); if (result === 'copied') toast(`已复制色值 ${hex}`); else if (result === 'busy') toast('请先完成当前浏览器剪贴板许可请求。',true); else toast(`自动复制不可用，色值为 ${hex}，请手动复制`); });
document.querySelectorAll('[data-find]').forEach(button => button.addEventListener('click', () => {
  const query = button.dataset.find;
  const exact = groups.find(g => g.key.includes(query));
  if (query === 'empty-report' && exact) return openDetail(exact,button);
  resetFilters(); state.category = query; renderLibrary(); $('#library').scrollIntoView({ behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); $(`[data-category="${query}"]`).focus({ preventScroll:true });
}));
const teacher = approved.find(a => a.path.includes('avatars/teachers/') && a.type === 'webp' && a.size[0] === 96);
if (teacher) document.querySelectorAll('[data-teacher-avatar]').forEach(img => { img.src = assetUrl(teacher.path); });
$('#small-mark-previews').innerHTML = [16,24,32].map(size => {
  const asset = approved.find(a => a.path === `brand/brand-mark-small-${size}.svg`);
  return asset ? `<figure><span><img src="${escapeHtml(assetUrl(asset.path))}" width="${size}" height="${size}" alt="相伴${size}像素专用符号" loading="lazy" /></span><figcaption>${size} px</figcaption></figure>` : '';
}).join('');
const observer = new IntersectionObserver(entries => {
  const current = entries.filter(e => e.isIntersecting).sort((a,b) => b.intersectionRatio-a.intersectionRatio)[0];
  if (!current) return;
  document.querySelectorAll('.rail nav a').forEach(a => { const active = a.hash === `#${current.target.id}`; a.classList.toggle('active',active); if (active) a.setAttribute('aria-current','location'); else a.removeAttribute('aria-current'); });
}, { rootMargin:'-8% 0px -55% 0px', threshold:[0,.1,.3] });
document.querySelectorAll('main > section[id]').forEach(section => observer.observe(section));

window.addEventListener('pagehide', event => { if (!event.persisted) observer.disconnect(); });
renderLibrary(); renderBrand(); renderPalette(); initChartLibrary();
