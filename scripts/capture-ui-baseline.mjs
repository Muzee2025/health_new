import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdir, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'

const require = createRequire(import.meta.url)
const scriptDir = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(scriptDir, '..')
const outputDir = resolve(repoRoot, 'docs/design/screenshots/before')
const baseUrl = process.env.BASELINE_BASE_URL || 'http://127.0.0.1:5173'
const viewport = { width: 1440, height: 900 }
const frozenTime = '2026-10-20T01:00:00.000Z'
const fakeToken = 'synthetic-baseline-token-only'
const syntheticStudent = { id: 'demo-student-900001', name: '演示学生', role: 'student', student_id: '演示编号-900001' }
const syntheticTeacher = { id: 'demo-teacher-900002', name: '演示教师', role: 'teacher', teacher_id: '演示编号-900002' }

function loadModule(envName, packageName) {
  const configured = process.env[envName]
  if (configured) return require(resolve(configured))
  return require(packageName)
}

const { chromium } = loadModule('PLAYWRIGHT_MODULE_PATH', 'playwright')
const sharp = loadModule('SHARP_MODULE_PATH', 'sharp')

const svgPlaceholder = Buffer.from(
  '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200"><defs><linearGradient id="g"><stop stop-color="#dbeafe"/><stop offset="1" stop-color="#ede9fe"/></linearGradient></defs><rect width="320" height="200" rx="20" fill="url(#g)"/><circle cx="160" cy="75" r="32" fill="#93c5fd"/><path d="M92 178c8-40 34-58 68-58s60 18 68 58" fill="#c4b5fd"/><text x="160" y="194" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#475569">合成演示素材</text></svg>'
)

const dates7 = ['10-14', '10-15', '10-16', '10-17', '10-18', '10-19', '10-20']
const fixtureTable = [
  [/^\/api\/student\/dashboard\/latest_scores$/, () => [
    { name: 'SDS', score: 42, norm: 41 }, { name: 'SAS', score: 39, norm: 40 }, { name: '心理年龄', score: 28, norm: 45 },
  ]],
  [/^\/api\/student\/dashboard\/red_energy$/, () => dates7.map((date, i) => ({ date, score: [5, 7, 6, 8, 7, 9, 8][i] }))],
  [/^\/api\/student\/dashboard\/treehole_words$/, () => [
    { word: '平静', count: 8 }, { word: '学习', count: 6 }, { word: '压力', count: 4 }, { word: '朋友', count: 3 },
  ]],
  [/^\/api\/student\/dashboard\/appointment_stats$/, () => ({ completed: 3, pending: 1, cancelled: 0, total: 4, next_appointment: null })],
  [/^\/api\/student\/dashboard\/stats$/, () => ({ red_energy: 28 })],
  [/^\/api\/student\/treehole\/posts$/, () => [
    { id: 'demo-post-01', content: '最近在练习把任务拆成更小的步骤，完成后会轻松一些。', tags: '学习,成长', likes: 6, favorites: 2, comments_count: 1, created_at: '2026-10-19T08:30:00+08:00', is_anonymous: true },
    { id: 'demo-post-02', content: '今天和朋友一起散步，心情放松了不少。', tags: '日常,陪伴', likes: 4, favorites: 1, comments_count: 0, created_at: '2026-10-18T15:10:00+08:00', is_anonymous: true },
  ]],
  [/^\/api\/student\/treehole\/[^/]+\/comments$/, () => []],
  [/^\/api\/student\/treehole\/search_by_word$/, () => []],
  [/^\/api\/student\/teachers$/, () => [{ id: 'demo-teacher-01', name: '林老师', title: '心理咨询师', consultation_direction: '压力与适应', location: '心理中心 201', intro: '关注学习压力与情绪调适，提供支持性谈话。', time_slots: ['2026-10-21 14:00-14:50', '2026-10-22 10:00-10:50'], booked_slots: [] }]],
  [/^\/api\/student\/appointments$/, () => [{ id: 'demo-appointment-01', time_slot: '2026-10-22 10:00-10:50', teacher_name: '林老师', location: '心理中心 201', status: 'pending' }]],
  [/^\/api\/student\/articles$/, () => [{ id: 'demo-article-01', title: '给日常压力留一个缓冲区', summary: '从呼吸、作息和任务安排开始，建立简单可持续的自我照顾习惯。', category: '情绪管理', source: '合成演示内容', views: 36, cover_url: '/__synthetic__/cover.svg' }, { id: 'demo-article-02', title: '睡前放松的三个小练习', summary: '用温和的节奏帮助身心逐渐安静下来。', category: '睡眠健康', source: '合成演示内容', views: 24, cover_url: '/__synthetic__/cover.svg' }]],
  [/^\/api\/student\/questions$/, () => [{ id: 'demo-question-01', question_text: '考试前如何安排复习和休息？', answer: '可以先列出重点任务，再穿插短暂休息。', status: 'answered', created_at: '2026-10-18T09:00:00+08:00' }]],
  [/^\/api\/advanced-ai\/sessions$/, () => []],
  [/^\/api\/advanced-ai\/sessions\/[^/]+\/messages$/, () => []],
  [/^\/api\/v1\/report\/analysis\/latest$/, () => ({ status: 'complete', data: {
    updated_at: '2026-10-20T09:00:00+08:00', risk: { risk_level: 'LOW', depression_confidence: 26, anxiety_confidence: 34, suicide_confidence: 4 },
    scores: { emotion: 72, cognition: 68, behavior: 75 }, source: { message_count: 12, messages: [
      { emotion_tags: { joy: 3, sadness: 1, fear: 0, anger: 0, neutral: 5 } }, { emotion_tags: { joy: 2, sadness: 1, fear: 1, anger: 0, neutral: 4 } },
    ] }, interventions: [], trends: {
      heatmap: dates7.map((date, i) => ({ date: `2026-${date.slice(0, 2)}-${date.slice(3)}`, depression: 20 + i, anxiety: 28 + (i % 3), suicide: 3 })),
      seven_days: dates7.map((date, i) => ({ date: `2026-${date.slice(0, 2)}-${date.slice(3)}`, score: 62 + i })),
      thirty_days: Array.from({ length: 30 }, (_, i) => ({ date: `2026-10-${String(Math.max(1, i + 1)).padStart(2, '0')}`, score: 55 + (i % 11) })),
    }, chart_insights: {},
  } })],
  [/^\/api\/v1\/model\/current$/, () => ({ data: { model_name: '合成演示模型', legacy_alias: 'synthetic-model' } })],
  [/^\/api\/teacher\/crisis\/pending$/, () => ({ data: { items: [] } })],
  [/^\/api\/advanced-teacher\/dashboard\/metrics$/, () => ({
    realtime_stats: { uv: 128, avg_session_rounds: 6.4, crisis_alerts: 2 },
    funnel_data: [{ name: '测评', value: 100 }, { name: '关注', value: 60 }, { name: '沟通', value: 35 }, { name: '支持', value: 18 }],
    emotion_trends_7d: { dates: dates7, joy: [0.55, 0.61, 0.58, 0.64, 0.67, 0.62, 0.7], anxiety: [0.42, 0.38, 0.44, 0.4, 0.36, 0.39, 0.33] },
    campus_heatmap: [{ building: '明心楼', risk_density: 0.34 }, { building: '知行楼', risk_density: 0.58 }, { building: '笃学楼', risk_density: 0.22 }],
  })],
  [/^\/api\/teacher\/students$/, () => [{ id: 'demo-student-900001', name: '演示学生', student_id: '演示编号-900001', class_name: '演示班级', advisor: '演示教师', risk_level: 'green', latest_test_time: '2026-10-19T09:00:00+08:00', latest_test_score: 28, has_pending_crisis: false, pending_crisis_count: 0 }]],
  [/^\/api\/teacher\/student\/900001$/, () => ({ student_info: { id: 'demo-student-900001', name: '演示学生', student_id: '演示编号-900001', advisor: '演示教师', phone: '000-0000-0000' }, ai_analysis: '本页使用虚构的合成数据展示档案结构，不代表真实测评或诊断。', test_history: [{ id: 'demo-test-01', test_name: '情绪状态自评', test_date: '2026-10-19', score: 28, risk_level: 'green' }], intervention_records: [{ id: 'demo-intervention-01', notes: '已提供日常情绪管理资源。', record_date: '2026-10-19', created_at: '2026-10-19T10:00:00+08:00' }] })],
  [/^\/api\/teacher\/appointments$/, () => [{ id: 'demo-appointment-01', student_name: '演示学生', teacher_name: '演示教师', teacher_id: 'demo-teacher-900002', time_slot: '2026-10-22 10:00-10:50', status: 'pending' }]],
  [/^\/api\/teacher\/articles$/, () => [{ id: 'demo-article-01', title: '给日常压力留一个缓冲区', summary: '合成演示内容。', category: '情绪管理', views: 36, created_at: '2026-10-18T09:00:00+08:00' }]],
  [/^\/api\/teacher\/teachers_profiles$/, () => [{ id: 'demo-profile-01', user_id: 'demo-teacher-900002', name: '演示教师', title: '心理咨询师', intro: '合成演示教师资料。', location: '心理中心 201', time_slots: [] }]],
  [/^\/api\/teacher\/interventions$/, () => [{ id: 'demo-intervention-01', student_id: 'demo-student-900001', student_name: '演示学生', teacher_name: '演示教师', record_date: '2026-10-19', created_at: '2026-10-19T10:00:00+08:00', notes: '已提供日常情绪管理资源。' }]],
]

const routes = [
  { path: '/student/dashboard', role: 'student', name: 'student-dashboard' },
  { path: '/student/test', role: 'student', name: 'student-test' },
  { path: '/student/appointments', role: 'student', name: 'student-appointments' },
  { path: '/student/articles', role: 'student', name: 'student-articles' },
  { path: '/student/advanced-chat', role: 'student', name: 'student-advanced-chat' },
  { path: '/student/report', role: 'student', name: 'student-report' },
  { path: '/student/treehole', role: 'student', name: 'student-treehole' },
  { path: '/student/questions', role: 'student', name: 'student-questions' },
  { path: '/teacher/advanced-dashboard', role: 'teacher', name: 'teacher-advanced-dashboard' },
  { path: '/teacher/students', role: 'teacher', name: 'teacher-students' },
  { path: '/teacher/student/900001', role: 'teacher', name: 'teacher-student-900001' },
  { path: '/teacher/appointments', role: 'teacher', name: 'teacher-appointments' },
  { path: '/teacher/content', role: 'teacher', name: 'teacher-content' },
  { path: '/teacher/interventions', role: 'teacher', name: 'teacher-interventions' },
]

const fixtureFor = (path) => fixtureTable.find(([pattern]) => pattern.test(path))?.[1]()
const isApi = (url) => new URL(url).pathname.startsWith('/api/')

const results = []
const configuredExecutablePath = process.env.BASELINE_EXECUTABLE_PATH
const browserChannel = process.env.BASELINE_BROWSER_CHANNEL || 'msedge'
const launchOptions = { headless: true, ...(configuredExecutablePath ? { executablePath: resolve(configuredExecutablePath) } : { channel: browserChannel }) }
let browser

try {
  browser = await chromium.launch(launchOptions)
} catch (error) {
  throw new Error(`Could not launch ${launchOptions.channel}; set BASELINE_BROWSER_CHANNEL or install/configure Edge. ${error.message}`)
}

try {
  await mkdir(outputDir, { recursive: true })
  for (const routeConfig of routes) {
    const context = await browser.newContext({
      viewport,
      serviceWorkers: 'block',
      locale: 'zh-CN',
      timezoneId: 'Asia/Shanghai',
      colorScheme: 'light',
      reducedMotion: 'reduce',
    })
    await context.addInitScript(({ role, token, user, now }) => {
      localStorage.clear()
      localStorage.setItem('token', token)
      localStorage.setItem('role', role)
      localStorage.setItem('user', JSON.stringify(user))
      const NativeDate = Date
      const fixedEpoch = NativeDate.parse(now)
      const originPerformance = performance.now()
      const anchoredNow = () => fixedEpoch + (performance.now() - originPerformance)
      class FixedDate extends NativeDate {
        constructor(...args) { super(...(args.length ? args : [anchoredNow()])) }
        static now() { return anchoredNow() }
      }
      Object.defineProperty(window, 'Date', { configurable: true, value: FixedDate })
      window.EventSource = class SyntheticEventSource extends EventTarget { close() {} }
    }, { role: routeConfig.role, token: fakeToken, user: routeConfig.role === 'student' ? syntheticStudent : syntheticTeacher, now: frozenTime })

    const page = await context.newPage()
    const apiRequests = []
    const unknownApis = []
    const blockedRequests = []
    const syntheticResources = []
    const consoleEvents = []
    const pageErrors = []
    const blockedSockets = []
    page.on('console', (message) => {
      if (message.type() === 'error' || message.type() === 'warning') consoleEvents.push({ type: message.type(), text: message.text().slice(0, 500) })
    })
    page.on('pageerror', (error) => pageErrors.push(String(error?.message || error).slice(0, 500)))
    await page.routeWebSocket('**/*', (socket) => {
      blockedSockets.push('websocket-intercepted')
      socket.onMessage(() => {})
    })

    await context.route('**/*', async (route) => {
      const request = route.request()
      const requestUrl = request.url()
      let parsed
      try { parsed = new URL(requestUrl) } catch { blockedRequests.push({ reason: 'invalid-url' }); return route.abort() }

      if (parsed.pathname.startsWith('/api/')) {
        const body = fixtureFor(parsed.pathname)
        const entry = { method: request.method(), path: parsed.pathname, status: body === undefined ? 501 : 200 }
        apiRequests.push(entry)
        if (body === undefined) {
          unknownApis.push(entry)
          return route.fulfill({ status: 501, contentType: 'application/json', body: JSON.stringify({ detail: 'Unmapped synthetic baseline API fixture' }) })
        }
        if (request.method() === 'GET' || request.method() === 'HEAD') {
          return route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify(body) })
        }
        return route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: JSON.stringify({ success: true, data: body }) })
      }

      if (parsed.pathname.startsWith('/__synthetic__/')) {
        syntheticResources.push({ origin: parsed.origin, path: parsed.pathname })
        return route.fulfill({ status: 200, contentType: 'image/svg+xml; charset=utf-8', body: svgPlaceholder, headers: { 'access-control-allow-origin': '*' } })
      }
      if (/cdnjs\.cloudflare\.com/.test(parsed.hostname) && parsed.pathname.endsWith('.css')) {
        blockedRequests.push({ origin: parsed.origin, path: parsed.pathname, syntheticResponse: 'empty-css' })
        return route.fulfill({ status: 200, contentType: 'text/css; charset=utf-8', body: '/* External stylesheet intentionally not loaded in synthetic capture. */' })
      }
      if (parsed.origin === baseUrl) return route.continue()
      blockedRequests.push({ origin: parsed.origin, path: parsed.pathname })
      if (/api\.dicebear\.com|cube\.elemecdn\.com|picsum\.photos/.test(parsed.hostname)) {
        return route.fulfill({ status: 200, contentType: 'image/svg+xml', body: svgPlaceholder, headers: { 'access-control-allow-origin': '*' } })
      }
      return route.abort('blockedbyclient')
    })

    let navigationError = null
    try {
      await page.goto(`${baseUrl}${routeConfig.path}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
      await page.waitForLoadState('load', { timeout: 12000 }).catch(() => {})
      await page.waitForTimeout(1200)
      await page.evaluate(() => document.fonts?.ready)
    } catch (error) {
      navigationError = String(error.message).slice(0, 400)
    }

    if (routeConfig.name === 'student-dashboard' && !navigationError) {
      const selects = page.locator('.trend-tools .el-select, .trend-tools select')
      if (await selects.count()) {
        const originalText = (await selects.first().innerText().catch(() => '')).trim()
        await selects.first().click().catch(() => {})
        const targetOption = page.locator('.el-select-dropdown__item').filter({ hasText: '近90天' }).first()
        await targetOption.waitFor({ state: 'visible', timeout: 2500 }).catch(() => {})
        if (await targetOption.isVisible().catch(() => false)) {
          await targetOption.click().catch(() => {})
          await page.waitForTimeout(250)
          const changedText = (await selects.first().innerText().catch(() => '')).trim()
          const changed = changedText.includes('近90天') && changedText !== originalText
          results.push({ interaction: 'student-dashboard-trend-range', observed: changed, from: originalText, to: changedText })
          if (changed) {
            await selects.first().click().catch(() => {})
            const restoreOption = page.locator('.el-select-dropdown__item').filter({ hasText: '近30天' }).first()
            await restoreOption.waitFor({ state: 'visible', timeout: 2500 }).catch(() => {})
            if (await restoreOption.isVisible().catch(() => false)) {
              await restoreOption.click().catch(() => {})
              await page.waitForTimeout(1800)
            }
          }
        } else {
          results.push({ interaction: 'student-dashboard-trend-range', observed: false, reason: 'Expected 近90天 option did not render' })
        }
      } else {
        results.push({ interaction: 'student-dashboard-trend-range', observed: false, reason: 'Trend range selector not found' })
      }
      await page.waitForTimeout(300)
    }

    const identity = await page.evaluate(() => ({ title: document.title, url: location.href, text: document.body?.innerText?.trim() || '' })).catch(() => ({ title: '', url: page.url(), text: '' }))
    const bodyText = identity.text
    const frameworkOverlay = await page.locator('vite-error-overlay, #webpack-dev-server-client-overlay, nextjs-portal').count().catch(() => 0)
    const hasContent = bodyText.length > 40 && !/^Internal Server Error\s*$/.test(bodyText)
    const imageHealth = await page.evaluate(async () => {
      const images = Array.from(document.images)
      images.forEach((image) => { if (image.loading === 'lazy') image.loading = 'eager' })
      await Promise.race([
        Promise.all(images.map((image) => image.decode().catch(() => null))),
        new Promise((resolve) => setTimeout(resolve, 2000)),
      ])
      return images.map((image) => ({
        src: (() => { try { const url = new URL(image.currentSrc || image.src, location.href); return `${url.origin}${url.pathname}` } catch { return 'invalid-url' } })(),
        complete: image.complete,
        naturalWidth: image.naturalWidth,
        naturalHeight: image.naturalHeight,
      }))
    }).catch(() => [])
    await page.evaluate(() => {
      const badge = document.createElement('div')
      badge.id = 'synthetic-baseline-badge'
      badge.textContent = '合成演示数据 · 改造前基线'
      Object.assign(badge.style, {
        position: 'fixed', left: '12px', bottom: '12px', zIndex: '2147483647',
        pointerEvents: 'none', padding: '9px 16px', borderRadius: '10px',
        background: 'rgba(15, 23, 42, 0.94)', color: '#fff',
        font: '700 13px/16px "Microsoft YaHei", sans-serif',
        boxShadow: '0 3px 12px rgba(15, 23, 42, 0.22)', whiteSpace: 'nowrap',
      })
      document.body.appendChild(badge)
    }).catch(() => {})
    const outputPath = resolve(outputDir, `${routeConfig.name}-1440.webp`)
    let screenshotSha256 = null
    let screenshotBytes = null
    if (!navigationError && hasContent) {
      const png = await page.screenshot({ type: 'png', animations: 'disabled', caret: 'hide', timeout: 30000 })
      const webp = await sharp(png).webp({ quality: 80, effort: 6 }).toBuffer()
      await writeFile(outputPath, webp)
      screenshotBytes = webp.length
      screenshotSha256 = createHash('sha256').update(webp).digest('hex')
    }

    const pageResult = {
      name: routeConfig.name,
      path: routeConfig.path,
      url: identity.url,
      title: identity.title,
      viewport,
      bodyTextLength: bodyText.length,
      nonBlank: hasContent,
      frameworkOverlay: frameworkOverlay > 0,
      navigationError,
      imageHealth,
      imageLoadFailures: imageHealth.filter((image) => image.complete && image.naturalWidth === 0).length,
      syntheticResourceCount: syntheticResources.length,
      screenshot: screenshotSha256 ? { file: `${routeConfig.name}-1440.webp`, bytes: screenshotBytes, sha256: screenshotSha256 } : null,
      console: consoleEvents,
      pageErrors,
      apiRequestCount: apiRequests.length,
      apiRequests,
      blockedExternalRequestCount: blockedRequests.length,
      blockedWebSocketCount: blockedSockets.length,
      unknownApis,
    }
    results.push(pageResult)
    await context.close()
  }
} finally {
  await browser.close()
}

const browserPluginAvailable = false
const manifest = {
  schemaVersion: 1,
  owner: 'E04',
  task: 'W1-T7',
  status: 'synthetic-baseline-captured',
  generatedAt: new Date().toISOString(),
  fixtureTime: frozenTime,
  baselineLabel: '合成演示数据 · 改造前基线',
  source: '当前前端基线；所有 API 均由本脚本在浏览器路由层合成响应。真实后端、真实账号、真实学生数据均未使用。',
  app: baseUrl,
  viewport,
  timezone: 'Asia/Shanghai',
  browser: { engine: 'Chromium', channel: configuredExecutablePath ? null : browserChannel, executablePathConfigured: Boolean(configuredExecutablePath), headless: true, browserPluginAvailable, fallbackReason: 'Browser plugin not available; isolation requires per-request Playwright routing and synthetic API fulfillment.' },
  artifactFormat: 'WebP',
  maxBytes: 300 * 1024,
  pages: results.filter((item) => item.path),
  interactions: results.filter((item) => item.interaction),
  totals: {
    expectedPages: routes.length,
    capturedPages: results.filter((item) => item.screenshot).length,
    unknownApiCount: results.filter((item) => item.path).flatMap((item) => item.unknownApis).length,
    pageErrorCount: results.filter((item) => item.path).flatMap((item) => item.pageErrors).length,
    imageLoadFailureCount: results.filter((item) => item.path).reduce((sum, item) => sum + item.imageLoadFailures, 0),
    pagesOverLimit: results.filter((item) => item.screenshot && item.screenshot.bytes > 300 * 1024).map((item) => item.name),
  },
}
await writeFile(resolve(outputDir, 'baseline.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')

const failed = manifest.totals.capturedPages !== routes.length || manifest.totals.unknownApiCount > 0 || manifest.totals.pageErrorCount > 0 || manifest.totals.imageLoadFailureCount > 0 || manifest.totals.pagesOverLimit.length > 0 || manifest.pages.some((item) => item.navigationError || !item.nonBlank || item.frameworkOverlay)
console.log(JSON.stringify({ outputDir, totals: manifest.totals, pages: manifest.pages.map((page) => ({ name: page.name, bytes: page.screenshot?.bytes, nonBlank: page.nonBlank, frameworkOverlay: page.frameworkOverlay, errors: page.pageErrors.length, unknownApis: page.unknownApis.length })) }, null, 2))
if (failed) process.exitCode = 1
