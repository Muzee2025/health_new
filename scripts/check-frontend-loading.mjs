// Measure cold authentication-page requests against an isolated compiled build.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { gzipSync } from 'node:zlib'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright')
const base = new URL(process.env.LOADING_BASE_URL || 'http://127.0.0.1:4185')
assert.equal(base.hostname, '127.0.0.1', 'Use an isolated loopback compiled preview')
const directory = path.resolve(process.env.LOADING_BUILD_DIR || 'tmp/frontend-audit')
const enforce = process.env.LOADING_ENFORCE !== '0'
const output = path.resolve(process.env.LOADING_REPORT || 'tmp/frontend-loading.json')
let origins = null
try {
  origins = JSON.parse(await fs.readFile(path.join(directory, '.vite/module-origins.json'), 'utf8'))
} catch {}
const browser = await chromium.launch({ headless: true, channel: 'msedge' })
const results = []
try {
  for (const width of [1440, 390])
    for (const route of ['/login', '/register']) {
      const context = await browser.newContext({
        viewport: { width, height: 900 },
        serviceWorkers: 'block',
      })
      const page = await context.newPage()
      const responses = []
      const errors = []
      const warnings = []
      const expectedWarnings = []
      const blocked = []
      page.on('pageerror', (error) => errors.push(error.message))
      page.on('console', (message) => {
        if (['error', 'warning'].includes(message.type())) {
          if (
            message.text().includes('ServiceWorker registration failed') ||
            message.text() === 'Service Worker registration blocked by Playwright'
          )
            expectedWarnings.push(message.text())
          else warnings.push(message.text())
        }
      })
      page.on('response', (response) => {
        if (new URL(response.url()).pathname.endsWith('.js')) responses.push(response)
      })
      await context.route('**/*', (request) => {
        const url = new URL(request.request().url())
        if (url.origin !== base.origin || url.pathname.startsWith('/api/')) {
          blocked.push(url.pathname)
          return request.abort()
        }
        return request.continue()
      })
      await page.goto(new URL(route, base).href)
      await page
        .getByRole('heading', {
          name: route === '/login' ? '欢迎回来' : '创建学生账号',
          exact: true,
        })
        .waitFor()
      await page.waitForLoadState('networkidle')
      assert.equal(await page.title(), '心域智链平台')
      const scripts = []
      for (const response of new Map(responses.map((item) => [item.url(), item])).values()) {
        const pathname = new URL(response.url()).pathname
        const absolute = path.resolve(directory, '.' + decodeURIComponent(pathname))
        assert(absolute.startsWith(directory + path.sep), 'Asset must remain inside selected build')
        const bytes = await fs.readFile(absolute)
        assert.equal(response.status(), 200)
        const encoding = response.headers()['content-encoding'] || 'identity'
        const encoded = Number(response.headers()['content-length'])
        assert(
          Number.isFinite(encoded) && encoded > 0,
          'Preview must expose actual response body length',
        )
        const gzip = gzipSync(bytes).length
        const kinds = origins?.[pathname.slice(1)]?.kinds || []
        if (enforce)
          assert(origins?.[pathname.slice(1)], 'Requested script is missing module-origin metadata')
        scripts.push({
          file: pathname,
          rawBytes: bytes.length,
          gzipBytes: gzip,
          servedEncoding: encoding,
          servedBodyBytes: encoded,
          moduleKinds: kinds,
        })
      }
      const overlay = await page.locator('vite-error-overlay').count()
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 2,
      )
      assert.equal(overlay, 0)
      assert.equal(overflow, false)
      assert.deepEqual(errors, [])
      assert.deepEqual(warnings, [])
      assert.deepEqual(blocked, [])
      const row = {
        route,
        width,
        status: 'passed',
        scriptCount: scripts.length,
        rawJsBytes: scripts.reduce((sum, item) => sum + item.rawBytes, 0),
        gzipJsBytes: scripts.reduce((sum, item) => sum + item.gzipBytes, 0),
        servedJsBodyBytes: scripts.reduce((sum, item) => sum + item.servedBodyBytes, 0),
        scripts,
        moduleMapAvailable: Boolean(origins),
        pageErrors: errors,
        unexpectedConsole: warnings,
        expectedWarnings,
        blockedRequests: blocked,
        overlay,
        overflow,
      }
      if (enforce) {
        assert(origins, 'Module-origin metadata is required for the loading budget')
        assert(row.gzipJsBytes <= 250 * 1024, 'Cold auth JS exceeds the 250 KiB gzip budget')
        assert(
          !scripts.some((item) =>
            item.moduleKinds.some((kind) => ['echarts', 'zrender', 'chartjs'].includes(kind)),
          ),
          'Chart engines entered cold authentication requests',
        )
      }
      results.push(row)
      await context.close()
    }
} finally {
  await browser.close()
}
const report = {
  schemaVersion: 1,
  task: 'W2-PERF-COLD-AUTH',
  checkedAt: new Date().toISOString(),
  baseUrl: base.origin,
  status: 'passed',
  method:
    'Fresh browser context per route/viewport; compiled files only; server gzip Content-Length and local raw/gzip byte totals. Counts exclude headers and HTML/CSS/images; not a network-latency benchmark.',
  browser: 'Playwright with installed Edge; Browser plugin not available',
  apiCallsAllowed: false,
  budgetsEnforced: enforce,
  results,
}
await fs.mkdir(path.dirname(output), { recursive: true })
await fs.writeFile(output, JSON.stringify(report, null, 2) + '\n')
console.log(
  JSON.stringify({
    status: report.status,
    results: results.map(
      ({ route, width, scriptCount, rawJsBytes, gzipJsBytes, servedJsBodyBytes }) => ({
        route,
        width,
        scriptCount,
        rawJsBytes,
        gzipJsBytes,
        servedJsBodyBytes,
      }),
    ),
  }),
)
