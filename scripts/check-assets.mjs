import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { inspectDesignSources } from './check-design-sources.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const assetsRoot = path.join(root, 'src', 'assets')
const manifestPath = path.join(assetsRoot, 'manifest.json')
const jsonMode = process.argv.includes('--json')
const errors = []
const warnings = []
const contrasts = []
const limits = {
  svg: 50 * 1024,
  webp: 200 * 1024,
  background: 300 * 1024,
  logoPng: 2 * 1024 * 1024,
}
const hardAssetLimit = 2 * 1024 * 1024
const required = [
  'id',
  'path',
  'type',
  'size',
  'usage',
  'license',
  'source',
  'owner',
  'status',
  'sha256',
]
const add = (arr, code, file, message) => arr.push({ code, file, message })
const exists = (p) => {
  try {
    return fs.statSync(p).isFile()
  } catch {
    return false
  }
}
const walk = (dir) => {
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    return entry.isDirectory() ? walk(full) : [full]
  })
}
// Text assets are hashed after CRLF->LF normalisation so the recorded digest does
// not depend on the checkout's line endings (Windows autocrlf writes CRLF, Linux
// writes LF). Binary assets are hashed byte-for-byte.
const TEXT_ASSET = /\.(?:svg|txt|md|json|css|js|mjs)$/i
const hashBytes = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex')
const hashFile = (p) => {
  const bytes = fs.readFileSync(p)
  if (!TEXT_ASSET.test(p)) return hashBytes(bytes)
  return hashBytes(Buffer.from(bytes.toString('utf8').replace(/\r\n/g, '\n'), 'utf8'))
}
const rel = (p) => path.relative(root, p).replaceAll('\\', '/')
const isAssetMetadata = (p) =>
  ['manifest.json', 'LICENSES.md'].includes(path.relative(assetsRoot, p).replaceAll('\\', '/')) ||
  path.basename(p) === '.gitattributes'
const categoryFor = (p, item) => {
  const lower = `${p} ${item.type}`.toLowerCase()
  if (/background|(^|\/)bg-/.test(lower)) return 'background'
  if (/logo|brand/.test(lower) && item.type === 'png') return 'logoPng'
  if (/(^|\/)shot-|screenshot/.test(lower)) return 'screenshot'
  if (/avatar/.test(lower) && item.type === 'webp') return 'avatarWebP'
  return item.type
}
const namingOk = (p) =>
  /^(brand|illu|avatar|icon|bg|shot|chart)-[a-z0-9]+(?:-[a-z0-9]+)*\.(svg|webp|png|ico)$/.test(
    path.posix.basename(p),
  )

function imageDimensions(file, ext) {
  const b = fs.readFileSync(file)
  if (ext === '.png' && b.length >= 24 && b.toString('hex', 0, 8) === '89504e470d0a1a0a')
    return [b.readUInt32BE(16), b.readUInt32BE(20)]
  if (
    ext === '.webp' &&
    b.length >= 30 &&
    b.toString('ascii', 0, 4) === 'RIFF' &&
    b.toString('ascii', 8, 12) === 'WEBP'
  ) {
    const kind = b.toString('ascii', 12, 16)
    if (kind === 'VP8X') return [1 + b.readUIntLE(24, 3), 1 + b.readUIntLE(27, 3)]
    if (kind === 'VP8L' && b[20] === 0x2f)
      return [
        1 + (((b[22] & 0x3f) << 8) | b[21]),
        1 + (((b[24] & 0x0f) << 10) | (b[23] << 2) | ((b[22] & 0xc0) >> 6)),
      ]
    if (kind === 'VP8 ' && b.length >= 30)
      return [b.readUInt16LE(26) & 0x3fff, b.readUInt16LE(28) & 0x3fff]
  }
  if (ext === '.svg') {
    const s = b.toString('utf8')
    const vb = s.match(
      /<svg\b[^>]*\bviewBox\s*=\s*["']\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+([\d.]+)\s+([\d.]+)\s*["']/i,
    )
    if (vb) return [Number(vb[3]), Number(vb[4])]
  }
  return null
}

function checkSvg(file, relFile) {
  const s = fs.readFileSync(file, 'utf8')
  const viewBox = s.match(/<svg\b[^>]*\bviewBox\s*=\s*["'][^"']+["']/i)
  if (!viewBox) add(errors, 'SVG_VIEWBOX', relFile, 'SVG must declare a viewBox.')
  const rules = [
    ['SVG_SCRIPT', /<\s*script\b/i],
    ['SVG_EVENT', /\son[a-z]+\s*=/i],
    ['SVG_FOREIGN_OBJECT', /<\s*foreignObject\b/i],
    ['SVG_REMOTE_HREF', /(?:href|xlink:href)\s*=\s*["']\s*(?!#)[^"']+/i],
    ['SVG_IMAGE', /<\s*image\b/i],
    ['SVG_FONT', /@font-face|<\s*font(?:\s|>)/i],
    ['SVG_IMPORT', /@import\b/i],
    ['SVG_EXTERNAL_CSS', /url\(\s*["']?\s*(?:https?:|\/\/|data:)/i],
    ['SVG_DECLARATION', /<!DOCTYPE\b|<!ENTITY\b|<\?xml-stylesheet\b/i],
  ]
  for (const [code, re] of rules)
    if (re.test(s))
      add(errors, code, relFile, 'SVG contains a prohibited executable or remote reference.')
}

function readTokens() {
  const tokenPath = path.join(root, 'src', 'styles', 'tokens.css')
  if (!exists(tokenPath)) {
    add(errors, 'TOKENS_MISSING', 'src/styles/tokens.css', 'Token source file is missing.')
    return null
  }
  const css = fs.readFileSync(tokenPath, 'utf8')
  const vars = new Map(
    [...css.matchAll(/(--[\w-]+)\s*:\s*([^;{}]+)\s*;/g)].map((m) => [m[1], m[2].trim()]),
  )
  const resolveRaw = (key, seen = new Set()) => {
    if (seen.has(key)) throw new Error(`cyclic token alias ${key}`)
    const value = vars.get(key)
    if (!value) throw new Error(`unresolved token ${key}`)
    const v = value
      .replace(/var\(\s*(--[\w-]+)(?:\s*,\s*([^()]+))?\s*\)/g, (_, alias, fallback) => {
        if (!vars.has(alias) && fallback) return fallback.trim()
        return resolveRaw(alias, new Set([...seen, key]))
      })
      .trim()
    return v
  }
  const resolve = (key) => color(resolveRaw(key))
  return { vars, resolve, tokenPath }
}
function color(value) {
  const s = value.trim().toLowerCase()
  let c,
    alpha = 1
  if (/^#[\da-f]{3,8}$/.test(s)) {
    const h = s.slice(1)
    if (h.length === 3 || h.length === 4) c = [...h.slice(0, 3)].map((x) => parseInt(x + x, 16))
    else if (h.length === 6 || h.length === 8)
      c = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16))
    if (h.length === 4) alpha = parseInt(h[3] + h[3], 16) / 255
    if (h.length === 8) alpha = parseInt(h.slice(6, 8), 16) / 255
  } else {
    const m = s.match(
      /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+%?)\s*)?\)$/,
    )
    if (m) {
      c = m.slice(1, 4).map(Number)
      if (m[4]) alpha = m[4].endsWith('%') ? Number(m[4].slice(0, -1)) / 100 : Number(m[4])
    }
  }
  if (!c || c.some((x) => !Number.isFinite(x) || x < 0 || x > 255))
    throw new Error(`unsupported color value ${s}`)
  if (!Number.isFinite(alpha) || alpha !== 1)
    throw new Error(`non-opaque color ${s} is not supported for contrast checks`)
  return c
}
function luminance(c) {
  const rgb = c.map((x) => {
    const v = x / 255
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
}
function contrast(a, b) {
  const x = luminance(a),
    y = luminance(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

let manifest
if (!exists(manifestPath))
  add(
    errors,
    'MANIFEST_MISSING',
    'src/assets/manifest.json',
    'Manifest is missing; asset validation cannot pass.',
  )
else {
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
  } catch {
    add(errors, 'MANIFEST_INVALID_JSON', 'src/assets/manifest.json', 'Manifest is not valid JSON.')
  }
}

let assets = []
if (manifest) {
  if (typeof manifest.version !== 'string' || !manifest.version)
    add(
      errors,
      'MANIFEST_VERSION',
      'src/assets/manifest.json',
      'version must be a non-empty string.',
    )
  if (typeof manifest.updated !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(manifest.updated))
    add(errors, 'MANIFEST_UPDATED', 'src/assets/manifest.json', 'updated must use YYYY-MM-DD.')
  if (!Array.isArray(manifest.assets))
    add(errors, 'MANIFEST_ASSETS', 'src/assets/manifest.json', 'assets must be an array.')
  else assets = manifest.assets
  const ids = new Set(),
    paths = new Set(),
    seenHashes = new Map()
  for (const [i, item] of assets.entries()) {
    const at = `src/assets/manifest.json#assets[${i}]`
    for (const key of required)
      if (!(key in (item ?? {})))
        add(errors, 'FIELD_REQUIRED', at, `Required field ${key} is missing.`)
    if (!item || typeof item !== 'object') continue
    for (const key of ['id', 'path', 'type', 'usage', 'license', 'source', 'owner', 'status']) {
      if (typeof item[key] !== 'string' || !item[key].trim())
        add(errors, 'FIELD_INVALID', at, `${key} must be a non-empty string.`)
    }
    if (typeof item.id === 'string') {
      if (ids.has(item.id)) add(errors, 'ID_DUPLICATE', at, `Duplicate id ${item.id}.`)
      ids.add(item.id)
    }
    if (typeof item.path !== 'string') continue
    const p = item.path
    if (
      path.posix.isAbsolute(p) ||
      path.win32.isAbsolute(p) ||
      p.includes('\\') ||
      p.split('/').includes('..')
    ) {
      add(errors, 'PATH_UNSAFE', at, 'Asset path must be a safe relative POSIX path.')
      continue
    }
    if (paths.has(p)) add(errors, 'PATH_DUPLICATE', at, `Duplicate path ${p}.`)
    paths.add(p)
    const full = path.resolve(assetsRoot, p)
    if (!full.startsWith(`${path.resolve(assetsRoot)}${path.sep}`) || !exists(full)) {
      add(errors, 'FILE_MISSING', at, `Manifest path is missing or escapes src/assets: ${p}.`)
      continue
    }
    const ext = path.extname(p).toLowerCase()
    if (!['.svg', '.png', '.webp', '.ico'].includes(ext))
      add(errors, 'FORMAT_UNSUPPORTED', at, 'Only SVG, PNG, WebP, and ICO assets are supported.')
    if (typeof item.type === 'string' && item.type !== ext.slice(1))
      add(errors, 'TYPE_MISMATCH', at, `type must match file extension ${ext.slice(1)}.`)
    if (
      !Array.isArray(item.size) ||
      item.size.length !== 2 ||
      item.size.some((n) => !Number.isInteger(n) || n <= 0)
    )
      add(errors, 'SIZE_INVALID', at, 'size must contain two positive integers.')
    if (!['approved', 'legacy-unverified'].includes(item.status))
      add(errors, 'STATUS_INVALID', at, 'status must be approved or legacy-unverified.')
    if (item.status === 'approved') {
      if (!namingOk(p))
        add(errors, 'NAME_INVALID', p, 'Approved asset name does not match the naming convention.')
      if (!item.license || /unknown|unverified|待核/i.test(item.license) || !item.source)
        add(errors, 'LICENSE_INVALID', p, 'Approved assets require a stated license and source.')
    } else
      add(
        warnings,
        'LEGACY_UNVERIFIED',
        p,
        'Legacy asset has unverified provenance; not counted as approved.',
      )
    const bytes = fs.statSync(full).size
    if (bytes > hardAssetLimit)
      add(
        errors,
        'SIZE_HARD_LIMIT',
        p,
        `File is ${bytes} bytes; universal limit is ${hardAssetLimit} bytes.`,
      )
    const cat = categoryFor(p, item)
    const max =
      ext === '.svg'
        ? limits.svg
        : (limits[cat] ??
          (cat === 'avatarWebP'
            ? limits.webp
            : cat === 'screenshot' || (ext === '.webp' && cat === 'background')
              ? 300 * 1024
              : null))
    if (max && bytes > max)
      add(errors, 'SIZE_LIMIT', p, `File is ${bytes} bytes; limit is ${max} bytes.`)
    if (ext === '.svg') checkSvg(full, p)
    const dims = imageDimensions(full, ext)
    if (dims && Array.isArray(item.size) && (dims[0] !== item.size[0] || dims[1] !== item.size[1]))
      add(
        errors,
        'DIMENSIONS_MISMATCH',
        p,
        `Actual dimensions ${dims[0]}x${dims[1]} differ from manifest.`,
      )
    if (['.png', '.webp'].includes(ext) && !dims)
      add(errors, 'DIMENSIONS_UNREADABLE', p, 'Could not parse actual image dimensions.')
    const digest = hashFile(full)
    if (typeof item.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(item.sha256))
      add(errors, 'HASH_INVALID', p, 'Manifest sha256 must be a lowercase SHA-256 digest.')
    else if (item.sha256 !== digest)
      add(errors, 'HASH_MISMATCH', p, 'Manifest sha256 does not match file content.')
    if (
      item.sourceInput ||
      (item.status === 'approved' && ['MIT', 'CC0-1.0'].includes(item.license))
    ) {
      const input = item.sourceInput
      const safeInput =
        typeof input === 'string' &&
        !path.posix.isAbsolute(input) &&
        !path.win32.isAbsolute(input) &&
        !input.includes('\\') &&
        !input.split('/').includes('..')
      if (!safeInput)
        add(
          errors,
          'SOURCE_PATH_UNSAFE',
          p,
          'Upstream input must be a safe repository-relative POSIX path.',
        )
      else {
        const inputPath = path.resolve(root, input)
        if (!inputPath.startsWith(`${root}${path.sep}`) || !exists(inputPath))
          add(
            errors,
            'SOURCE_INPUT_MISSING',
            p,
            'Recorded upstream input is missing or outside the repository.',
          )
        else if (
          typeof item.sourceSha256 !== 'string' ||
          !/^[a-f0-9]{64}$/.test(item.sourceSha256) ||
          hashFile(inputPath) !== item.sourceSha256
        )
          add(
            errors,
            'SOURCE_HASH_MISMATCH',
            p,
            'Recorded upstream digest does not match the preserved source input.',
          )
      }
      for (const key of ['sourceRevision', 'modifications', 'notice']) {
        if (typeof item[key] !== 'string' || !item[key].trim())
          add(errors, 'SOURCE_METADATA_MISSING', p, `Third-party metadata requires ${key}.`)
      }
      if (item.notice !== 'src/assets/LICENSES.md')
        add(
          errors,
          'SOURCE_NOTICE_MISSING',
          p,
          'Third-party notice must point to the versioned license register.',
        )
    }
    const key = `${item.type}:${digest}`
    const prior = seenHashes.get(key)
    if (prior && item.status === 'approved' && prior.status === 'approved')
      add(
        errors,
        'HASH_DUPLICATE',
        p,
        `Approved asset duplicates ${prior.path} within the same type.`,
      )
    else if (prior)
      add(
        warnings,
        'LEGACY_HASH_DUPLICATE',
        p,
        `Same-type duplicate with ${prior.path}; duplicate includes an unverified legacy asset.`,
      )
    else seenHashes.set(key, { path: p, status: item.status })
  }
  const allFiles = walk(assetsRoot).filter((p) => !isAssetMetadata(p))
  const listed = new Set([...paths].map((p) => path.resolve(assetsRoot, p)))
  for (const f of allFiles)
    if (!listed.has(path.resolve(f)))
      add(errors, 'COVERAGE_MISSING', rel(f), 'Asset file is not listed in manifest.')
  for (const p of paths) {
    const full = path.resolve(assetsRoot, p)
    if (exists(full) && !allFiles.some((f) => path.resolve(f) === full))
      add(errors, 'COVERAGE_EXTRA', p, 'Manifest path is outside scanned asset files.')
  }
  const licensesPath = path.join(assetsRoot, 'LICENSES.md')
  if (!exists(licensesPath))
    add(errors, 'LICENSES_MISSING', rel(licensesPath), 'License register is missing.')
  else {
    const licenses = fs.readFileSync(licensesPath, 'utf8')
    for (const item of assets.filter((a) => a?.status === 'approved' && typeof a.id === 'string')) {
      if (!licenses.includes(item.id))
        add(
          errors,
          'LICENSE_RECORD_MISSING',
          'src/assets/LICENSES.md',
          `No license register entry found for ${item.id}.`,
        )
    }
  }
}

// Check local executable resources in the new library and PPT kit; old application pages are W2 debt.
const scanRoots = ['src/styles', 'src/assets', 'docs/design/ppt-kit'].map((p) => path.join(root, p))
const previewFiles = walk(path.join(root, 'docs/design')).filter((f) =>
  /^(?:library-preview|chart-[a-z0-9-]+)\.(?:html|css|js|mjs)$/.test(path.basename(f)),
)
const remoteRe = /(?:https?:)?\/\/[^\s"')<>]+/gi
const isStandardXmlns = (content, url, index) => {
  const prefix = content.slice(Math.max(0, index - 160), index)
  const inXmlns = /xmlns(?::[\w-]+)?\s*=\s*["']$/i.test(prefix)
  return Boolean(
    inXmlns &&
    [
      'http://www.w3.org/2000/svg',
      'http://www.w3.org/1999/xlink',
      'http://www.w3.org/XML/1998/namespace',
    ].includes(url),
  )
}
const hasRemoteReference = (content) =>
  [...content.matchAll(remoteRe)].some((m) => !isStandardXmlns(content, m[0], m.index))
for (const dir of scanRoots)
  for (const f of walk(dir)) {
    if (!/\.(?:css|js|mjs|html|json|svg)$/i.test(f) || path.basename(f) === 'manifest.json')
      continue
    const content = fs.readFileSync(f, 'utf8')
    if (hasRemoteReference(content))
      add(
        errors,
        'REMOTE_RESOURCE',
        rel(f),
        'New library source contains an external resource URL.',
      )
  }
for (const previewPath of previewFiles) {
  if (hasRemoteReference(fs.readFileSync(previewPath, 'utf8')))
    add(
      errors,
      'REMOTE_RESOURCE',
      rel(previewPath),
      'New library preview contains an external resource URL.',
    )
}

const tokenData = readTokens()
if (tokenData) {
  const pair = (fg, bg, label) => {
    try {
      const rawRatio = contrast(tokenData.resolve(fg), tokenData.resolve(bg))
      const ratio = Number(rawRatio.toFixed(2))
      const passed = rawRatio >= 4.5
      contrasts.push({ label, foreground: fg, background: bg, ratio, passed })
      if (!passed)
        add(
          errors,
          'CONTRAST_LOW',
          rel(tokenData.tokenPath),
          `${label} contrast is ${ratio}:1; minimum is 4.5:1.`,
        )
    } catch (e) {
      add(errors, 'TOKEN_UNRESOLVED', rel(tokenData.tokenPath), `${label}: ${e.message}`)
    }
  }
  pair('--brand-600', '--brand-100', 'brand text on brand tint')
  pair('--text-primary', '--surface', 'primary text on surface')
  pair('--text-secondary', '--surface', 'secondary text on surface')
  for (const name of ['success', 'warning', 'danger', 'info'])
    pair(`--${name}-text`, `--${name}-100`, `${name} text on tint`)

  const palettePath = path.join(root, 'docs/design/ppt-kit/chart-palette.json')
  if (!exists(palettePath))
    add(errors, 'PALETTE_MISSING', rel(palettePath), 'Derived chart palette JSON is missing.')
  else {
    try {
      const palette = JSON.parse(fs.readFileSync(palettePath, 'utf8'))
      const order = [
        'brand-500',
        'brand-600',
        'success',
        'warning',
        'danger',
        'info',
        'risk-low',
        'risk-mid',
        'risk-high',
        'emo-joy',
        'emo-sadness',
        'emo-neutral',
        'emo-fear',
        'emo-anxiety',
        'emo-anger',
      ]
      if (palette.source !== 'src/styles/tokens.css')
        add(
          errors,
          'PALETTE_SOURCE',
          rel(palettePath),
          'Palette source must identify src/styles/tokens.css.',
        )
      if (JSON.stringify(palette.order) !== JSON.stringify(order))
        add(
          errors,
          'PALETTE_ORDER',
          rel(palettePath),
          'Palette order must match the canonical token order.',
        )
      if (!Array.isArray(palette.colors) || palette.colors.length !== order.length)
        add(
          errors,
          'PALETTE_COLORS',
          rel(palettePath),
          'Palette colors must contain one value for each ordered token.',
        )
      else
        order.forEach((name, i) => {
          try {
            const expected = `#${tokenData
              .resolve(`--${name}`)
              .map((v) => Math.round(v).toString(16).padStart(2, '0'))
              .join('')}`
            const actual = `#${color(String(palette.colors[i]))
              .map((v) => Math.round(v).toString(16).padStart(2, '0'))
              .join('')}`
            if (actual !== expected)
              add(
                errors,
                'PALETTE_TOKEN_MISMATCH',
                rel(palettePath),
                `Palette value ${i} does not match --${name}.`,
              )
          } catch (e) {
            add(
              errors,
              'PALETTE_TOKEN_INVALID',
              rel(palettePath),
              `Palette value ${i}: ${e.message}`,
            )
          }
        })
      for (const [group, expectedPairs] of Object.entries({
        emotions: [
          ['joy', 'emo-joy'],
          ['sadness', 'emo-sadness'],
          ['neutral', 'emo-neutral'],
          ['fear', 'emo-fear'],
          ['anxiety', 'emo-anxiety'],
          ['anger', 'emo-anger'],
        ],
        risks: [
          ['low', 'risk-low'],
          ['mid', 'risk-mid'],
          ['high', 'risk-high'],
        ],
      })) {
        for (const [key, tokenName] of expectedPairs) {
          try {
            const expected = `#${tokenData
              .resolve(`--${tokenName}`)
              .map((v) => Math.round(v).toString(16).padStart(2, '0'))
              .join('')}`
            const actual = `#${color(String(palette[group]?.[key]))
              .map((v) => Math.round(v).toString(16).padStart(2, '0'))
              .join('')}`
            if (actual !== expected)
              add(
                errors,
                'PALETTE_GROUP_MISMATCH',
                rel(palettePath),
                `${group}.${key} does not match --${tokenName}.`,
              )
          } catch (e) {
            add(errors, 'PALETTE_GROUP_INVALID', rel(palettePath), `${group}.${key}: ${e.message}`)
          }
        }
      }
    } catch {
      add(
        errors,
        'PALETTE_INVALID',
        rel(palettePath),
        'Palette JSON is invalid or has an unsupported shape.',
      )
    }
  }
}

// W2 debt counts are informational and never block G1.
const oldFiles = [
  ...walk(path.join(root, 'src')),
  ...walk(path.join(root, 'public')),
  path.join(root, 'index.html'),
].filter((p) => exists(p) && /\.(?:vue|css|js|mjs|html)$/i.test(p))
let legacyColors = 0,
  legacyUrls = 0
for (const f of oldFiles) {
  if (/src[\\/]styles[\\/]/i.test(f) || /src[\\/]assets[\\/]/i.test(f)) continue
  const s = fs.readFileSync(f, 'utf8')
  legacyColors += [...s.matchAll(/#[0-9a-fA-F]{6}\b/g)].length
  legacyUrls += [...s.matchAll(/https?:\/\//g)].length
}

const approved = assets.filter((a) => a?.status === 'approved').length
const legacy = assets.filter((a) => a?.status === 'legacy-unverified').length
const fileCount = walk(assetsRoot).filter((p) => !isAssetMetadata(p)).length
if (manifest) {
  const approvedByHash = new Map()
  for (const item of assets.filter((a) => a?.status === 'approved' && typeof a.path === 'string')) {
    const f = path.resolve(assetsRoot, item.path)
    if (exists(f)) approvedByHash.set(hashFile(f), item.path)
  }
  const mirrorRoots = ['src', 'public'].map((p) => path.join(root, p))
  const mirrorFiles = mirrorRoots
    .flatMap(walk)
    .filter(
      (f) =>
        /\.(?:svg|png|webp|ico)$/i.test(f) &&
        path.relative(assetsRoot, f).startsWith('..') &&
        !f.includes(`${path.sep}ppt-kit${path.sep}`),
    )
  for (const f of mirrorFiles) {
    const source = approvedByHash.get(hashFile(f))
    if (source)
      add(
        warnings,
        'APPROVED_MIRROR',
        rel(f),
        `Byte-identical mirror of approved asset ${source} exists outside ppt-kit.`,
      )
  }
}
const designSources = inspectDesignSources(root)
for (const error of designSources.errors)
  add(errors, `DESIGN_SOURCE_${error.code}`, error.file, error.message)
const result = {
  status: errors.length ? 'failed' : 'passed',
  manifest: exists(manifestPath),
  approved,
  legacy,
  coverage: {
    listed: pathsCount(assets),
    files: fileCount,
    complete:
      Boolean(manifest) &&
      errors.every(
        (e) =>
          !['COVERAGE_MISSING', 'COVERAGE_EXTRA', 'FILE_MISSING', 'PATH_UNSAFE'].includes(e.code),
      ),
  },
  errors,
  warnings,
  contrasts,
  designSources,
  w2Legacy: {
    hardcodedColorOccurrences: legacyColors,
    externalUrlOccurrences: legacyUrls,
    blocking: false,
  },
  limitations: [
    'ICO dimensions are not parsed; SVG viewBox is validated and raster PNG/WebP dimensions are parsed from headers.',
    'Mirror scan covers versioned src and public; it excludes ppt-kit copies and does not scan backend/uploads or ignored dependency/cache directories.',
  ],
}
function pathsCount(list) {
  return list.filter((a) => a && typeof a.path === 'string').length
}

if (jsonMode) console.log(JSON.stringify(result, null, 2))
else {
  console.log(`Asset check: ${result.status.toUpperCase()}`)
  console.log(
    `Approved: ${approved}; legacy-unverified: ${legacy}; coverage: ${result.coverage.listed}/${fileCount}`,
  )
  for (const c of contrasts)
    console.log(`Contrast ${c.label}: ${c.ratio}:1 ${c.passed ? 'PASS' : 'FAIL'}`)
  console.log(
    `W2 legacy report (informational): ${legacyColors} hardcoded color occurrences, ${legacyUrls} external URL occurrences.`,
  )
  for (const e of errors) console.log(`ERROR ${e.code} ${e.file}: ${e.message}`)
  for (const w of warnings) console.log(`WARN ${w.code} ${w.file}: ${w.message}`)
}
process.exitCode = errors.length ? 1 : 0
