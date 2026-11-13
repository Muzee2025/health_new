/**
 * Behaviour lock for check-chart-data.mjs.
 *
 * The script is a top-level gate: it derives nothing from arguments, imports the
 * fixture module by a relative path, and runs on import. To prove it can still
 * fail, each case copies the script and the fixture module into a fixture tree,
 * optionally corrupts the fixture, then runs it as a child process and reads the
 * JSON report it prints last.
 *
 * The important direction is the negative one: a gate that cannot fail is worse
 * than no gate, so every invariant the script claims to check has a case here
 * that breaks it and asserts exit code 1 plus "status": "failed".
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const scripts = path.resolve(here, '..')
const repo = path.resolve(scripts, '..')
const scratch = path.join(repo, 'tmp', 'chart-data-check-fixtures')
fs.mkdirSync(scratch, { recursive: true })

function fixture(mutateFixture) {
  const root = fs.mkdtempSync(path.join(scratch, 'case-'))
  fs.mkdirSync(path.join(root, 'scripts'), { recursive: true })
  fs.mkdirSync(path.join(root, 'docs', 'design'), { recursive: true })
  fs.copyFileSync(
    path.join(scripts, 'check-chart-data.mjs'),
    path.join(root, 'scripts', 'check-chart-data.mjs'),
  )
  // chart-demo-data.js imports ../../src/styles/echarts-theme.js, so the fixture
  // needs that file too or the copy fails to resolve before any check runs.
  fs.mkdirSync(path.join(root, 'src', 'styles'), { recursive: true })
  fs.copyFileSync(
    path.join(repo, 'src', 'styles', 'echarts-theme.js'),
    path.join(root, 'src', 'styles', 'echarts-theme.js'),
  )
  const fixturePath = path.join(repo, 'docs', 'design', 'chart-demo-data.js')
  let source = fs.readFileSync(fixturePath, 'utf8')
  if (mutateFixture) source = mutateFixture(source)
  fs.writeFileSync(path.join(root, 'docs', 'design', 'chart-demo-data.js'), source)
  return root
}

/**
 * Run the copied script; returns { code, report }. A failure before the report
 * exists (an unresolved import, for example) yields report === null.
 */
function run(root) {
  let stdout
  let code = 0
  try {
    stdout = execFileSync(process.execPath, [path.join(root, 'scripts', 'check-chart-data.mjs')], {
      cwd: root,
      encoding: 'utf8',
      timeout: 60_000,
    })
  } catch (error) {
    stdout = error.stdout ?? ''
    code = error.status ?? 1
  }
  const start = stdout.lastIndexOf('\n{')
  let report
  try {
    report = JSON.parse(stdout.slice(start === -1 ? 0 : start + 1))
  } catch {
    report = null
  }
  return { code, report }
}

test('the unmodified fixture passes and reports every case', () => {
  const { code, report } = run(fixture())
  assert.equal(code, 0, JSON.stringify(report.errors))
  assert.equal(report.status, 'passed')
  assert.deepEqual(report.errors, [])
  // Two samples x three ranges.
  assert.equal(report.cases.length, 6)
  for (const entry of report.cases) {
    assert.equal(entry.passed, true)
    assert.ok(entry.heatmapCells > 0)
    assert.ok(entry.resourcePoints > 0)
  }
})

test('a broken daily total fails the gate', () => {
  // support is computed as sum(channels); break the relationship the gate asserts.
  const { code, report } = run(
    fixture((source) =>
      source.replace('const support = sum(channels);', 'const support = sum(channels) + 1;'),
    ),
  )
  assert.equal(code, 1)
  assert.equal(report.status, 'failed')
  assert.ok(report.errors.length > 0)
})

test('a non-deterministic fixture fails the gate', () => {
  // Same inputs must yield equal output. A per-call counter makes two calls with
  // identical arguments differ, which is exactly what the first assertion catches.
  const { code, report } = run(
    fixture((source) =>
      source.replace(
        'return { range:count,',
        'return { drift:(globalThis.__drift = (globalThis.__drift || 0) + 1), range:count,',
      ),
    ),
  )
  assert.equal(code, 1)
  assert.equal(report.status, 'failed')
})

test('the report is the last line and stays machine-readable', () => {
  const root = fixture()
  const stdout = execFileSync(
    process.execPath,
    [path.join(root, 'scripts', 'check-chart-data.mjs')],
    {
      cwd: root,
      encoding: 'utf8',
      timeout: 60_000,
    },
  )
  const lastLine = stdout.trimEnd().split('\n').slice(-1)[0]
  assert.equal(lastLine, '}')
  assert.doesNotThrow(() => JSON.parse(stdout.slice(stdout.lastIndexOf('\n{') + 1)))
})

test('a fixture missing the module fails instead of silently passing', () => {
  const root = fixture()
  fs.rmSync(path.join(root, 'docs', 'design', 'chart-demo-data.js'))
  const { code } = run(root)
  // An unresolved import aborts before the try block, so there is no report at
  // all; what matters is that the gate is not silently green.
  assert.equal(code, 1)
})
