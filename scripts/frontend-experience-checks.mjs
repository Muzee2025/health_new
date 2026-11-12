// Opt-in interaction checks for capture-w2-ui.mjs. All API responses are synthetic.
import assert from 'node:assert/strict'
import { resolve } from 'node:path'

export async function checkExperience({ page, routeConfig, outputDir }) {
  const results = []
  const label = `${routeConfig.name}-${routeConfig.viewport.width}`
  async function check(name, action) {
    try {
      const detail = await action()
      results.push({ name: `${label}-${name}`, passed: true, detail })
    } catch (error) {
      const screenshot = `${label}-${name}-failure.png`
      await page
        .screenshot({ path: resolve(outputDir, screenshot), animations: 'disabled' })
        .catch(() => {})
      results.push({
        name: `${label}-${name}`,
        passed: false,
        error: String(error.message).slice(0, 1200),
        screenshot,
      })
      console.log(JSON.stringify(results.at(-1)))
    }
  }
  const fulfill = (route, body, status = 200) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  async function assertDialogFits() {
    const dialog = page.getByRole('dialog').last()
    await dialog.waitFor({ state: 'visible' })
    const box = await dialog.boundingBox()
    assert(
      box && box.x >= 0 && box.x + box.width <= page.viewportSize().width + 1,
      'Dialog exceeds viewport',
    )
    return dialog
  }

  if (routeConfig.role && routeConfig.name !== 'article-safe-html') {
    await check('navigation', async () => {
      const nav = page.locator('.sidebar')
      if (routeConfig.viewport.width < 761) {
        const trigger = page.getByRole('button', { name: '导航', exact: true })
        await trigger.click()
        await page.waitForFunction(
          () => document.querySelector('.sidebar')?.contains(document.activeElement),
          null,
          { timeout: 2000 },
        )
        if (['student-dashboard', 'teacher-advanced-dashboard'].includes(routeConfig.name))
          await page.screenshot({
            path: resolve(outputDir, `${label}-navigation.png`),
            animations: 'disabled',
          })
        assert(
          await page.locator('.main-content').evaluate((el) => el.inert),
          'Background must be inert',
        )
        assert(
          await nav.evaluate((el) => el.contains(document.activeElement)),
          'Focus must enter navigation',
        )
        for (let i = 0; i < 16; i++) {
          await page.keyboard.press('Tab')
          assert(
            await nav.evaluate((el) => el.contains(document.activeElement)),
            'Tab escaped navigation',
          )
        }
        await page.keyboard.press('Shift+Tab')
        assert(
          await nav.evaluate((el) => el.contains(document.activeElement)),
          'Reverse Tab escaped navigation',
        )
        await page.keyboard.press('Escape')
        assert(
          await trigger.evaluate((el) => el === document.activeElement),
          'Close must restore trigger focus',
        )
        assert(
          !(await page.locator('.main-content').evaluate((el) => el.inert)),
          'Background remained inert',
        )
        await trigger.click()
      }
      const current = nav.locator('a[aria-current="page"]')
      assert.equal(await current.count(), 1, 'Exactly one current navigation link required')
      while (await nav.locator('button[aria-expanded="false"]').count())
        await nav.locator('button[aria-expanded="false"]').first().click()
      assert((await nav.locator('a[href]').count()) >= (routeConfig.role === 'student' ? 8 : 7))
      if (routeConfig.viewport.width < 761) {
        const target = nav.locator(
          `a[href="/${routeConfig.role}/${routeConfig.role === 'student' ? 'questions' : 'support'}"]`,
        )
        await target.click()
        await page.waitForTimeout(100)
        assert(
          !(await page.locator('.main-content').evaluate((el) => el.inert)),
          'Route change did not close navigation',
        )
        assert(!(await nav.isVisible()), 'Navigation remained visible after route change')
        await page.goto(new URL(routeConfig.path, page.url()).href)
        await page.waitForTimeout(300)
        const trigger = page.getByRole('button', { name: '导航', exact: true })
        await trigger.click()
        await page.waitForFunction(
          () => document.querySelector('.sidebar')?.contains(document.activeElement),
          null,
          { timeout: 2000 },
        )
        await nav.locator('a[aria-current="page"]').click()
        assert(
          !(await page.locator('.main-content').evaluate((el) => el.inert)),
          'Current page click must close navigation',
        )
        await trigger.click()
        await page.setViewportSize({ width: 1440, height: 900 })
        await page.waitForTimeout(100)
        assert(
          !(await page.locator('.main-content').evaluate((el) => el.inert)),
          'Desktop resize left background inert',
        )
        assert(await nav.isVisible())
        await page.setViewportSize(routeConfig.viewport)
        // A detail page highlights its list parent; restore the case after following that link.
        if (new URL(page.url()).pathname !== routeConfig.path) {
          await page.goto(new URL(routeConfig.path, page.url()).href)
          await page.waitForTimeout(300)
        }
      }
      return {
        groups: routeConfig.role === 'student' ? 6 : 5,
        keyboardTested: routeConfig.viewport.width < 761,
      }
    })
    // Recover the fixture after a failed navigation assertion so later checks remain independent.
    await page.keyboard.press('Escape')
    await page.waitForTimeout(50)
  }

  await page.setViewportSize({ width: 320, height: 844 })
  await check('320-layout', async () => {
    await page.waitForTimeout(120)
    const state = await page.evaluate(() => ({
      width: innerWidth,
      scroll: document.documentElement.scrollWidth,
    }))
    assert.equal(
      new URL(page.url()).pathname,
      routeConfig.path,
      'Layout check left the requested route',
    )
    assert(state.scroll <= state.width + 2, 'Page overflows at 320px')
    const clipped = await page.evaluate(() =>
      [
        ...document.querySelectorAll(
          '.main-content button, .main-content input, .main-content textarea',
        ),
      ]
        .filter((el) => {
          if (el.closest('.el-table, [aria-hidden="true"]')) return false
          const box = el.getBoundingClientRect()
          return (
            box.width &&
            box.height &&
            getComputedStyle(el).visibility !== 'hidden' &&
            (box.x < -2 || box.right > innerWidth + 2)
          )
        })
        .map((el) => ({
          tag: el.tagName,
          label: (
            el.getAttribute('aria-label') ||
            el.textContent ||
            el.getAttribute('placeholder') ||
            ''
          )
            .trim()
            .slice(0, 60),
        })),
    )
    assert.deepEqual(clipped, [], `Controls clipped: ${JSON.stringify(clipped)}`)
    return state
  })

  if (
    ['student-dashboard', 'teacher-advanced-dashboard', 'login', 'register'].includes(
      routeConfig.name,
    )
  ) {
    await page.screenshot({ path: resolve(outputDir, `${label}-320.png`), animations: 'disabled' })
  }

  if (['login', 'register'].includes(routeConfig.name)) {
    await check('form-required', async () => {
      const posts = []
      page.on('request', (req) => {
        if (req.method() === 'POST') posts.push(new URL(req.url()).pathname)
      })
      assert.equal(await page.locator('h1').count(), 1)
      const button = page.getByRole('button', {
        name: routeConfig.name === 'login' ? '登录' : '注册',
        exact: true,
      })
      await button.click()
      await page.waitForTimeout(150)
      assert.equal(posts.length, 0, 'Empty form sent a request')
      assert(
        await page.locator('.el-message, .el-form-item__error, .el-alert--error').count(),
        'Required field feedback missing',
      )
      if (routeConfig.name === 'register')
        assert.equal(await page.locator('fieldset legend').innerText(), '个人资料（选填）')
      return { posted: posts.length, oneMainHeading: true }
    })
  }

  if (routeConfig.name === 'article-safe-html') {
    await check('article-retry', async () => {
      let fail = true
      await page.route('**/api/student/articles/1', (route) =>
        fulfill(
          route,
          fail
            ? { detail: 'Synthetic failure' }
            : { id: 1, title: '合成恢复文章', content: '<p>恢复后的合成正文</p>', views: 0 },
          fail ? 500 : 200,
        ),
      )
      await page.reload()
      await page.getByRole('heading', { name: '文章暂时无法打开' }).waitFor()
      fail = false
      await page.getByRole('button', { name: '重新加载', exact: true }).click()
      await page.getByRole('heading', { name: '合成恢复文章' }).waitFor()
      assert(await page.getByRole('article', { name: '文章正文' }).isVisible())
      await page.screenshot({
        path: resolve(outputDir, `${label}-article-recovered.png`),
        animations: 'disabled',
      })
      return { failureStatus: 500, retryStatus: 200, bodyRestored: true }
    })
  }
  if (routeConfig.name === 'student-appointments') {
    await check('appointment-recovery-dialog', async () => {
      let fail = true
      await page.route('**/api/student/teachers', (route) =>
        fulfill(
          route,
          fail
            ? { detail: 'Synthetic failure' }
            : [
                {
                  id: 'qa-teacher',
                  name: '合成老师',
                  can_book: true,
                  time_slots: ['2026-10-29 10:00-10:50'],
                  booked_slots: [],
                },
              ],
          fail ? 500 : 200,
        ),
      )
      await page.reload()
      await page.getByRole('button', { name: '重新加载老师' }).waitFor()
      fail = false
      await page.getByRole('button', { name: '重新加载老师' }).click()
      await page.getByRole('button', { name: '2026-10-29 10:00-10:50' }).click()
      const dialog = await assertDialogFits()
      await dialog.getByRole('button', { name: '取消', exact: true }).click()
      await dialog.waitFor({ state: 'hidden' })
      return { retryStatus: 200, confirmationFits320: true, bookingCancelled: true }
    })
  }
  if (routeConfig.name === 'student-questions') {
    await check('questions-empty-focus', async () => {
      await page.route('**/api/student/questions', (route) => fulfill(route, []))
      await page.getByRole('button', { name: '刷新记录' }).click()
      await page.getByRole('button', { name: '写一条留言' }).click()
      assert(
        await page
          .locator('#student-question-text')
          .evaluate((el) => el === document.activeElement),
      )
      assert(await page.getByRole('button', { name: '提交留言' }).isDisabled())
      return { emptyActionFocusesComposer: true, blankSubmitDisabled: true }
    })
  }
  if (routeConfig.name === 'teacher-advanced-dashboard') {
    await check('review-dialog', async () => {
      await page.route('**/api/teacher/crisis/pending?*', (route) =>
        fulfill(route, {
          data: {
            items: [
              {
                id: 'qa-review',
                createdAt: '2026-10-22',
                studentName: '合成学生',
                riskLevel: 'medium',
                description: '仅界面验收，合成待办。',
                status: 'pending',
              },
            ],
          },
        }),
      )
      await page.reload()
      await page.getByRole('button', { name: '通过', exact: true }).click()
      const dialog = await assertDialogFits()
      await dialog.getByRole('button', { name: '保存审核' }).click()
      await dialog.getByText('请填写审核原因。', { exact: true }).waitFor()
      await dialog.getByRole('button', { name: '返回', exact: true }).click()
      return { requiredReasonPreserved: true, dialogFits320: true }
    })
  }
  if (routeConfig.name === 'teacher-content') {
    await check('content-dialog', async () => {
      await page.getByRole('button', { name: '新增文章', exact: true }).click()
      const dialog = await assertDialogFits()
      const textarea = dialog.locator('textarea').last()
      await textarea.fill('合成界面检查；不会提交。')
      assert.equal(await textarea.inputValue(), '合成界面检查；不会提交。')
      await dialog.getByRole('button', { name: '取消', exact: true }).click()
      return { dialogFits320: true, cancelledWithoutSubmit: true }
    })
  }
  if (
    ['teacher-students', 'teacher-appointments', 'teacher-interventions'].includes(routeConfig.name)
  ) {
    await check('many-pages', async () => {
      const kind = routeConfig.name.replace('teacher-', '')
      const rows = Array.from({ length: 120 }, (_, i) => ({
        id: 910000 + i,
        name: `合成学生${i + 1}`,
        student_name: `合成学生${i + 1}`,
        student_id: `QA-${i + 1}`,
        teacher_name: '合成老师',
        advisor: '合成老师',
        class_name: '合成班级',
        risk_level: 'green',
        time_slot: '2026-10-29 10:00-10:50',
        status: 'pending',
        record_date: '2026-10-22',
        notes: '合成多页记录，用于分页界面验收。',
      }))
      await page.route(`**/api/teacher/${kind}`, (route) => fulfill(route, rows))
      await page.reload()
      const pagination = page.locator('.el-pagination')
      await pagination.getByText(/共\s*120\s*条/).waitFor()
      await pagination.getByRole('button', { name: '下一页' }).click()
      assert.equal(await pagination.locator('.el-pager .is-active').innerText(), '2')
      const overflow = await pagination.evaluate(
        (el) =>
          [...el.querySelectorAll('button, [role="button"], .el-pagination__sizes')].filter(
            (child) => {
              const box = child.getBoundingClientRect()
              return box.width > 0 && (box.x < -2 || box.right > innerWidth + 2)
            },
          ).length,
      )
      assert.equal(overflow, 0, 'Multi-page navigation controls exceed viewport')
      await pagination.scrollIntoViewIfNeeded()
      await page.screenshot({
        path: resolve(outputDir, `${label}-many-pages-320.png`),
        animations: 'disabled',
      })
      return { records: rows.length, currentPageAfterNext: 2, controlsInViewport: true }
    })
  }
  if (routeConfig.name === 'teacher-interventions') {
    await check('date-filter-panel-320', async () => {
      await page.getByPlaceholder('开始日期', { exact: true }).click()
      const panel = page.locator('.el-date-range-picker:visible')
      await panel.waitFor({ state: 'visible' })
      const box = await panel.boundingBox()
      assert(box && box.x >= -1 && box.x + box.width <= 321, 'Date panel exceeds narrow viewport')
      const popper = page.locator('.teacher-intervention-date-popper:visible')
      const popperBox = await popper.boundingBox()
      assert(
        popperBox &&
          popperBox.y >= 0 &&
          popperBox.y + popperBox.height <= page.viewportSize().height + 1,
        'Date popover exceeds vertical viewport',
      )
      const scroll = await popper.evaluate((el) => {
        el.scrollTop = el.scrollHeight
        return { scrollTop: el.scrollTop, height: el.clientHeight, content: el.scrollHeight }
      })
      assert(
        scroll.content <= scroll.height || scroll.scrollTop > 0,
        'Lower calendar cannot be reached',
      )
      await popper.evaluate((el) => {
        el.scrollTop = 0
      })
      await page.screenshot({
        path: resolve(outputDir, `${label}-date-panel-320.png`),
        animations: 'disabled',
      })
      await page.keyboard.press('Escape')
      await panel.waitFor({ state: 'hidden' })
      return { panelFits320: true, escapeCloses: true, popoverInViewport: true, scroll }
    })
  }
  if (routeConfig.name === 'teacher-student-900001') {
    await check('detail-form-320', async () => {
      const notes = page.getByPlaceholder('添加新的干预记录...')
      await notes.scrollIntoViewIfNeeded()
      await notes.fill('合成界面检查，不提交记录。')
      const fits = await notes.evaluate((el) => {
        const box = el.getBoundingClientRect()
        return box.x >= 0 && box.right <= innerWidth + 1
      })
      assert(fits)
      await page.screenshot({
        path: resolve(outputDir, `${label}-detail-form-320.png`),
        animations: 'disabled',
      })
      await page.evaluate(() => scrollTo(0, 0))
      await page.screenshot({
        path: resolve(outputDir, `${label}-detail-header-320.png`),
        animations: 'disabled',
      })
      return { inputFits: true, saved: false }
    })
  }
  return results
}
