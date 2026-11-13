import assert from 'node:assert/strict'
import { loadScriptDependencies } from './optional-script-dependencies.mjs'
import { dirname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdir, writeFile } from 'node:fs/promises'

const { playwright } = loadScriptDependencies(import.meta.url, ['playwright'])
const { chromium } = playwright
const scriptDir = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(scriptDir, '..')
const baseUrl = process.env.CONTENT_BASE_URL || 'http://127.0.0.1:4198'
const outputDir = resolve(
  repoRoot,
  process.env.CONTENT_QA_OUTPUT || 'tmp/content-quality-20261024/ui',
)
const baseOrigin = new URL(baseUrl).origin
assert.equal(new URL(baseUrl).hostname, '127.0.0.1', 'Use only an isolated loopback preview')
assert.equal(new URL(baseUrl).protocol, 'http:')
assert(
  outputDir.startsWith(resolve(repoRoot, 'tmp') + sep),
  'Evidence must stay inside ignored tmp',
)
const viewports = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]
const fakeToken = 'synthetic-content-quality-token-only'
const syntheticStudent = { id: 'qa-student-content-001', name: '合成学生', role: 'student' }
const syntheticTeacher = { id: 'qa-teacher-content-001', name: '合成教师', role: 'teacher' }
const categories = ['情绪管理', '睡眠健康', '人际关系']
const longTitle = `给忙碌的日常留出一点温柔的空间：${'从一个小小的呼吸练习开始，慢慢找回自己的节奏'.repeat(3)}`
const pad = (value) => String(value).padStart(3, '0')

function makeArticles() {
  return Array.from({ length: 26 }, (_, index) => {
    const id = index + 1
    return {
      id,
      title: id === 2 ? longTitle : `标题线索-${pad(id)} · 心理科普文章 ${id}`,
      summary: `摘要线索-${pad(id)}：从日常练习、休息与交流中照顾自己。`,
      category: categories[index % categories.length],
      source: `来源线索-${pad(id)}`,
      cover_url: null,
      views: id === 1 ? 0 : id === 26 ? 250 : (id * 13) % 71,
      ...(id === 3 ? {} : { created_at: new Date(Date.UTC(2026, 9, id, 8)).toISOString() }),
      content: `合成正文 ${id}`,
    }
  }).sort((a, b) => (Date.parse(b.created_at || '') || 0) - (Date.parse(a.created_at || '') || 0))
}

const json = (route, payload, status = 200) =>
  route.fulfill({
    status,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(payload),
  })

function safeName(value) {
  return (
    value
      .toLocaleLowerCase()
      .replace(/[^a-z0-9\u3400-\u9fff]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 64) || 'scenario'
  )
}

async function main() {
  await mkdir(outputDir, { recursive: true })
  const results = []
  const runErrors = []
  let browser

  try {
    browser = await chromium.launch({ headless: true, channel: 'msedge' })
    for (const role of ['student', 'teacher']) {
      for (const viewport of viewports) {
        const context = await browser.newContext({
          viewport,
          serviceWorkers: 'block',
          locale: 'zh-CN',
          timezoneId: 'Asia/Shanghai',
          colorScheme: 'light',
          reducedMotion: 'reduce',
        })
        await context.addInitScript(
          ({ user, roleValue, token }) => {
            localStorage.clear()
            localStorage.setItem('token', token)
            localStorage.setItem('role', roleValue)
            localStorage.setItem('user', JSON.stringify(user))
          },
          {
            user: role === 'student' ? syntheticStudent : syntheticTeacher,
            roleValue: role,
            token: fakeToken,
          },
        )

        const page = await context.newPage()
        page.setDefaultTimeout(7000)
        const articles = makeArticles()
        const apiCalls = []
        const unmappedApiCalls = []
        const externalRequests = []
        const consoleEvents = []
        const pageErrors = []
        const blockedSockets = []
        const postPayloads = []
        const deleteIds = []
        let createMode = 'fail'
        let failNextCatalog = false
        let failedCatalogRequests = 0
        let nextId = 27
        const expectedConsole = (entry) => entry.expected === true

        page.on('console', (message) => {
          if (message.type() === 'error' || message.type() === 'warning') {
            const text = message.text().slice(0, 500)
            consoleEvents.push({
              type: message.type(),
              text,
              expected:
                ((createMode === 'fail' && postPayloads.length > 0) || failedCatalogRequests > 0) &&
                /^Failed to load resource:.*500/.test(text),
            })
          }
        })
        page.on('pageerror', (error) =>
          pageErrors.push(String(error?.message || error).slice(0, 500)),
        )
        await page.routeWebSocket('**/*', (socket) => {
          blockedSockets.push('websocket-intercepted')
          socket.onMessage(() => {})
        })

        await context.route('**/*', async (route) => {
          const request = route.request()
          let url
          try {
            url = new URL(request.url())
          } catch {
            externalRequests.push({ url: request.url(), reason: 'invalid-url' })
            return route.abort('blockedbyclient')
          }
          if (url.origin !== baseOrigin) {
            externalRequests.push({
              origin: url.origin,
              path: url.pathname,
              method: request.method(),
            })
            return route.abort('blockedbyclient')
          }
          if (url.pathname.startsWith('/api/')) {
            const method = request.method()
            const path = url.pathname
            const apiCall = { method, path, query: Object.fromEntries(url.searchParams) }
            apiCalls.push(apiCall)

            if (/^\/api\/(student|teacher)\/articles\/page$/.test(path) && method === 'GET') {
              if (failNextCatalog) {
                failNextCatalog = false
                failedCatalogRequests++
                apiCall.expectedFailure = true
                return json(route, { detail: 'Synthetic catalog failure' }, 500)
              }
              const q = (url.searchParams.get('q') || '').trim().toLocaleLowerCase()
              const category = url.searchParams.get('category') || ''
              const pageSize = Number(url.searchParams.get('page_size'))
              assert.equal(pageSize, 12, 'The client must request a bounded page')
              const matches = articles.filter(
                (article) =>
                  (!category || article.category === category) &&
                  (!q ||
                    [article.title, article.summary, article.source].some((value) =>
                      String(value || '')
                        .toLocaleLowerCase()
                        .includes(q),
                    )),
              )
              matches.sort(
                (a, b) =>
                  (url.searchParams.get('sort') === 'most-read'
                    ? (b.views || 0) - (a.views || 0)
                    : 0) ||
                  (Date.parse(b.created_at || '') || 0) - (Date.parse(a.created_at || '') || 0) ||
                  b.id - a.id,
              )
              const effectivePage = Math.max(
                1,
                Math.min(
                  Number(url.searchParams.get('page')) || 1,
                  Math.ceil(matches.length / pageSize) || 1,
                ),
              )
              const items = matches
                .slice((effectivePage - 1) * pageSize, effectivePage * pageSize)
                .map(({ content, ...summary }) => summary)
              apiCall.returnedItems = items.length
              apiCall.bodyIncluded = items.some((item) => 'content' in item)
              return json(route, {
                items,
                total: matches.length,
                page: effectivePage,
                page_size: pageSize,
                categories: [
                  ...new Set(articles.map((article) => article.category).filter(Boolean)),
                ],
              })
            }
            const detailMatch = path.match(/^\/api\/student\/articles\/(\d+)$/)
            if (detailMatch && method === 'GET') {
              const article = articles.find((item) => item.id === Number(detailMatch[1]))
              if (!article) return json(route, { detail: 'Synthetic article missing' }, 404)
              return json(route, {
                ...article,
                content: `第一行：给日常留一点空隙。\n第二行：可以慢慢来。<script>window.__contentXss = true</script>`,
              })
            }
            if (/^\/api\/student\/articles\/\d+\/view$/.test(path) && method === 'POST') {
              const id = Number(path.split('/')[4])
              const article = articles.find((item) => item.id === id)
              if (article) article.views = Math.max(0, Number(article.views) || 0) + 1
              return json(route, {
                article_id: id,
                views: article?.views ?? 1,
                counted: true,
                dedup_window_seconds: 300,
              })
            }
            if (path === '/api/teacher/teachers_profiles' && method === 'GET')
              return json(route, [])
            if (path === '/api/teacher/students' && method === 'GET') return json(route, [])
            if (path === '/api/teacher/articles' && method === 'POST') {
              let payload = {}
              try {
                payload = request.postDataJSON() || {}
              } catch {}
              postPayloads.push(payload)
              if (createMode === 'fail')
                return json(route, { detail: 'Synthetic create failure' }, 500)
              await new Promise((resolvePromise) => setTimeout(resolvePromise, 500))
              const created = {
                id: nextId++,
                ...payload,
                views: 0,
                created_at: '2026-10-28T08:00:00.000Z',
              }
              articles.unshift(created)
              return json(route, created, 200)
            }
            const deleteMatch = path.match(/^\/api\/teacher\/articles\/(\d+)$/)
            if (deleteMatch && method === 'DELETE') {
              const id = Number(deleteMatch[1])
              deleteIds.push(id)
              const index = articles.findIndex((item) => item.id === id)
              if (index >= 0) articles.splice(index, 1)
              return json(route, { message: 'Deleted' })
            }

            unmappedApiCalls.push({ method, path })
            return json(route, { detail: 'Unexpected synthetic API' }, 501)
          }
          return route.continue()
        })

        const viewportKey = `${viewport.width}x${viewport.height}`
        const scenario = async (name, action) => {
          const before = {
            console: consoleEvents.length,
            pageErrors: pageErrors.length,
            external: externalRequests.length,
            api: apiCalls.length,
          }
          let passed = true
          let details = {}
          let error = null
          try {
            details = await action()
          } catch (caught) {
            passed = false
            error = String(caught?.stack || caught).slice(0, 1400)
          }
          let layout = null
          try {
            layout = await page.evaluate(() => ({
              viewportWidth: innerWidth,
              documentWidth: document.documentElement.scrollWidth,
              bodyWidth: document.body.scrollWidth,
              horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 2,
            }))
            if (layout.horizontalOverflow) {
              passed = false
              error = [error, 'Document has horizontal overflow'].filter(Boolean).join('\n')
            }
          } catch (caught) {
            passed = false
            error = [error, `Could not inspect layout: ${caught.message}`]
              .filter(Boolean)
              .join('\n')
          }
          const consoleDelta = consoleEvents.slice(before.console)
          const pageErrorDelta = pageErrors.slice(before.pageErrors)
          const externalDelta = externalRequests.slice(before.external)
          if (
            pageErrorDelta.length ||
            consoleDelta.some((item) => item.type === 'error' && !expectedConsole(item)) ||
            externalDelta.length
          )
            passed = false

          const screenshot = `${role}-${viewportKey}-${String(results.length + 1).padStart(2, '0')}-${safeName(name)}.png`
          let screenshotError = null
          try {
            await page.screenshot({
              path: resolve(outputDir, screenshot),
              animations: 'disabled',
              caret: 'hide',
              fullPage: false,
            })
          } catch (caught) {
            screenshotError = String(caught?.message || caught)
            passed = false
          }

          results.push({
            role,
            viewport,
            name,
            passed,
            details,
            error,
            layout,
            console: consoleDelta,
            pageErrors: pageErrorDelta,
            externalRequests: externalDelta,
            apiCalls: apiCalls.slice(before.api),
            screenshot: screenshotError ? null : screenshot,
            screenshotError,
          })
        }

        const open = async (path) => {
          await page.goto(`${baseUrl}${path}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
          await page.waitForLoadState('load', { timeout: 10000 }).catch(() => {})
        }

        // Wait for Vue's rendered result as well as the asynchronous page response.
        const waitCatalog = async () => {
          if (role === 'student') {
            await page.locator('.article-loading').waitFor({ state: 'hidden' })
          } else {
            await page
              .locator('.el-tab-pane')
              .first()
              .locator('.el-loading-mask')
              .waitFor({ state: 'hidden' })
          }
        }
        const catalogAction = async (action) => {
          const response = page.waitForResponse(
            (value) =>
              new URL(value.url()).pathname === `/api/${role}/articles/page` &&
              value.request().method() === 'GET',
          )
          await action()
          await response
          await waitCatalog()
        }
        const fillSearch = async (value) => {
          const search = page.getByLabel('搜索文章标题、摘要或来源')
          if ((await search.inputValue()) !== value) await catalogAction(() => search.fill(value))
        }
        const checkCatalogRecovery = async (entries) => {
          failNextCatalog = true
          await fillSearch('绝无匹配结果-retry-qa')
          await page.getByRole('alert').waitFor({ state: 'visible' })
          assert.equal(await entries.count(), 0, 'No stale rows after a failed request')
          assert.equal(await page.locator('.el-pagination:visible').count(), 0)
          await catalogAction(() =>
            page.getByRole('button', { name: '重新加载', exact: true }).click(),
          )
          assert.equal(await page.getByRole('alert').count(), 0)
          assert.equal(
            await page.getByLabel('搜索文章标题、摘要或来源').inputValue(),
            '绝无匹配结果-retry-qa',
          )
          assert.equal(await entries.count(), 0)
          await page
            .getByText(role === 'student' ? '没有找到符合条件的文章' : '没有符合条件的文章。', {
              exact: true,
            })
            .waitFor()
          await fillSearch('')
          assert.equal(await entries.count(), 12)
          return {
            staleRowsHidden: true,
            retryKeepsQuery: true,
            emptyResultIsNotAnEmptyDatabase: true,
            restoredRows: 12,
          }
        }

        try {
          if (role === 'student') {
            await open('/student/articles')
            const cards = page.locator('.article-card')
            await cards.first().waitFor({ state: 'visible', timeout: 15000 })

            await scenario('article-list-12-and-pagination', async () => {
              assert.equal(await cards.count(), 12)
              assert(
                (await page.locator('.header-wrapper').boundingBox()).y >= -2,
                'Pagination must return to list controls',
              )
              const totalText = await page.locator('.el-pagination__total').innerText()
              assert.match(totalText, /26/)
              await catalogAction(() => page.locator('.el-pagination .btn-next').click())
              await page
                .locator('.el-pagination .el-pager .is-active')
                .filter({ hasText: '2' })
                .waitFor()
              assert.equal(await cards.count(), 12)
              assert(
                (await page.locator('.header-wrapper').boundingBox()).y >= -2,
                'Pagination must return to list controls',
              )
              return { initialCardsPerPage: 12, total: 26, nextPage: 2 }
            })

            const search = page.getByLabel('搜索文章标题、摘要或来源')
            await scenario('catalog-error-and-retry-retains-query', () =>
              checkCatalogRecovery(cards),
            )
            await scenario('search-title-summary-source', async () => {
              await fillSearch('标题线索-007')
              assert.equal(await cards.count(), 1)
              assert.match(await cards.first().innerText(), /标题线索-007/)
              await fillSearch('摘要线索-011')
              assert.equal(await cards.count(), 1)
              assert.match(await cards.first().innerText(), /摘要线索-011/)
              await fillSearch('来源线索-020')
              assert.equal(await cards.count(), 1)
              assert.match(await cards.first().innerText(), /来源线索-020/)
              return { fields: ['title', 'summary', 'source'], eachReturnedOneMatch: true }
            })

            await scenario('category-and-search-combination', async () => {
              await fillSearch('摘要线索-007')
              await catalogAction(() =>
                page
                  .locator('.category-filter .el-radio-button')
                  .filter({ hasText: '情绪管理' })
                  .click(),
              )
              assert.equal(await cards.count(), 1)
              assert.match(await cards.first().innerText(), /摘要线索-007/)
              return { category: '情绪管理', searchField: 'summary', matches: 1 }
            })

            await scenario('most-read-sort-and-zero-views', async () => {
              await fillSearch('')
              await catalogAction(() =>
                page
                  .locator('.category-filter .el-radio-button')
                  .filter({ hasText: '全部' })
                  .click(),
              )
              await page.locator('.article-filters .el-select').click()
              await catalogAction(() => page.getByRole('option', { name: '阅读最多' }).click())
              assert.match(await cards.first().innerText(), /标题线索-026/)
              await fillSearch('标题线索-001')
              assert.equal(await cards.count(), 1)
              assert.match(await cards.first().locator('.views').innerText(), /0/)
              return { topArticle: 26, zeroViewDisplayed: true }
            })

            await scenario('long-title-and-empty-date-fixtures', async () => {
              await fillSearch('给忙碌的日常')
              assert.equal(await cards.count(), 1)
              const lineClamp = await cards
                .first()
                .locator('.article-title')
                .evaluate((element) => getComputedStyle(element).webkitLineClamp)
              assert.equal(lineClamp, '2')
              return {
                longTitleMatched: true,
                webkitLineClamp: lineClamp,
                missingDateFixtureArticleId: 3,
              }
            })

            await scenario('no-match-clear-filters-and-reader-back', async () => {
              await fillSearch('绝无匹配结果-qa')
              await page
                .getByText('没有找到符合条件的文章', { exact: true })
                .waitFor({ state: 'visible' })
              await catalogAction(() => page.getByRole('button', { name: '清空筛选' }).click())
              assert.equal(await cards.count(), 12)
              assert.equal(await search.inputValue(), '')

              await fillSearch('标题线索-003')
              assert.equal(await cards.count(), 1)
              await cards.first().click()
              await page.waitForURL(/\/article\/3$/)
              const body = page.getByRole('article', { name: '文章正文' })
              await body.waitFor({ state: 'visible' })
              const detail = await body.evaluate((element) => ({
                text: element.innerText,
                whiteSpace: getComputedStyle(element).whiteSpace,
                scripts: element.querySelectorAll('script').length,
                xss: Boolean(window.__contentXss),
              }))
              assert.equal(detail.whiteSpace, 'pre-line')
              assert.match(detail.text, /第一行：给日常留一点空隙。\n第二行：可以慢慢来。/)
              assert.equal(detail.scripts, 0)
              assert.equal(detail.xss, false)
              assert.match(await page.locator('.article-meta').innerText(), /发布时间：未提供/)
              const detailShot = `${role}-${viewportKey}-article-detail.png`
              await page.screenshot({
                path: resolve(outputDir, detailShot),
                animations: 'disabled',
                caret: 'hide',
              })
              await page.locator('.el-page-header__back').focus()
              await page.keyboard.press('Enter')
              await page.waitForURL(/\/student\/articles$/)
              await cards.first().waitFor({ state: 'visible' })
              return {
                emptyResultCleared: true,
                detail,
                missingDateRendered: true,
                returnedToList: true,
                detailScreenshot: detailShot,
              }
            })
          } else {
            await open('/teacher/content')
            const rows = page.locator('.el-table__body tbody tr')
            await rows.first().waitFor({ state: 'visible', timeout: 15000 })

            await scenario('teacher-list-12-and-pagination', async () => {
              assert.equal(await rows.count(), 12)
              assert.match(await page.locator('.el-pagination__total').innerText(), /26/)
              await catalogAction(() => page.locator('.el-pagination .btn-next').click())
              await page
                .locator('.el-pagination .el-pager .is-active')
                .filter({ hasText: '2' })
                .waitFor()
              assert.equal(await rows.count(), 12)
              return { initialRowsPerPage: 12, total: 26, nextPage: 2 }
            })

            await scenario('catalog-error-and-retry-retains-query', () =>
              checkCatalogRecovery(rows),
            )
            await scenario('teacher-search-and-category', async () => {
              await fillSearch('标题线索-008')
              assert.equal(await rows.count(), 1)
              assert.match(await rows.first().innerText(), /标题线索-008/)
              await fillSearch('摘要线索-007')
              await page.locator('.article-toolbar .el-select').click()
              await catalogAction(() => page.getByRole('option', { name: '情绪管理' }).click())
              assert.equal(await rows.count(), 1)
              assert.match(await rows.first().innerText(), /标题线索-007/)
              await fillSearch('')
              await page.locator('.article-toolbar .el-select').click()
              await catalogAction(() => page.getByRole('option', { name: '全部分类' }).click())
              return { titleSearchMatched: true, categoryAndSearchMatched: true }
            })

            await scenario('teacher-reader-entry', async () => {
              const waitForDetail = page.waitForURL(/\/article\/\d+$/)
              await rows.first().getByRole('button', { name: '阅读' }).click()
              await waitForDetail
              const body = page.getByRole('article', { name: '文章正文' })
              await body.waitFor({ state: 'visible' })
              assert.equal(
                await body.evaluate((element) => getComputedStyle(element).whiteSpace),
                'pre-line',
              )
              await page.locator('.el-page-header__back').click()
              await page.waitForURL(/\/teacher\/content$/)
              return { openedArticleDetail: true, returnedToManagement: true }
            })

            await scenario('blank-article-fields-do-not-post', async () => {
              await page.getByRole('button', { name: '新增文章', exact: true }).click()
              const dialog = page.getByRole('dialog')
              const inputs = dialog.locator('input')
              const textareas = dialog.locator('textarea')
              assert.equal(await textareas.nth(1).getAttribute('maxlength'), '100000')
              const before = postPayloads.length
              await inputs.nth(0).fill('   ')
              await textareas.nth(1).fill('   ')
              await dialog.getByRole('button', { name: '保存', exact: true }).click()
              await page.getByText('标题和正文必填', { exact: true }).waitFor({ state: 'visible' })
              await page.waitForTimeout(120)
              assert.equal(postPayloads.length, before)
              assert.equal(await dialog.isVisible(), true)
              await dialog.getByRole('button', { name: '取消', exact: true }).click()
              return { whitespaceTitleAndBodyRejected: true, postCount: 0 }
            })

            await scenario('failed-create-keeps-form', async () => {
              createMode = 'fail'
              await page.getByRole('button', { name: '新增文章', exact: true }).click()
              const dialog = page.getByRole('dialog')
              const inputs = dialog.locator('input')
              const textareas = dialog.locator('textarea')
              await inputs.nth(0).fill('失败后保留的标题')
              await textareas.nth(1).fill('失败后保留的正文')
              await dialog.getByRole('button', { name: '保存', exact: true }).click()
              await page.getByText('保存失败', { exact: true }).waitFor({ state: 'visible' })
              assert.equal(await dialog.isVisible(), true)
              assert.equal(await inputs.nth(0).inputValue(), '失败后保留的标题')
              assert.equal(await textareas.nth(1).inputValue(), '失败后保留的正文')
              await dialog.getByRole('button', { name: '取消', exact: true }).click()
              return { failureShown: true, dialogAndValuesPreserved: true }
            })

            await scenario('delayed-create-trims-and-prevents-double-submit', async () => {
              createMode = 'success'
              await page.getByRole('button', { name: '新增文章', exact: true }).click()
              const dialog = page.getByRole('dialog')
              const inputs = dialog.locator('input')
              const textareas = dialog.locator('textarea')
              await inputs.nth(0).fill('  新增验收文章  ')
              await inputs.nth(1).fill('  情绪管理  ')
              await inputs.nth(2).fill('  合成来源  ')
              await textareas.nth(0).fill('  带首尾空白的摘要  ')
              await textareas.nth(1).fill('  正文保留边界空格  ')
              const countBefore = postPayloads.length
              const postResponse = page.waitForResponse(
                (response) =>
                  response.url().includes('/api/teacher/articles') &&
                  response.request().method() === 'POST',
              )
              const saveButton = dialog.getByRole('button', { name: '保存', exact: true })
              await saveButton.click()
              await page.waitForTimeout(80)
              assert.equal(await saveButton.isDisabled(), true)
              assert.equal(postPayloads.length, countBefore + 1)
              assert.equal(await dialog.locator('.el-dialog__headerbtn').count(), 0)
              const response = await postResponse
              assert.equal(response.status(), 200)
              await dialog.waitFor({ state: 'hidden' })
              const payload = postPayloads.at(-1)
              assert.equal(payload.title, '新增验收文章')
              assert.equal(payload.content, '正文保留边界空格')
              assert.equal(payload.summary, '带首尾空白的摘要')
              assert.equal(payload.category, '情绪管理')
              assert.equal(payload.source, '合成来源')
              await page.waitForFunction(() =>
                document.querySelector('.el-pagination__total')?.textContent?.includes('27'),
              )
              return {
                onePostDuringDelayedSave: postPayloads.length === countBefore + 1,
                fieldsTrimmed: true,
                totalAfterCreate: 27,
              }
            })

            await scenario('delete-cancel-and-confirm-page-clamp', async () => {
              await catalogAction(() =>
                page.locator('.el-pagination .el-pager .number').last().click(),
              )
              await page
                .locator('.el-pagination .el-pager .is-active')
                .filter({ hasText: '3' })
                .waitFor()
              assert.equal(await rows.count(), 3)
              const deleteCountBeforeCancel = deleteIds.length
              await rows.first().getByRole('button', { name: '删除' }).click()
              const cancelDialog = page.locator('.el-message-box')
              await cancelDialog.waitFor({ state: 'visible' })
              await cancelDialog.getByRole('button', { name: '取消', exact: true }).click()
              await cancelDialog.waitFor({ state: 'hidden' })
              assert.equal(deleteIds.length, deleteCountBeforeCancel)

              const deleteOne = async () => {
                const deletion = page.waitForResponse(
                  (response) =>
                    response.url().match(/\/api\/teacher\/articles\/\d+$/) &&
                    response.request().method() === 'DELETE',
                )
                const refreshed = page.waitForResponse(
                  (response) =>
                    new URL(response.url()).pathname === '/api/teacher/articles/page' &&
                    response.request().method() === 'GET',
                )
                await rows.first().getByRole('button', { name: '删除' }).click()
                const confirmDialog = page.locator('.el-message-box')
                await confirmDialog.waitFor({ state: 'visible' })
                await confirmDialog.getByRole('button', { name: '确定', exact: true }).click()
                await Promise.all([deletion, refreshed])
                await waitCatalog()
              }
              await deleteOne()
              await deleteOne()
              await deleteOne()
              await page.waitForFunction(() =>
                document.querySelector('.el-pagination__total')?.textContent?.includes('24'),
              )
              assert.match(
                await page.locator('.el-pagination .el-pager .is-active').innerText(),
                /2/,
              )
              assert.equal(await rows.count(), 12)
              return {
                cancelledWithoutRequest: true,
                confirmedDeletes: 3,
                totalAfterDelete: 24,
                clampedPage: 2,
              }
            })
          }
        } catch (error) {
          runErrors.push({ role, viewport, error: String(error?.stack || error).slice(0, 1800) })
        } finally {
          const pageConsole = consoleEvents.filter(
            (entry) => entry.type === 'error' && !expectedConsole(entry),
          ).length
          const pageErrorCount = pageErrors.length
          const externalCount = externalRequests.length
          results.push({
            role,
            viewport,
            name: 'context-summary',
            passed:
              pageConsole === 0 &&
              pageErrorCount === 0 &&
              externalCount === 0 &&
              unmappedApiCalls.length === 0 &&
              apiCalls
                .filter(
                  (call) =>
                    call.method === 'GET' &&
                    /\/articles\/page$/.test(call.path) &&
                    !call.expectedFailure,
                )
                .every((call) => call.returnedItems <= 12 && call.bodyIncluded === false),
            counts: {
              consoleErrors: pageConsole,
              pageErrors: pageErrorCount,
              blockedExternalRequests: externalCount,
              apiCalls: apiCalls.length,
              unmappedApiCalls,
              blockedWebSockets: blockedSockets.length,
            },
          })
          await context.close()
        }
      }
    }
  } catch (error) {
    runErrors.push({
      role: null,
      viewport: null,
      error: String(error?.stack || error).slice(0, 1800),
    })
  } finally {
    await browser?.close().catch(() => {})
  }

  const manifest = {
    schemaVersion: 1,
    task: 'OPT-FE-QA',
    status:
      runErrors.length || results.some((result) => result.passed === false)
        ? 'failed-or-blocked'
        : 'synthetic-ui-check-complete',
    generatedAt: new Date().toISOString(),
    app: baseUrl,
    fixture: {
      kind: 'synthetic-only',
      articleCount: 26,
      categories,
      includesLongTitle: true,
      includesZeroViews: true,
      includesMissingCreatedAt: true,
    },
    browser: { engine: 'Chromium', channel: 'msedge', headless: true },
    viewports,
    outputDir,
    interactions: results,
    errors: runErrors,
    totals: {
      scenarios: results.filter((result) => result.name !== 'context-summary').length,
      failedScenarios: results.filter(
        (result) => result.name !== 'context-summary' && !result.passed,
      ).length,
      contexts: results.filter((result) => result.name === 'context-summary').length,
      failedContexts: results.filter(
        (result) => result.name === 'context-summary' && !result.passed,
      ).length,
      screenshots: results.filter((result) => Boolean(result.screenshot)).length,
      externalRequests: results.reduce(
        (sum, result) => sum + (result.counts?.blockedExternalRequests || 0),
        0,
      ),
      pageErrors: results.reduce((sum, result) => sum + (result.counts?.pageErrors || 0), 0),
      consoleErrors: results.reduce((sum, result) => sum + (result.counts?.consoleErrors || 0), 0),
    },
    limitations: [
      '所有数据均由浏览器路由fixture合成；未连接数据库、真实账号或生产服务。',
      '脚本只验证浏览器交互，不构成持久化或真实业务闭环证明。',
    ],
  }
  await writeFile(resolve(outputDir, 'qa.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
  console.log(
    JSON.stringify(
      { outputDir, status: manifest.status, totals: manifest.totals, errors: runErrors },
      null,
      2,
    ),
  )
  if (
    runErrors.length ||
    manifest.totals.failedScenarios ||
    manifest.totals.failedContexts ||
    manifest.totals.externalRequests ||
    manifest.totals.pageErrors ||
    manifest.totals.consoleErrors
  )
    process.exitCode = 1
}

main().catch(async (error) => {
  await mkdir(outputDir, { recursive: true }).catch(() => {})
  const failure = {
    schemaVersion: 1,
    task: 'OPT-FE-QA',
    status: 'failed-or-blocked',
    generatedAt: new Date().toISOString(),
    app: baseUrl,
    outputDir,
    error: String(error?.stack || error),
    limitations: ['No real database, account, or production service was used.'],
  }
  await writeFile(
    resolve(outputDir, 'qa.json'),
    `${JSON.stringify(failure, null, 2)}\n`,
    'utf8',
  ).catch(() => {})
  console.error(failure.error)
  process.exitCode = 1
})
