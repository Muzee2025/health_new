// Build a separate Sites preview from the current frontend; never read runtime env/DB.
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const site = path.resolve(process.argv[2] || '')
assert(site.startsWith(path.join(root, 'tmp', 'sites') + path.sep), 'Use a new tmp/sites directory')
assert(fs.existsSync(path.join(site, '.openai', 'hosting.json')), 'Persist Site identity first')
const refresh = process.argv[3] === '--refresh'
assert(!process.argv[3] || refresh, 'Only an explicit --refresh may update an existing Site snapshot')
if (refresh) {
  const gitRoot = execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: site, encoding: 'utf8', windowsHide: true }).trim()
  assert.equal(fs.realpathSync(gitRoot), fs.realpathSync(site), 'Refresh only the standalone Site repository')
  assert(fs.existsSync(path.join(site, 'source-snapshot.json')), 'Refresh only a previously registered source snapshot')
} else assert(!fs.existsSync(path.join(site, 'src')), 'Preserve an existing snapshot instead of overwriting it')
for (const name of ['src', 'public']) fs.cpSync(path.join(root, name), path.join(site, name), { recursive: true })
fs.copyFileSync(path.join(root, 'src', 'assets', 'brand', 'brand-favicon-32.png'), path.join(site, 'public', 'preview-favicon.png'))
fs.mkdirSync(path.join(site, 'docs', 'design'), { recursive: true })
for (const name of ['chart-style.js', 'chart-options.js', 'chart-surfaces.css', 'chart-palette.json']) {
  fs.copyFileSync(path.join(root, 'docs', 'design', name), path.join(site, 'docs', 'design', name))
}
for (const name of ['package.json', 'package-lock.json']) {
  if (fs.existsSync(path.join(root, name))) fs.copyFileSync(path.join(root, name), path.join(site, name))
}
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'backend', 'scripts', 'content-catalog.json'), 'utf8'))
fs.writeFileSync(path.join(site, 'preview-articles.json'), JSON.stringify(catalog.articles.map((article, i) => ({
  id: 900100 + i, title: article.title, category: article.category, summary: article.summary,
  content: article.content, source: '项目原创操作指南 · 演示副本', views: 0,
  created_at: '2026-11-02T04:00:00Z', cover_url: null,
})), null, 2) + '\n')
const files = []
function inventory(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name)
    if (entry.isDirectory()) inventory(full)
    else if (entry.isFile()) files.push({ path: path.relative(root, full).replaceAll('\\', '/'), sha256: createHash('sha256').update(fs.readFileSync(full)).digest('hex') })
    else throw new Error('Source snapshot must contain regular files only')
  }
}
inventory(path.join(root, 'src'))
inventory(path.join(root, 'public'))
fs.writeFileSync(path.join(site, 'source-snapshot.json'), JSON.stringify({ date: '2026-11-02', policy: 'Current frontend bytes only; no env, databases, uploads, credentials or backend runtime', files }, null, 2) + '\n')
fs.writeFileSync(path.join(site, '.gitignore'), 'node_modules/\n.sites-runtime/\n.playwright-cli/\nqa/\n')
const hostingPath = path.join(site, '.openai', 'hosting.json')
const hosting = JSON.parse(fs.readFileSync(hostingPath, 'utf8'))
hosting.static = { ...hosting.static, directory: 'dist', not_found_handling: 'single-page-application' }
fs.writeFileSync(hostingPath, JSON.stringify(hosting, null, 2) + '\n')
console.log(JSON.stringify({ source_files: files.length, site, original_source_read_only: true, refreshed: refresh }))
