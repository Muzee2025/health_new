// Browser regression with synthetic identities only; no real API is contacted.
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const fs = require('fs')
const assert = require('assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright')
const base = process.env.BASELINE_BASE_URL || 'http://127.0.0.1:5173'
assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname))
;(async () => {
  let workerServer
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const results = {}
  try {
    const context = await browser.newContext({ serviceWorkers: 'block', acceptDownloads: true })
    const page = await context.newPage()
    await context.route('**/*', (route) => {
      const u = new URL(route.request().url())
      if (u.pathname.startsWith('/api/'))
        return route.fulfill({
          status: 501,
          contentType: 'application/json',
          body: '{"detail":"isolated fixture"}',
        })
      if (u.origin === base) return route.continue()
      return route.abort()
    })
    await page.goto(base + '/login')
    results.chatStorage = await page.evaluate(async () => {
      const { createPrivateChatSession } = await import('/src/services/privateChatSession.ts')
      const { createChatStorage } = await import('/src/services/chatIndexedDb.ts')
      await new Promise((resolve, reject) => {
        const request = indexedDB.open('health_new_chat_db', 1)
        request.onupgradeneeded = () => request.result.createObjectStore('legacy')
        request.onsuccess = () => {
          request.result.close()
          resolve()
        }
        request.onerror = reject
      })
      localStorage.setItem('token', 'synthetic-cache-A')
      const aSession = createPrivateChatSession('synthetic-cache-A')
      const a = createChatStorage(aSession)
      await a.upsertConversation({ id: 'same-id', title: 'private-A' })
      await a.saveUiState('same-id', { draft: 'draft-A' })
      await a.putMessage({ id: 'same-msg', conversationId: 'same-id', content: 'message-A' })
      let finish
      const pending = aSession.run(() => new Promise((resolve) => (finish = resolve)))
      localStorage.setItem('token', 'synthetic-cache-B')
      const bSession = createPrivateChatSession('synthetic-cache-B')
      const b = createChatStorage(bSession)
      const emptyB = await b.getAllConversations()
      let staleRead = false,
        staleWrite = false,
        lateRejected = false
      try {
        await a.getUiState('same-id')
      } catch {
        staleRead = true
      }
      try {
        await a.putMessage({ id: 'late', conversationId: 'same-id', content: 'late-A' })
      } catch {
        staleWrite = true
      }
      finish('late-A-result')
      try {
        await pending
      } catch {
        lateRejected = true
      }
      await b.upsertConversation({ id: 'same-id', title: 'private-B' })
      const ownB = await b.getAllConversations()
      const bMessages = await b.listMessages('same-id')
      localStorage.removeItem('token')
      let loggedOut = false
      try {
        await b.getAllConversations()
      } catch {
        loggedOut = true
      }
      const dbs = await indexedDB.databases()
      return {
        emptyB: emptyB.length === 0,
        ownB: ownB[0]?.title === 'private-B',
        bMessagesEmpty: bMessages.length === 0,
        staleRead,
        staleWrite,
        lateRejected,
        loggedOut,
        legacyRetained: dbs.some((x) => x.name === 'health_new_chat_db'),
      }
    })
    assert(Object.values(results.chatStorage).every(Boolean))
    // A stale failed request cannot clear a later login in the shared Axios interceptor.
    await page.route('**/api/synthetic-delayed-401', async (route) => {
      await new Promise((r) => setTimeout(r, 150))
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: '{"detail":"expired synthetic A"}',
      })
    })
    results.delayed401 = await page.evaluate(async () => {
      localStorage.setItem('token', 'synthetic-old-A')
      const http = document.getElementById('app').__vue_app__.config.globalProperties.$http
      const pending = http.get('/api/synthetic-delayed-401')
      await new Promise((r) => setTimeout(r, 40))
      localStorage.setItem('token', 'synthetic-new-B')
      await pending.catch(() => {})
      return localStorage.getItem('token') === 'synthetic-new-B'
    })
    assert(results.delayed401)
    await context.close()
    const docs = await browser.newContext({ serviceWorkers: 'block', acceptDownloads: true })
    await docs.addInitScript(() => {
      localStorage.setItem('token', 'synthetic-document-token')
      localStorage.setItem('role', 'student')
      localStorage.setItem('user', JSON.stringify({ id: 900001, role: 'student' }))
    })
    const docPage = await docs.newPage()
    let authorized = false
    const doc = '/api/teacher/documents/0123456789abcdef0123456789abcdef.pdf'
    await docs.route('**/*', (route) => {
      const r = route.request(),
        u = new URL(r.url())
      if (u.pathname === doc) {
        authorized = r.headers().authorization === 'Bearer synthetic-document-token'
        return route.fulfill({
          contentType: 'application/pdf',
          body: '%PDF-1.4\nsynthetic attachment only',
        })
      }
      if (u.pathname === '/api/student/articles/900001')
        return route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({
            id: 900001,
            title: '合成附件验证',
            views: 12,
            content: `<p><a href="${doc}">下载合成附件</a></p>`,
          }),
        })
      if (u.pathname.endsWith('/view'))
        return route.fulfill({ contentType: 'application/json', body: '{"views":13}' })
      if (u.origin === base && !u.pathname.startsWith('/api/')) return route.continue()
      return route.abort()
    })
    await docPage.goto(base + '/article/900001')
    const downloaded = docPage.waitForEvent('download')
    await docPage.getByText('下载合成附件', { exact: true }).click()
    const download = await downloaded
    results.document = {
      bearerSent: authorized,
      downloadFilename: download.suggestedFilename(),
      views: (await docPage.locator('.article-meta').innerText()).includes('13'),
    }
    assert(authorized)
    assert(results.document.views)
    assert(download.suggestedFilename().endsWith('.pdf'))
    await docs.close()
    // Exercise the actual worker in a separate fake-data origin with workers enabled.
    const http = require('node:http')
    const worker = fs.readFileSync('public/sw.js')
    workerServer = http.createServer((request, response) => {
      if (request.url === '/sw.js') {
        response.setHeader('Content-Type', 'application/javascript')
        response.end(worker)
        return
      }
      if (request.url === '/api/student/report/analysis') {
        response.setHeader('Content-Type', 'application/json')
        response.setHeader('Cache-Control', 'no-store')
        response.end(JSON.stringify({ identity: request.headers.authorization || 'none' }))
        return
      }
      response.setHeader('Content-Type', 'text/html')
      response.end('<title>Synthetic service worker fixture</title>')
    })
    await new Promise((resolve) => workerServer.listen(0, '127.0.0.1', resolve))
    const workerContext = await browser.newContext()
    const workerPage = await workerContext.newPage()
    await workerPage.goto('http://127.0.0.1:' + workerServer.address().port)
    await workerPage.evaluate(async () => {
      await (
        await caches.open('report-api-cache-v1')
      ).put('/api/student/report/analysis', new Response('synthetic-private-A'))
      await (await caches.open('unrelated-retained')).put('/other', new Response('keep'))
      await navigator.serviceWorker.register('/sw.js')
      await navigator.serviceWorker.ready
    })
    await workerPage.waitForFunction(() => !!navigator.serviceWorker.controller)
    const workerResult = await workerPage.evaluate(async () => {
      const a = await (
        await fetch('/api/student/report/analysis', { headers: { Authorization: 'synthetic-A' } })
      ).json()
      const b = await (
        await fetch('/api/student/report/analysis', { headers: { Authorization: 'synthetic-B' } })
      ).json()
      return {
        controlled: !!navigator.serviceWorker.controller,
        cacheNames: await caches.keys(),
        a: a.identity,
        b: b.identity,
      }
    })
    await workerContext.setOffline(true)
    workerResult.offlineFailed = await workerPage.evaluate(async () => {
      try {
        await fetch('/api/student/report/analysis')
        return false
      } catch {
        return true
      }
    })
    assert(
      workerResult.controlled &&
        workerResult.a === 'synthetic-A' &&
        workerResult.b === 'synthetic-B' &&
        workerResult.offlineFailed,
    )
    assert(
      !workerResult.cacheNames.includes('report-api-cache-v1') &&
        workerResult.cacheNames.includes('unrelated-retained'),
    )
    results.serviceWorker = workerResult
    await workerContext.close()
    const output = process.env.W2_CLIENT_QA_OUTPUT || 'tmp/w2-client-qa.json'
    fs.mkdirSync(require('node:path').dirname(output), { recursive: true })
    fs.writeFileSync(output, JSON.stringify(results, null, 2))
    console.log(JSON.stringify(results, null, 2))
  } finally {
    await browser.close()
    if (workerServer?.listening) await new Promise((resolve) => workerServer.close(resolve))
  }
})().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
