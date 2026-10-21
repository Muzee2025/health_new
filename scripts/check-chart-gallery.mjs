import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { getChartDemoData } from '../docs/design/chart-demo-data.js';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const sharp = require(process.env.SHARP_MODULE_PATH || 'sharp');
const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.resolve(root, process.env.CHART_QA_OUTPUT || 'tmp/chart-gallery-qa');
const origin = new URL(process.env.BASELINE_BASE_URL || 'http://127.0.0.1:5173').origin;
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(origin).hostname), 'Use a local preview server');
const preview = `${origin}/docs/design/library-preview.html`;
const ids = ['trend', 'emotion', 'risk', 'appointment', 'channel', 'heatmap', 'histogram', 'scatter'];
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const sum = values => values.reduce((total, value) => total + value, 0);
const report = { task: 'Chart browser QA', checkedAt: new Date().toISOString(), baseCommit: process.env.CHART_QA_BASE_COMMIT || '612f8cf', environment: { baseUrl: preview, browserAvailability: 'absent', reason: 'Browser plugin not available', viewports: [[1440, 1000], [390, 844], [320, 844]] }, tests: [], errors: [], warnings: [], blockedRequests: [], downloads: [], screenshots: [] };
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, ...(process.env.BASELINE_EXECUTABLE_PATH ? { executablePath: process.env.BASELINE_EXECUTABLE_PATH } : { channel: process.env.BASELINE_BROWSER_CHANNEL || 'msedge' }) });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block', reducedMotion: 'reduce', acceptDownloads: true });
await context.route('**/*', route => {
  const url = new URL(route.request().url());
  if (url.origin === origin && !url.pathname.startsWith('/api/')) return route.continue();
  report.blockedRequests.push(url.origin + url.pathname);
  return route.abort();
});
const page = await context.newPage();
page.setDefaultTimeout(8000);
page.on('pageerror', error => report.errors.push(String(error)));
page.on('console', message => {
  if (message.type() === 'error') report.errors.push(message.text());
  if (message.type() === 'warning') report.warnings.push(message.text());
});
const pass = (name, evidence = {}) => report.tests.push({ name, passed: true, ...evidence });
async function shot(name, target = page) {
  const bytes = await sharp(await target.screenshot({ type: 'png' })).webp({ quality: 90 }).toBuffer();
  await fs.writeFile(path.join(output, name), bytes);
  report.screenshots.push({ file: name, bytes: bytes.length, sha256: sha(bytes) });
}
async function options() {
  return page.evaluate(async ids => {
    const url = performance.getEntriesByType('resource').map(item => item.name).find(name => name.includes('/echarts.js?'));
    const echarts = await import(url);
    return ids.map(id => {
      const chart = echarts.getInstanceByDom(document.getElementById(`chart-${id}`));
      const option = chart.getOption();
      return { id, renderer: chart.getZr().painter.getType(), animation: option.animation, xAxis: option.xAxis, yAxis: option.yAxis, series: option.series.map(series => ({ type: series.type, data: series.data })) };
    });
  }, ids);
}
let stage = 'initial load';
try {
  await page.goto(`${preview}?qa=keep#charts`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelectorAll('[data-chart-id] [data-rendered=true] svg').length === 8);
  assert.equal(await page.title(), '心域智链 · 素材工作台');
  assert.equal(await page.locator('vite-error-overlay').count(), 0);
  assert.ok((await page.locator('#charts-title').innerText()).trim().length > 0);
  pass('page identity, meaningful content and no framework overlay', { title: await page.title(), pathname: new URL(page.url()).pathname });
  assert.equal(await page.locator('[data-chart-id]:visible').count(), 8);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 1440);
  const initial = await options();
  assert.ok(initial.every(item => item.renderer === 'svg' && item.animation === false));
  assert.equal(initial.find(item => item.id === 'trend').yAxis[0].min, 0);
  pass('eight SVG charts and reduced motion', { charts: initial.map(item => ({ id: item.id, renderer: item.renderer, types: item.series.map(series => series.type) })), trendZeroBaseline: true });
  await page.locator('#charts').scrollIntoViewIfNeeded();
  await shot('desktop.webp');
  await shot('gallery.webp', page.locator('#charts'));

  stage = 'filters and URL';
  const counts = { trend: 1, compare: 3, composition: 2, distribution: 1, relationship: 1, all: 8 };
  for (const [use, expected] of Object.entries(counts)) {
    const button = page.locator(`[data-chart-use="${use}"]`);
    await button.focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('[data-chart-id]:visible').count(), expected);
    assert.equal(await button.getAttribute('aria-pressed'), 'true');
  }
  await page.locator('#chart-range').selectOption('7');
  await page.locator('#chart-sample').selectOption('B');
  assert.match(page.url(), /qa=keep/);
  assert.match(page.url(), /chart-range=7/);
  assert.match(page.url(), /chart-sample=B/);
  assert.match(page.url(), /#charts$/);
  await page.reload({ waitUntil: 'networkidle' });
  assert.equal(await page.locator('#chart-range').inputValue(), '7');
  assert.equal(await page.locator('#chart-sample').inputValue(), 'B');
  await page.locator('#chart-range').selectOption('30');
  await page.goBack();
  await page.waitForFunction(() => document.querySelector('#chart-range').value === '7');
  await page.goForward();
  await page.waitForFunction(() => document.querySelector('#chart-range').value === '30');
  pass('keyboard filters and URL reload/back/forward', { counts, preservedOtherQueryAndHash: true });

  stage = 'tables and plotted values';
  await page.locator('#chart-range').selectOption('7');
  const data = getChartDemoData({ sample: 'B', range: 7 });
  const plotted = await options();
  assert.deepEqual(plotted.find(item => item.id === 'trend').series[0].data, data.daily.map(day => day.support));
  assert.deepEqual(plotted.find(item => item.id === 'emotion').series[0].data.map(item => item.value), data.emotions.map(item => item.value));
  assert.deepEqual(plotted.find(item => item.id === 'risk').series[0].data.map(item => item.value), data.risks.map(item => item.value));
  assert.deepEqual(plotted.find(item => item.id === 'appointment').series.map(item => item.data), [data.appointments.map(item => item.planned), data.appointments.map(item => item.completed)]);
  assert.deepEqual(plotted.find(item => item.id === 'channel').series.map(item => item.data), [0, 1, 2].map(index => data.channels.map(group => group.percentages[index])));
  assert.equal(sum(plotted.find(item => item.id === 'heatmap').series[0].data.map(item => item.value[2])), sum(data.appointments.map(item => item.planned)));
  assert.deepEqual(plotted.find(item => item.id === 'histogram').series[0].data, data.histogram.map(item => item.value));
  assert.deepEqual(plotted.find(item => item.id === 'scatter').series[0].data.map(item => item.value), data.resources.map(item => [item.views, item.saves]));
  const rows = {};
  for (const id of ids) {
    const details = page.locator(`#chart-data-${id}`);
    await details.locator(':scope > summary').focus();
    await page.keyboard.press('Enter');
    assert.ok(await details.evaluate(element => element.open));
    rows[id] = await details.locator('tbody tr').evaluateAll(elements => elements.map(row => [...row.children].map(cell => cell.textContent.trim())));
    assert.ok(rows[id].length > 0);
    assert.match(await details.locator('caption').innerText(), /合成示例 B/);
    assert.equal(await details.locator('table thead th').count() > 1, true);
    await details.locator(':scope > summary').click();
  }
  assert.equal(rows.trend.length, 7);
  assert.equal(rows.emotion.length, 6);
  assert.equal(rows.heatmap.length, 28);
  assert.equal(rows.histogram.length, 8);
  assert.equal(rows.scatter.length, 8);
  assert.equal(Number((await page.locator('[data-chart-overview="total"]').innerText()).replaceAll(',', '')), sum(data.daily.map(day => day.support)));
  assert.equal(await page.locator('[data-chart-overview="average"]').innerText(), (sum(data.daily.map(day => day.support)) / data.range).toFixed(1));
  assert.equal((await page.locator('[data-chart-period]').innerText()).replaceAll('.', '-'), data.period);
  const asText = values => values.map(row => row.map(String));
  assert.deepEqual(rows.trend, asText(data.daily.map(day => [day.date, day.support])));
  assert.deepEqual(rows.emotion.map(row => row.slice(0, 3)), asText(data.emotions.map(row => [row.name, row.field, row.value])));
  assert.deepEqual(rows.risk.map(row => row.slice(0, 2)), asText(data.risks.map(row => [row.name, row.value])));
  assert.deepEqual(rows.appointment, asText(data.appointments.map(row => [row.name, row.planned, row.completed])));
  assert.deepEqual(rows.channel.map(row => Number(row[2])), data.channels.flatMap(group => group.counts));
  assert.deepEqual(rows.channel.map(row => Number.parseFloat(row[3])), data.channels.flatMap(group => group.percentages));
  assert.deepEqual(rows.heatmap, asText(data.heatmap.map(row => [row.name, row.slot, row.value])));
  assert.deepEqual(rows.histogram, asText(data.histogram.map(bin => [`[${bin.min}, ${bin.max})`, bin.value])));
  assert.deepEqual(rows.scatter, asText(data.resources.map(row => [row.name, row.views, row.saves])));
  pass('all eight plots match current deterministic data; keyboard data tables', { sample: 'B', range: 7, tableRows: Object.fromEntries(Object.entries(rows).map(([id, values]) => [id, values.length])) });

  stage = 'current overview and table polish';
  const overview = [];
  for (const sample of ['A', 'B']) for (const range of [7, 14, 30]) {
    await page.locator('#chart-range').selectOption(String(range));
    await page.locator('#chart-sample').selectOption(sample);
    const fixture = getChartDemoData({ sample, range });
    const total = sum(fixture.daily.map(day => day.support));
    assert.equal(Number((await page.locator('[data-chart-overview="total"]').innerText()).replaceAll(',', '')), total);
    assert.equal(await page.locator('[data-chart-overview="average"]').innerText(), (total / range).toFixed(1));
    assert.equal((await page.locator('[data-chart-period]').innerText()).replaceAll('.', '-'), fixture.period);
    for (const id of ids) assert.equal(await page.locator(`#chart-data-${id} [data-chart-row-count]`).innerText(), `${await page.locator(`#chart-data-${id} tbody tr`).count()} 行`);
    overview.push({ sample, range, total, average: (total / range).toFixed(1) });
  }
  await page.locator('#chart-range').selectOption('7');
  await page.locator('#chart-sample').selectOption('B');
  await page.locator('#chart-data-emotion > summary').click();
  await shot('desktop-table.webp', page.locator('[data-chart-id="emotion"]'));
  await page.locator('#chart-data-emotion > summary').click();
  pass('current overview and row counts across six states', { overview });

  stage = 'actual SVG exports';
  for (const id of ids) {
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator(`[data-chart-export="${id}"]`).click()]);
    const bytes = await fs.readFile(await download.path());
    const svg = bytes.toString('utf8');
    assert.equal(download.suggestedFilename(), `chart-${id}-B-7d.svg`);
    assert.match(svg, /<title[^>]*>[^<]+<\/title>/);
    assert.match(svg, /合成示例 B/);
    assert.match(svg, /7天/);
    assert.match(svg, /不代表真实学生/);
    assert.ok((svg.match(/<path\b/g) || []).length > 5, 'Export contains actual chart geometry');
    assert.doesNotMatch(svg, /var\(--|<parsererror\b|<html\b/i);
    assert.doesNotMatch(svg, /<script\b|<foreignObject\b|\son\w+\s*=|(?:href|src)\s*=\s*["']https?:/i);
    const dimensions = await sharp(bytes).metadata();
    assert.deepEqual([dimensions.width, dimensions.height], [920, 550]);
    report.downloads.push({ id, filename: download.suggestedFilename(), bytes: bytes.length, sha256: sha(bytes), dimensions: [dimensions.width, dimensions.height] });
    if (id === 'emotion') {
      const exported = await context.newPage();
      await exported.setViewportSize({ width: 936, height: 566 });
      await exported.setContent(svg);
      assert.equal(await exported.locator('parsererror').count(), 0);
      await shot('export-emotion.webp', exported);
      await exported.close();
    }
  }
  pass('eight actual SVG downloads', { currentStateInFilenameAndContent: true, count: report.downloads.length });

  stage = 'invalid query defaults';
  await page.goto(`${preview}?qa=keep&chart-range=999&chart-sample=invalid&chart-use=constructor#charts`, { waitUntil: 'networkidle' });
  assert.equal(await page.locator('#chart-range').inputValue(), '14');
  assert.equal(await page.locator('#chart-sample').inputValue(), 'A');
  assert.equal(await page.locator('[data-chart-id]:visible').count(), 8);
  pass('invalid query safe defaults', { range: 14, sample: 'A', use: 'all' });

  stage = 'mobile chart details';
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.waitForFunction(width => document.documentElement.scrollWidth === width, width);
    for (const id of ids) {
      const rect = await page.locator(`[data-chart-id="${id}"]`).boundingBox();
      assert.ok(rect.x >= 0 && rect.x + rect.width <= width + 0.5, `${id} overflows at ${width}`);
    }
    await page.locator('#chart-data-emotion > summary').click();
    const tableReadability = await page.locator('#chart-data-emotion').evaluate(details => {
      const region = details.querySelector('.chart-table-wrap');
      const singleLineFields = [...details.querySelectorAll('tbody tr td:first-of-type')].every(cell => {
        const range = document.createRange();
        range.selectNodeContents(cell);
        return range.getClientRects().length <= 1;
      });
      region.scrollLeft = region.scrollWidth;
      const last = details.querySelector('tbody tr td:last-child').getBoundingClientRect();
      const bounds = region.getBoundingClientRect();
      const lastColumnReadable = last.left >= bounds.left - 1 && last.right <= bounds.right + 1;
      region.scrollLeft = 0;
      return { singleLineFields, lastColumnReadable };
    });
    assert.equal(tableReadability.singleLineFields, true, `Field words split at ${width}px`);
    assert.equal(tableReadability.lastColumnReadable, true, `Last data column unreachable at ${width}px`);
    await page.locator('#chart-data-emotion > summary').click();
    if (width === 390) {
      await page.locator('[data-chart-id="trend"]').scrollIntoViewIfNeeded();
      await shot('mobile-trend.webp');
      await page.locator('[data-chart-id="heatmap"]').scrollIntoViewIfNeeded();
      await shot('mobile-heatmap.webp');
      await shot('mobile-scatter.webp', page.locator('[data-chart-id="scatter"]'));
      await page.locator('#chart-data-channel > summary').click();
      assert.ok(await page.locator('#chart-data-channel table').isVisible());
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
      await page.locator('#chart-data-channel').scrollIntoViewIfNeeded();
      await shot('mobile-data.webp');
      await page.locator('#chart-data-channel > summary').click();
    }
  }
  pass('390 and 320 pixel mobile layouts', { noHorizontalOverflow: true, allEightCardsWithinViewport: true, dataTableVisible: true });

  stage = 'chart lifecycle events';
  const retained = await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    return document.querySelectorAll('.chart-canvas svg').length;
  });
  assert.equal(retained, 8);
  const released = await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false }));
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false }));
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    return document.querySelectorAll('.chart-canvas svg').length;
  });
  assert.equal(released, 0);
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelectorAll('.chart-canvas svg').length === 8);
  pass('chart lifecycle event handlers and reload', { persistedEventsRetain: 8, nonPersistedRelease: 0, noResurrectionAfterDispose: true, reloadRestores: 8 });

  stage = 'existing asset browser regression';
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator('[data-category="teachers"]').click();
  assert.equal(await page.locator('.asset-card').count(), 3);
  await page.locator('.asset-card').first().focus();
  await page.keyboard.press('Enter');
  await page.locator('#asset-dialog').waitFor({ state: 'visible' });
  await page.locator('#detail-format').selectOption('webp');
  await page.locator('#detail-size').selectOption('avatar-teacher-01-48-webp');
  const manifest = JSON.parse(await fs.readFile(path.join(root, 'src/assets/manifest.json'), 'utf8'));
  const expected = manifest.assets.find(item => item.id === 'avatar-teacher-01-48-webp');
  const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#download-asset').click()]);
  assert.equal(sha(await fs.readFile(await download.path())), expected.sha256);
  await page.keyboard.press('Escape');
  pass('existing asset detail and real download', { asset: expected.id, manifestHashMatches: true });
  assert.deepEqual(await page.evaluate(() => [...document.images].filter(image => image.complete && !image.naturalWidth).map(image => image.getAttribute('src'))), []);
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.warnings, []);
  assert.deepEqual(report.blockedRequests, []);
  report.status = 'passed';
  report.browser = await browser.version();
} catch (error) {
  report.status = 'failed';
  report.failure = { stage, message: String(error) };
  process.exitCode = 1;
} finally {
  await browser.close();
  await fs.writeFile(path.join(output, 'qa.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
