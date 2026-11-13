// Execute copied CLI scripts only, never import the production capture entry points.
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { tmpdir } from 'node:os'
import { spawnSync } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'

const scriptsRoot = fileURLToPath(new URL('../', import.meta.url))
const scratch = fileURLToPath(new URL('../../tmp/script-dependency-tests/', import.meta.url))
fs.mkdirSync(scratch, { recursive: true })
const helper = 'optional-script-dependencies.mjs'
const browserStub = `module.exports = {
  marker: 'fixture-playwright',
  chromium: { launch() { throw new Error('Browser launch must not run during preflight') } }
}`
const sharpStub = `module.exports = function () {
  throw new Error('Image processing must not run during preflight')
}`
const browserScripts = [
  ['capture-attachment-ui.mjs', ['playwright']],
  ['capture-ui-baseline.mjs', ['playwright', 'sharp']],
  ['capture-w2-ui.mjs', ['playwright', 'sharp']],
  ['check-chart-gallery.mjs', ['playwright', 'sharp']],
  ['check-client-isolation.mjs', ['playwright']],
  ['check-content-experience.mjs', ['playwright']],
  ['check-frontend-loading.mjs', ['playwright']],
  ['export-application-diagrams.mjs', ['playwright', 'sharp']],
  ['verify-interface-ai.mjs', ['playwright']],
]

function fixture() {
  const root = fs.mkdtempSync(path.join(scratch, 'case-'))
  const write = (name, bytes) => {
    const target = path.join(root, name)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.writeFileSync(target, bytes)
    return target
  }
  write('package.json', '{"type":"module"}')
  write(`scripts/${helper}`, fs.readFileSync(path.join(scriptsRoot, helper)))
  const playwrightPath = write('modules/playwright.cjs', browserStub)
  const sharpPath = write('modules/sharp.cjs', sharpStub)
  return { root, write, playwrightPath, sharpPath }
}

function run(f, script = 'probe.mjs', args = [], overrides = {}) {
  const env = { ...process.env }
  for (const key of [
    'PLAYWRIGHT_MODULE_PATH',
    'SHARP_MODULE_PATH',
    'CODEX_PLAYWRIGHT_PATH',
    'NODE_PATH',
    'NODE_OPTIONS',
  ])
    delete env[key]
  return spawnSync(process.execPath, [path.join(f.root, 'scripts', script), ...args], {
    cwd: f.root,
    env: { ...env, ...overrides },
    encoding: 'utf8',
    timeout: 10000,
  })
}

function probe(f, { names = ['playwright'], options = {}, moduleUrl = 'import.meta.url' } = {}) {
  f.write(
    'scripts/probe.mjs',
    `import { writeFileSync } from 'node:fs'
import { loadScriptDependencies } from './${helper}'
const modules = loadScriptDependencies(${moduleUrl}, ${JSON.stringify(names)}, ${JSON.stringify(options)})
writeFileSync(new URL('../continued.txt', import.meta.url), 'main executed')
console.log(JSON.stringify({ marker: modules.playwright?.marker, names: Object.keys(modules) }))
`,
  )
}

function packageAt(f, base, name, source) {
  f.write(`${base}/${name}/package.json`, '{"main":"index.cjs","type":"commonjs"}')
  return f.write(`${base}/${name}/index.cjs`, source)
}

function snapshot(root) {
  return fs
    .readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => {
      const filename = path.join(entry.parentPath, entry.name)
      return [path.relative(root, filename), fs.readFileSync(filename).toString('base64')]
    })
    .sort(([a], [b]) => a.localeCompare(b))
}

test('explicit paths load existing modules and normal execution continues', () => {
  const f = fixture()
  probe(f, { names: ['playwright', 'sharp'] })
  const result = run(f, 'probe.mjs', [], {
    PLAYWRIGHT_MODULE_PATH: './modules/playwright.cjs',
    SHARP_MODULE_PATH: f.sharpPath,
  })
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(JSON.parse(result.stdout), {
    marker: 'fixture-playwright',
    names: ['playwright', 'sharp'],
  })
  assert.equal(fs.readFileSync(path.join(f.root, 'continued.txt'), 'utf8'), 'main executed')
})

test('normal Node resolution finds a local package directory', () => {
  const f = fixture()
  probe(f)
  packageAt(f, 'node_modules', 'playwright', browserStub)
  const result = run(f)
  assert.equal(result.status, 0, result.stderr)
  assert.equal(JSON.parse(result.stdout).marker, 'fixture-playwright')
})

test('NODE_PATH supplies an existing module without copying or installing it', () => {
  const f = fixture()
  // Use a virtual resolution base outside this checkout so an optional local
  // installation cannot shadow the NODE_PATH fixture. No file is written there.
  const virtualBase = pathToFileURL(path.join(tmpdir(), path.basename(f.root), 'probe.mjs')).href
  probe(f, { moduleUrl: JSON.stringify(virtualBase) })
  packageAt(f, 'external-modules', 'playwright', browserStub)
  const result = run(f, 'probe.mjs', [], { NODE_PATH: path.join(f.root, 'external-modules') })
  assert.equal(result.status, 0, result.stderr)
  assert.equal(JSON.parse(result.stdout).marker, 'fixture-playwright')
})

test('a broken explicit path fails without falling back or printing its value', () => {
  const f = fixture()
  probe(f)
  packageAt(f, 'node_modules', 'playwright', browserStub)
  const secretPath = path.join(f.root, 'private-path-must-not-be-printed')
  const result = run(f, 'probe.mjs', [], { PLAYWRIGHT_MODULE_PATH: secretPath })
  assert.equal(result.status, 2)
  assert.match(result.stderr, /PLAYWRIGHT_MODULE_PATH/)
  assert.match(result.stderr, /No install is performed/)
  assert.ok(!result.stderr.includes(secretPath))
  assert.ok(!fs.existsSync(path.join(f.root, 'continued.txt')))
})

test('the legacy diagram override works and the standard override takes precedence', () => {
  const f = fixture()
  probe(f, { options: { playwrightAliases: ['CODEX_PLAYWRIGHT_PATH'] } })
  const result = run(f, 'probe.mjs', ['--check-deps'], { CODEX_PLAYWRIGHT_PATH: f.playwrightPath })
  assert.equal(result.status, 0, result.stderr)
  assert.equal(JSON.parse(result.stdout).dependencies[0].source, 'CODEX_PLAYWRIGHT_PATH')
  const overridden = run(f, 'probe.mjs', ['--check-deps'], {
    CODEX_PLAYWRIGHT_PATH: path.join(f.root, 'missing'),
    PLAYWRIGHT_MODULE_PATH: f.playwrightPath,
  })
  assert.equal(overridden.status, 0, overridden.stderr)
  assert.equal(JSON.parse(overridden.stdout).dependencies[0].source, 'PLAYWRIGHT_MODULE_PATH')
})

test('a module directory override is supported', () => {
  const f = fixture()
  probe(f)
  const entry = packageAt(f, 'external-modules', 'playwright', browserStub)
  const result = run(f, 'probe.mjs', ['--check-deps'], {
    PLAYWRIGHT_MODULE_PATH: path.dirname(entry),
  })
  assert.equal(result.status, 0, result.stderr)
})

test('missing transitive dependencies are reported as load errors without raw stacks', () => {
  const f = fixture()
  probe(f)
  f.write('modules/broken.cjs', "require('./private-transitive-path-not-for-output')")
  const result = run(f, 'probe.mjs', ['--check-deps'], {
    PLAYWRIGHT_MODULE_PATH: path.join(f.root, 'modules/broken.cjs'),
  })
  assert.equal(result.status, 2)
  const report = JSON.parse(result.stdout)
  assert.equal(report.dependencies[0].phase, 'load')
  assert.equal(report.dependencies[0].code, 'MODULE_NOT_FOUND')
  assert.ok(!(result.stdout + result.stderr).includes('private-transitive-path-not-for-output'))
  assert.ok(!(result.stdout + result.stderr).includes(f.root))
})

test('incompatible exports fail dependency checks', () => {
  const f = fixture()
  probe(f, { names: ['playwright', 'sharp'] })
  const invalid = f.write('modules/invalid.cjs', 'module.exports = {}')
  const result = run(f, 'probe.mjs', ['--check-deps'], {
    PLAYWRIGHT_MODULE_PATH: invalid,
    SHARP_MODULE_PATH: invalid,
  })
  assert.equal(result.status, 2)
  const report = JSON.parse(result.stdout)
  assert.equal(report.ok, false)
  assert.deepEqual(
    report.dependencies.map((item) => item.code),
    ['INVALID_EXPORTS', 'INVALID_EXPORTS'],
  )
})

for (const [script, names] of browserScripts) {
  for (const available of [true, false]) {
    test(`${script}: --check-deps ${available ? 'succeeds' : 'fails'} before any main work`, () => {
      const f = fixture()
      f.write(`scripts/${script}`, fs.readFileSync(path.join(scriptsRoot, script)))
      // The gallery's static import is pure fixture data; any use of it signals
      // that the script incorrectly continued past the dependency-only branch.
      f.write(
        'docs/design/chart-demo-data.js',
        'export function getChartDemoData() { throw Error("main ran") }',
      )
      const before = snapshot(f.root)
      const result = run(f, script, ['--check-deps'], {
        PLAYWRIGHT_MODULE_PATH: available
          ? f.playwrightPath
          : path.join(f.root, 'missing-playwright'),
        SHARP_MODULE_PATH: available ? f.sharpPath : path.join(f.root, 'missing-sharp'),
      })
      assert.equal(result.status, available ? 0 : 2, result.stderr)
      const report = JSON.parse(result.stdout)
      assert.equal(report.script, script)
      assert.equal(report.ok, available)
      assert.equal(report.checkOnly, true)
      assert.deepEqual(
        report.dependencies.map((item) => item.name),
        names,
      )
      assert.deepEqual(
        report.dependencies.map((item) => item.available),
        names.map(() => available),
      )
      assert.deepEqual(snapshot(f.root), before, 'preflight changed fixture files')
    })
  }
  test(`${script}: missing dependencies stop ordinary invocation before any main work`, () => {
    const f = fixture()
    f.write(`scripts/${script}`, fs.readFileSync(path.join(scriptsRoot, script)))
    f.write(
      'docs/design/chart-demo-data.js',
      'export function getChartDemoData() { throw Error("main ran") }',
    )
    const before = snapshot(f.root)
    const result = run(f, script, [], {
      PLAYWRIGHT_MODULE_PATH: path.join(f.root, 'missing-playwright'),
      SHARP_MODULE_PATH: path.join(f.root, 'missing-sharp'),
    })
    assert.equal(result.status, 2, result.stderr)
    assert.equal(result.stdout, '')
    assert.match(result.stderr, /PLAYWRIGHT_MODULE_PATH/)
    assert.ok(!result.stderr.includes(f.root))
    assert.deepEqual(snapshot(f.root), before, 'dependency failure changed fixture files')
  })
}
