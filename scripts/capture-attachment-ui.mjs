// Current project UI evidence for the supplied Word attachment. No backend is used.
import { createRequire } from 'node:module'
import { resolve, extname } from 'node:path'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { createServer } from 'node:http'
import { pathToFileURL } from 'node:url'

const root = process.cwd()
const out = resolve(root, 'tmp/attachment-system-20261029')
const bundle =
  'C:/Users/14012/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
const runtimeRequire = createRequire(resolve(bundle, '../package.json'))
const { chromium } = runtimeRequire('playwright')
const projectRequire = createRequire(resolve(root, 'package.json'))
const { build } = await import(pathToFileURL(projectRequire.resolve('vite')).href)
await mkdir(resolve(out, 'screens'), { recursive: true })
await build({
  root,
  envDir: false,
  build: { outDir: resolve(out, 'dist'), emptyOutDir: true },
  logLevel: 'warn',
})

const fixtureSource = (
  await readFile(resolve(root, 'scripts/capture-w2-ui.mjs'), 'utf8')
).replaceAll('\r\n', '\n')
const snippet = fixtureSource.slice(
  fixtureSource.indexOf('const fixtureTable = ['),
  fixtureSource.indexOf('\nconst baseRoutes = ['),
)
const dates7 = ['10-22', '10-23', '10-24', '10-25', '10-26', '10-27', '10-28']
const fixtures = new Function('dates7', `${snippet}; return fixtureTable;`)(dates7)
const catalog = JSON.parse(
  await readFile(resolve(root, 'backend/scripts/content-catalog.json'), 'utf8'),
)
const articles = catalog.articles.map((a, i) => ({
  ...a,
  id: 900100 + i,
  views: 0,
  created_at: '2026-10-28T09:00:00+08:00',
}))
const overrides = new Map([
  [
    '/api/advanced-ai/sessions',
    {
      data: [
        {
          id: 'synthetic-session-01',
          title: '操作演示对话',
          mode: 'daily',
          updated_at: '2026-10-28T09:00:00+08:00',
        },
      ],
    },
  ],
  [
    '/api/advanced-ai/sessions/synthetic-session-01/messages',
    {
      data: [
        {
          id: 'synthetic-message-01',
          role: 'user',
          content: '这是用于展示界面的虚构对话。怎样查看自己的测评记录？',
          created_at: '2026-10-28T09:00:00+08:00',
        },
        {
          id: 'synthetic-message-02',
          role: 'ai',
          content:
            '【合成演示回复】可从“心理测评”和“个人报告”查看相关页面。本段文字为预设示例，未调用真实模型。',
          created_at: '2026-10-28T09:01:00+08:00',
        },
      ],
    },
  ],
  ['/api/student/articles', articles],
  ['/api/teacher/articles', articles],
])
function fixture(path) {
  if (overrides.has(path)) return overrides.get(path)
  if (/^\/api\/(student|teacher)\/articles\/page$/.test(path))
    return {
      items: articles.map(({ content, ...a }) => a),
      total: articles.length,
      page: 1,
      page_size: 12,
      categories: ['平台使用指南'],
    }
  return fixtures.find(([pattern]) => pattern.test(path))?.[1]()
}
const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
}
const server = createServer(async (req, res) => {
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname)
    if (req.method !== 'GET' || path.startsWith('/api/') || path.includes('..')) {
      res.writeHead(403)
      res.end()
      return
    }
    const file = resolve(out, 'dist', path.replace(/^\//, ''))
    let bytes
    try {
      bytes = await readFile(file)
    } catch {
      bytes = await readFile(resolve(out, 'dist/index.html'))
    }
    res.writeHead(200, { 'content-type': types[extname(file)] || 'text/html; charset=utf-8' })
    res.end(bytes)
  } catch {
    res.writeHead(500)
    res.end()
  }
})
await new Promise((r) => server.listen(0, '127.0.0.1', r))
const origin = `http://127.0.0.1:${server.address().port}`
const cases = [
  ['student-dashboard', 'student', '/student/dashboard'],
  ['student-test', 'student', '/student/test'],
  ['student-chat', 'student', '/student/advanced-chat'],
  ['student-report', 'student', '/student/report'],
  ['teacher-dashboard', 'teacher', '/teacher/advanced-dashboard'],
  ['teacher-support', 'teacher', '/teacher/support'],
  ['teacher-student', 'teacher', '/teacher/student/900001'],
  ['teacher-content', 'teacher', '/teacher/content'],
]
const evidence = []
let browser
try {
  browser = await chromium.launch({ headless: true, channel: 'msedge' })
  for (const [name, role, path] of cases) {
    const width = ['student-chat', 'student-report', 'teacher-content'].includes(name)
      ? 1440
      : name === 'teacher-student'
        ? 1280
        : 1040
    const context = await browser.newContext({
      viewport: { width, height: 870 },
      deviceScaleFactor: 2,
      serviceWorkers: 'block',
      locale: 'zh-CN',
      timezoneId: 'Asia/Shanghai',
      reducedMotion: 'reduce',
    })
    const record = {
      name,
      role,
      path,
      api: [],
      unknownApis: [],
      externalBlocked: [],
      pageErrors: [],
      consoleErrors: [],
    }
    await context.addInitScript(
      ({ role }) => {
        localStorage.clear()
        localStorage.setItem('token', 'synthetic-attachment-capture-only')
        localStorage.setItem('role', role)
        localStorage.setItem(
          'user',
          JSON.stringify({
            id: role === 'student' ? 'demo-student-900001' : 'demo-teacher-900002',
            name: role === 'student' ? '演示学生' : '演示教师',
            role,
            student_id: '演示编号-900001',
          }),
        )
        window.EventSource = class extends EventTarget {
          close() {}
        }
      },
      { role },
    )
    await context.route('**/*', async (route) => {
      const request = route.request(),
        url = new URL(request.url())
      if (url.pathname.startsWith('/api/')) {
        const body = fixture(url.pathname)
        record.api.push({
          method: request.method(),
          path: url.pathname,
          status: body === undefined ? 501 : 200,
        })
        if (body === undefined) record.unknownApis.push(url.pathname)
        return route.fulfill({
          status: body === undefined ? 501 : 200,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify(body ?? { detail: 'Unmapped synthetic fixture' }),
        })
      }
      if (url.pathname.startsWith('/__synthetic__/'))
        return route.fulfill({
          contentType: 'image/svg+xml',
          body: await readFile(resolve(root, 'src/assets/brand/brand-logo-vertical.svg')),
        })
      if (url.origin === origin) return route.continue()
      record.externalBlocked.push(url.origin + url.pathname)
      return route.abort()
    })
    const page = await context.newPage()
    await page.routeWebSocket('**/*', (socket) => socket.onMessage(() => {}))
    page.on('pageerror', (e) => record.pageErrors.push(e.message))
    page.on('console', (m) => {
      if (m.type() === 'error') record.consoleErrors.push(m.text().slice(0, 300))
    })
    await page.goto(origin + path, { waitUntil: 'networkidle' })
    await page.locator('.main-content').waitFor()
    if (name === 'student-test')
      await page.getByRole('button', { name: '开始测试', exact: true }).first().click()
    await page.evaluate(() => document.fonts.ready)
    await page.waitForTimeout(1400)
    const box = await page.locator('.main-content').boundingBox()
    await page.evaluate(
      ({ x }) => {
        const badge = document.createElement('div')
        badge.textContent = '合成演示数据'
        badge.setAttribute('data-capture-provenance', 'synthetic')
        Object.assign(badge.style, {
          position: 'fixed',
          top: '12px',
          left: `${x + 350}px`,
          padding: '4px 8px',
          background: '#ffffff',
          color: '#334155',
          border: '1px solid #64748b',
          font: '13px sans-serif',
          zIndex: '99999',
          borderRadius: '4px',
        })
        document.body.appendChild(badge)
      },
      { x: box.x },
    )
    const clip = { x: box.x, y: 0, width: width - box.x, height: 850 }
    const imagePath = resolve(out, 'screens', `${name}.png`)
    await page.screenshot({ path: imagePath, clip, animations: 'disabled' })
    record.image = imagePath
    record.imageSha256 = createHash('sha256')
      .update(await readFile(imagePath))
      .digest('hex')
    record.clip = clip
    record.text = (await page.locator('.main-content').innerText()).slice(0, 12000)
    if (/文章列表暂时无法加载|报告暂时无法加载|统计数据加载失败/.test(record.text))
      record.pageErrors.push('Visible load error')
    record.brokenImages = await page
      .locator('img')
      .evaluateAll((imgs) =>
        imgs.filter((i) => !i.complete || i.naturalWidth === 0).map((i) => i.getAttribute('src')),
      )
    evidence.push(record)
    console.log(
      JSON.stringify({
        name,
        unknownApis: record.unknownApis,
        pageErrors: record.pageErrors,
        consoleErrors: record.consoleErrors,
        brokenImages: record.brokenImages,
      }),
    )
    await context.close()
  }
} finally {
  if (browser) await browser.close()
  await new Promise((r) => server.close(r))
}
await writeFile(
  resolve(out, 'capture-evidence.json'),
  JSON.stringify(
    {
      captured: new Date().toISOString(),
      source: 'current project production build',
      synthetic: true,
      backendUsed: false,
      cases: evidence,
    },
    null,
    2,
  ),
)
if (
  evidence.some(
    (r) =>
      r.unknownApis.length ||
      r.pageErrors.length ||
      r.consoleErrors.length ||
      r.brokenImages.length,
  )
)
  process.exitCode = 1
