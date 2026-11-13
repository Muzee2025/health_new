// Real HTTP/browser verification. Only synthetic accounts in a new private QA DB.
import assert from 'node:assert/strict'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { loadScriptDependencies } from './optional-script-dependencies.mjs'
import { resolve, relative, sep } from 'node:path'

const { playwright } = loadScriptDependencies(import.meta.url, ['playwright'])
const { chromium } = playwright
const { preview } = await import('vite')
const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, item, index, all) => {
    if (item.startsWith('--')) pairs.push([item.slice(2), all[index + 1]])
    return pairs
  }, []),
)
const root = process.cwd()
const tmp = resolve(root, 'tmp') + sep
const buildDir = resolve(args.build || '')
const accountsFile = resolve(args.accounts || '')
const output = resolve(args.output || '')
assert(
  [buildDir, accountsFile, output].every((path) => path.startsWith(tmp)),
  'Use explicit paths inside ignored tmp',
)
const backend = new URL(args.backend || 'http://127.0.0.1:18081')
assert(backend.origin === 'http://127.0.0.1:18081', 'Only this fresh project QA backend is allowed')
const accounts = JSON.parse(await readFile(accountsFile, 'utf8'))
assert(
  accounts.synthetic_only === true &&
    accounts.users.every((user) => user.username.startsWith('qa-')),
  'Synthetic QA accounts required',
)
await mkdir(output, { recursive: false })
const server = await preview({
  root,
  envDir: false,
  build: { outDir: buildDir },
  preview: {
    host: '127.0.0.1',
    port: 4193,
    strictPort: true,
    proxy: {
      '/api': { target: backend.origin, changeOrigin: true, ws: true },
      '/static': { target: backend.origin },
    },
  },
})
const origin = 'http://127.0.0.1:4193'
let browser
const results = []
const pageErrors = []
const apiFailures = []
const blockedExternal = []
async function check(name, page, action) {
  try {
    const detail = await action()
    await page.screenshot({
      path: resolve(output, `${name}.png`),
      fullPage: true,
      animations: 'disabled',
    })
    results.push({ name, passed: true, detail })
  } catch (error) {
    const screenshot = `${name.replace(/[^a-z0-9-]/gi, '-')}-failed.png`
    await page.screenshot({ path: resolve(output, screenshot), fullPage: true }).catch(() => {})
    results.push({ name, passed: false, error: String(error.message).slice(0, 700), screenshot })
  }
  console.log(JSON.stringify({ check: name, passed: results.at(-1).passed }))
}
async function request(page, path, method = 'GET', payload) {
  return page.evaluate(
    async ({ path, method, payload }) => {
      const response = await fetch(path, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
      })
      return { status: response.status, body: await response.json() }
    },
    { path, method, payload },
  )
}
async function login(page, username) {
  if (page.url().startsWith(origin)) {
    // This browser context contains synthetic QA identities only.
    await page.evaluate(() => {
      for (const key of ['token', 'role', 'user']) localStorage.removeItem(key)
      sessionStorage.clear()
    })
  }
  await page.goto(`${origin}/login`)
  await page.getByRole('textbox', { name: '账号', exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill(accounts.password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.waitForURL(/\/(student|teacher)\//)
}
async function beginTest(page, index) {
  await page.goto(`${origin}/student/test`)
  await page.getByRole('button', { name: '查看说明', exact: true }).nth(index).click()
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
}
async function answer(page, count, option = 0) {
  for (let i = 0; i < count; i += 1) {
    await page.getByRole('radio').nth(option).click()
    if (i < count - 1) await page.getByRole('button', { name: '下一题', exact: true }).click()
  }
}
async function layout(page) {
  await page.evaluate(
    () => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))),
  )
  const value = await page.evaluate(() => ({
    width: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    bodyText: document.body.innerText.length,
    headings: document.querySelectorAll('h1,h2').length,
    brokenImages: [...document.images].filter((img) => img.complete && img.naturalWidth === 0)
      .length,
  }))
  assert(
    value.scrollWidth <= value.width + 1,
    `Horizontal overflow ${value.scrollWidth}/${value.width}`,
  )
  assert(
    value.bodyText >= 15 && value.headings > 0 && !value.brokenImages,
    'Empty page or broken image',
  )
  return value
}
try {
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  for (const width of [1440, 390]) {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
      timezoneId: 'Asia/Shanghai',
      serviceWorkers: 'block',
    })
    await context.route('**/*', (route) => {
      const url = new URL(route.request().url())
      if (url.origin === origin || ['data:', 'blob:'].includes(url.protocol))
        return route.continue()
      blockedExternal.push({ type: route.request().resourceType() })
      return route.abort()
    })
    const page = await context.newPage()
    page.on('pageerror', (error) =>
      pageErrors.push({ width, message: error.message.slice(0, 500) }),
    )
    page.on('response', (response) => {
      if (new URL(response.url()).pathname.startsWith('/api/') && response.status() >= 500)
        apiFailures.push({
          width,
          path: new URL(response.url()).pathname,
          status: response.status(),
          injected: response.headers()['x-healthnew-qa-injection'] === 'save-failure',
        })
    })
    for (const path of ['/login', '/register', '/qa-not-found'])
      await check(`public-page-${path.slice(1)}-${width}`, page, async () => {
        await page.goto(origin + path)
        await page.waitForLoadState('networkidle')
        return layout(page)
      })
    await login(page, width === 1440 ? 'qa-student-desktop' : 'qa-student-mobile')
    await check(`assessment-normal-${width}`, page, async () => {
      await beginTest(page, 0)
      await page.getByRole('radio').first().focus()
      await page.keyboard.press('ArrowDown')
      await page.waitForFunction(
        () =>
          document.querySelectorAll('[role="radio"]')[1]?.getAttribute('aria-checked') === 'true',
      )
      await answer(page, 20)
      const saved = page.waitForResponse(
        (response) =>
          response.url().endsWith('/api/student/tests/submit') &&
          response.request().method() === 'POST',
      )
      await page.getByRole('button', { name: '提交并查看结果', exact: true }).click()
      const response = await saved
      assert(response.status() === 200)
      const result = await response.json()
      assert(result.score === 50 && result.standard_score === 62 && result.risk_level === null)
      const analyzed = page.waitForResponse((response) =>
        response.url().endsWith('/api/student/tests/ai-analyze'),
      )
      await page.getByRole('button', { name: '查看AI辅助说明', exact: true }).click()
      const explanation = await (await analyzed).json()
      assert(explanation.test_id === result.id && explanation.source === 'local_rule')
      await page.getByRole('heading', { name: '摘要', exact: true }).waitFor()
      assert((await page.locator('.ai-status').innerText()).includes('本地'))
      await layout(page)
      await page.screenshot({
        path: resolve(output, `assessment-result-${width}.png`),
        fullPage: true,
      })
      return { test_id: result.id, source: explanation.source, transport: 'real_http_no_api_mock' }
    })
    await check(`assessment-save-retry-${width}`, page, async () => {
      await beginTest(page, 1)
      await answer(page, 20)
      const ids = []
      let attempts = 0
      await page.route('**/api/student/tests/submit', async (route) => {
        ids.push(route.request().postDataJSON().submission_id)
        attempts += 1
        if (attempts === 1)
          return route.fulfill({
            status: 503,
            headers: { 'x-healthnew-qa-injection': 'save-failure' },
            contentType: 'application/json',
            body: JSON.stringify({ detail: '合成保存失败，用于恢复验证' }),
          })
        return route.continue()
      })
      await page.getByRole('button', { name: '提交并查看结果', exact: true }).click()
      await page.getByRole('button', { name: '重试保存', exact: true }).waitFor()
      assert(
        (await page.locator('.result-card').count()) === 0,
        'Failed save must not show a saved result',
      )
      const saved = page.waitForResponse(
        (response) =>
          response.url().endsWith('/api/student/tests/submit') && response.status() === 200,
      )
      await page.getByRole('button', { name: '重试保存', exact: true }).click()
      await saved
      await page.unroute('**/api/student/tests/submit')
      assert(ids.length === 2 && ids[0] === ids[1], 'Retry changed submission ID')
      return {
        failure: 'one_explicit_browser_injected_503',
        retry: 'real_http',
        stable_submission_id: true,
      }
    })
    await check(`assessment-rejects-mismatched-explanation-${width}`, page, async () => {
      await page.route('**/api/student/tests/ai-analyze', (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            test_id: 999999,
            source: 'local_rule',
            status: 'fallback',
            content: {
              summary: 'MISMATCH-SHOULD-NOT-RENDER',
              observations: [],
              limitations: [],
              next_steps: [],
            },
          }),
        }),
      )
      try {
        await page.getByRole('button', { name: '查看AI辅助说明', exact: true }).click()
        await page.locator('.ai-error[role="alert"]').waitFor()
        assert(!(await page.locator('.ai-analysis').count()), 'Mismatched explanation rendered')
        assert(
          !(await page.locator('body').innerText()).includes('MISMATCH-SHOULD-NOT-RENDER'),
          'Foreign content rendered',
        )
      } finally {
        await page.unroute('**/api/student/tests/ai-analyze')
      }
      return { failure: 'explicit_mismatched_response_injection', rejected: true }
    })
    await check(`api-permissions-and-support-${width}`, page, async () => {
      const forbidden = await request(page, '/api/teacher/students')
      assert(forbidden.status === 403)
      const otherId = width === 1440 ? 8102 : 8101
      const history = await request(page, '/api/student/tests/history')
      assert(history.status === 200)
      const wrong = await request(page, '/api/student/tests/ai-analyze', 'POST', {
        test_id: 999999,
      })
      assert(wrong.status === 404)
      const forged = await request(page, '/api/student/tests/submit', 'POST', {
        test_type: 'SDS',
        answers: {},
        score: 0,
        submission_id: 'synthetic-forgery',
      })
      assert(forged.status === 422)
      const question = await request(page, '/api/student/questions', 'POST', {
        question_text: `合成求助闭环 ${width}`,
      })
      assert(question.status === 200)
      return {
        question_id: question.body.id,
        role_rejected: true,
        foreign_identity_not_used: otherId,
        forged_score_rejected: true,
      }
    })
    const paths = [
      '/student/dashboard',
      '/student/appointments',
      '/student/test',
      '/student/report',
      '/student/advanced-chat',
      '/student/articles',
      '/student/treehole',
      '/student/questions',
      '/article/1',
    ]
    for (const path of paths)
      await check(`student-page-${path.split('/').at(-1)}-${width}`, page, async () => {
        await page.goto(origin + path)
        await page.waitForLoadState('networkidle')
        if (path.startsWith('/article/'))
          await page.getByRole('heading', { name: '合成平台使用指南', level: 1 }).waitFor()
        else await page.locator('.main-content').waitFor()
        return layout(page)
      })
    await login(page, 'qa-teacher')
    await check(`teacher-support-roundtrip-${width}`, page, async () => {
      const questions = await request(page, '/api/teacher/questions?status=pending')
      assert(questions.status === 200)
      const question = questions.body.data.find(
        (row) => row.question_text === `合成求助闭环 ${width}`,
      )
      assert(question)
      const reply = await request(page, `/api/teacher/questions/${question.id}/answer`, 'POST', {
        answer_text: `合成回复 ${width}`,
      })
      assert(reply.status === 200)
      const duplicate = await request(
        page,
        `/api/teacher/questions/${question.id}/answer`,
        'POST',
        { answer_text: '合成重复答复' },
      )
      assert(duplicate.status === 409)
      return { question_id: question.id, answered: true, repeated_write_rejected: true }
    })
    for (const path of [
      '/teacher/advanced-dashboard',
      '/teacher/support',
      '/teacher/students',
      '/teacher/appointments',
      '/teacher/content',
      '/teacher/interventions',
      '/teacher/student/8101',
    ])
      await check(`teacher-page-${path.split('/').at(-1)}-${width}`, page, async () => {
        await page.goto(origin + path)
        await page.waitForLoadState('networkidle')
        await page.locator('.main-content').waitFor()
        return layout(page)
      })
    await page.screenshot({ path: resolve(output, `teacher-detail-${width}.png`), fullPage: true })
    await context.close()
  }
} finally {
  if (browser) await browser.close()
  await new Promise((done) => server.httpServer.close(done))
  const summary = {
    synthetic_only: true,
    status:
      results.length === 48 &&
      results.every((row) => row.passed) &&
      !pageErrors.length &&
      !apiFailures.some((row) => !row.injected) &&
      !blockedExternal.length
        ? 'passed'
        : 'failed',
    results,
    pageErrors,
    apiFailures,
    blockedExternal,
    browser: 'new isolated Edge contexts',
    build: relative(root, buildDir),
  }
  await writeFile(resolve(output, 'summary.json'), JSON.stringify(summary, null, 2) + '\n')
  console.log(
    JSON.stringify({
      status: summary.status,
      checks: results.length,
      passed: results.filter((row) => row.passed).length,
      failed: results.filter((row) => !row.passed),
      pageErrors,
      apiFailures,
      blockedExternal: blockedExternal.length,
    }),
  )
  if (summary.status !== 'passed') process.exitCode = 1
}
