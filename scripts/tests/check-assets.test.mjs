/**
 * Behaviour lock for check-assets.mjs.
 *
 * check-assets.mjs is a top-level script: it derives the repository root from its
 * own location and runs on import. To test it against a fixture tree the script
 * (and the module it imports) are copied into the fixture and executed as a
 * child process, then the JSON report is inspected.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const scripts = path.resolve(here, '..')
const scratch = fileURLToPath(new URL('../../tmp/asset-check-fixtures/', import.meta.url))
fs.mkdirSync(scratch, { recursive: true })

// Smallest real PNG: the header carries the dimensions the checker parses.
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

function fixture() {
  const root = fs.mkdtempSync(path.join(scratch, 'case-'))
  const write = (name, content) => {
    const target = path.join(root, name)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.writeFileSync(target, content)
  }
  for (const name of ['check-assets.mjs', 'check-design-sources.mjs'])
    write(`scripts/${name}`, fs.readFileSync(path.join(scripts, name), 'utf8'))
  const approvedPath = 'brand/brand-probe.png'
  write(`src/assets/${approvedPath}`, PNG_1X1)
  const manifest = {
    version: '1',
    updated: '2026-11-13',
    assets: [
      {
        id: 'brand-probe',
        path: approvedPath,
        type: 'png',
        size: [1, 1],
        usage: 'synthetic fixture',
        license: 'LicenseRef-Project-Original',
        source: 'Synthetic test fixture',
        owner: 'tests',
        status: 'approved',
        sha256: crypto.createHash('sha256').update(PNG_1X1).digest('hex'),
      },
    ],
  }
  write('src/assets/manifest.json', JSON.stringify(manifest))
  write('src/assets/LICENSES.md', '# Licenses\n\n- brand-probe\n')
  return { root, write, approvedPath }
}

/** Run the copied checker inside the fixture and return its parsed JSON report. */
function inspect(root) {
  let stdout
  try {
    stdout = execFileSync(
      process.execPath,
      [path.join(root, 'scripts/check-assets.mjs'), '--json'],
      {
        cwd: root,
        encoding: 'utf8',
      },
    )
  } catch (error) {
    // A failing fixture still prints its report; the exit code is asserted separately.
    stdout = error.stdout
    if (typeof stdout !== 'string') throw error
  }
  return JSON.parse(stdout)
}

const mirrors = (report) =>
  report.warnings
    .filter((warning) => warning.code === 'APPROVED_MIRROR')
    .map((warning) => warning.file)

test('an approved asset inside src/assets is never reported as its own mirror', () => {
  const f = fixture()
  assert.deepEqual(mirrors(inspect(f.root)), [])
})

test('a byte-identical copy beside src/assets is scanned, not skipped by path prefix', () => {
  const f = fixture()
  f.write('src/assets-probe-mirror.png', PNG_1X1)
  assert.deepEqual(mirrors(inspect(f.root)), ['src/assets-probe-mirror.png'])
})

test('a byte-identical copy under public is still reported', () => {
  const f = fixture()
  f.write('public/probe-mirror.png', PNG_1X1)
  assert.deepEqual(mirrors(inspect(f.root)), ['public/probe-mirror.png'])
})

test('a sibling directory whose name merely starts with assets is not treated as inside it', () => {
  const f = fixture()
  f.write('src/assetsX/probe-mirror.png', PNG_1X1)
  assert.deepEqual(mirrors(inspect(f.root)), ['src/assetsX/probe-mirror.png'])
})

test('an unrelated image produces no mirror warning', () => {
  const f = fixture()
  const other = Buffer.concat([PNG_1X1, Buffer.from('different bytes')])
  f.write('public/other.png', other)
  assert.deepEqual(mirrors(inspect(f.root)), [])
})
