/** Enforce approved library sources without reading runtime configuration or data. */
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const defaultRoot = fileURLToPath(new URL('../', import.meta.url))
const walk = (directory) =>
  !fs.existsSync(directory)
    ? []
    : fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const target = path.join(directory, entry.name)
        return entry.isDirectory() ? walk(target) : [target]
      })

export function inspectDesignSources(root = defaultRoot) {
  const errors = []
  const relative = (target) => path.relative(root, target).replaceAll('\\', '/')
  const issue = (code, file, message) => errors.push({ code, file, message })
  const readJson = (name) => {
    try {
      return JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'))
    } catch {
      issue('CATALOG_READ', name, 'Required library JSON is missing or invalid.')
      return null
    }
  }
  const manifest = readJson('src/assets/manifest.json')
  const catalog = readJson('src/design/library-catalog.json')
  if (!manifest || !catalog)
    return { status: 'failed', errors, staticAssetRoles: 0, icons: 0, scannedFiles: 0 }
  const entries = new Map()
  for (const asset of manifest.assets || []) {
    if (entries.has(asset.id))
      issue('DUPLICATE_ASSET_ID', 'src/assets/manifest.json', 'Manifest IDs must be unique.')
    entries.set(asset.id, asset)
  }
  const referenced = new Set()
  function approved(id, role) {
    const asset = entries.get(id)
    if (!asset || asset.status !== 'approved') {
      issue(
        'ASSET_NOT_APPROVED',
        'src/design/library-catalog.json',
        `${role} must reference an approved manifest ID.`,
      )
      return null
    }
    const absolute = path.resolve(root, 'src/assets', asset.path || '')
    const assetRoot = path.resolve(root, 'src/assets') + path.sep
    let regularLocalFile = false
    try {
      regularLocalFile =
        fs.lstatSync(absolute).isFile() &&
        fs
          .realpathSync(absolute)
          .startsWith(fs.realpathSync(path.join(root, 'src/assets')) + path.sep)
    } catch {}
    if (
      !asset.path ||
      !absolute.startsWith(assetRoot) ||
      !asset.license ||
      !asset.source ||
      !regularLocalFile
    ) {
      issue(
        'ASSET_SOURCE_INVALID',
        'src/design/library-catalog.json',
        `${role} has an invalid path, source or license.`,
      )
      return null
    }
    // Same normalisation as check-assets.mjs: text assets are digested after
    // CRLF->LF so a Windows checkout and a Linux checkout agree.
    const TEXT_ASSET = /\.(?:svg|txt|md|json|css|js|mjs)$/i
    const digest = TEXT_ASSET.test(absolute)
      ? crypto
          .createHash('sha256')
          .update(
            Buffer.from(fs.readFileSync(absolute).toString('utf8').replace(/\r\n/g, '\n'), 'utf8'),
          )
          .digest('hex')
      : crypto.createHash('sha256').update(fs.readFileSync(absolute)).digest('hex')
    if (digest !== asset.sha256) {
      issue(
        'ASSET_HASH_CHANGED',
        relative(absolute),
        'Referenced asset bytes differ from the approved manifest.',
      )
    }
    referenced.add(id)
    return { ...asset, absolute }
  }
  if (catalog.schemaVersion !== 1 || !catalog.assets || !catalog.icons)
    issue(
      'CATALOG_SCHEMA',
      'src/design/library-catalog.json',
      'Expected schemaVersion 1 with asset and icon maps.',
    )
  for (const [role, id] of Object.entries(catalog.assets || {})) approved(id, role)
  for (const [name, icon] of Object.entries(catalog.icons || {})) {
    if (icon.kind === 'asset' || icon.kind === 'symbol') {
      const asset = approved(icon.assetId, `icon:${name}`)
      if (icon.kind === 'symbol' && asset) {
        const symbols = [
          ...fs
            .readFileSync(asset.absolute, 'utf8')
            .matchAll(/<symbol\b[^>]*\bid=["']([^"']+)["']/g),
        ].map((match) => match[1])
        if (!symbols.includes(icon.symbol))
          issue(
            'SYMBOL_UNKNOWN',
            'src/design/library-catalog.json',
            `icon:${name} references an absent sprite symbol.`,
          )
      }
    } else if (icon.kind === 'element-plus') {
      if (
        icon.source !== '@element-plus/icons-vue' ||
        icon.scope !== 'standard-control' ||
        !/^[A-Z][A-Za-z0-9]+$/.test(icon.export || '')
      ) {
        issue(
          'ICON_SOURCE_INVALID',
          'src/design/library-catalog.json',
          `icon:${name} requires a declared standard-control export.`,
        )
      }
    } else
      issue(
        'ICON_KIND_UNKNOWN',
        'src/design/library-catalog.json',
        `icon:${name} has an unknown source kind.`,
      )
  }
  const chartSources = {
    styleSource: 'docs/design/chart-style.js',
    optionSource: 'docs/design/chart-options.js',
    cssSource: 'docs/design/chart-surfaces.css',
  }
  for (const [key, source] of Object.entries(chartSources)) {
    if (catalog.charts?.[key] !== source || !fs.existsSync(path.join(root, source))) {
      issue(
        'CHART_SOURCE_INVALID',
        'src/design/library-catalog.json',
        `${key} must point to the shared library source.`,
      )
    }
  }
  if (catalog.charts?.dataPolicy !== 'business-api-only')
    issue(
      'DATA_POLICY',
      'src/design/library-catalog.json',
      'Business charts must retain API data, not gallery demonstration values.',
    )

  const files = [
    ...walk(path.join(root, 'src')),
    ...walk(path.join(root, 'public')),
    path.join(root, 'index.html'),
  ].filter(
    (target) =>
      fs.existsSync(target) &&
      /\.(vue|css|js|mjs|ts|html)$/.test(target) &&
      !relative(target).startsWith('src/assets/') &&
      !/\.test\.[cm]?[jt]s$/.test(target),
  )
  for (const file of files) {
    const name = relative(file)
    const source = fs.readFileSync(file, 'utf8')
    const assetResolver = name === 'src/design/asset-registry.js'
    const iconResolver = name === 'src/design/icon-registry.js'
    if (!assetResolver && /["'`](?:assets\/|[^"'`\r\n]*\/assets\/)[^"'`\r\n]*["'`]/.test(source)) {
      issue(
        'DIRECT_ASSET_REFERENCE',
        name,
        'Static assets must be resolved through the approved library registry.',
      )
    }
    if (!iconResolver && source.includes('@element-plus/icons-vue'))
      issue(
        'DIRECT_ICON_IMPORT',
        name,
        'Use the library icon whitelist instead of a direct icon-package import.',
      )
    if (
      name.startsWith('src/') &&
      /(?:from|import\s*\()[^\n]*(?:chart-demo-data|chart-library\.js)/.test(source)
    )
      issue(
        'DEMO_DATA_IN_BUSINESS',
        name,
        'Only shared chart styles/options may enter business code.',
      )
    if (/(?:\.|\?\.)setOption\s*\(/.test(source))
      issue(
        'RAW_CHART_OPTION',
        name,
        'Business ECharts options must pass through the shared library adapter.',
      )
    if (/new\s+Chart\s*\(/.test(source) && !source.includes('createLibraryChartJsConfig'))
      issue(
        'RAW_CHARTJS_CONFIG',
        name,
        'Business Chart.js configuration must use the library adapter.',
      )
    if (/<el-?empty\b/i.test(source) && name !== 'src/design/LibraryEmpty.vue')
      issue(
        'DEFAULT_EMPTY_ART',
        name,
        'Use LibraryEmpty so empty-state artwork comes from the approved manifest.',
      )
    // Both the opening and closing tags may span lines after formatting
    // (Prettier can move the trailing '>' to the next line). A bare `>` or
    // `[^>]*>` would then match the wrong delimiter and swallow the next
    // sibling element into the icon body, producing false
    // UNREGISTERED_ICON_COMPONENT reports.
    for (const match of source.matchAll(/<el-?icon\b[\s\S]*?>\s*([\s\S]*?)\s*<\/el-?icon\s*>/gi)) {
      if (/<(?!LibraryIcon\b|\/)[A-Za-z][\w-]*\b/.test(match[1]))
        issue(
          'UNREGISTERED_ICON_COMPONENT',
          name,
          'Explicit control icons must resolve through LibraryIcon, not removed global component registrations.',
        )
    }
    if (/\p{Extended_Pictographic}/u.test(source))
      issue('DECORATIVE_EMOJI', name, 'Use a registered library icon for static graphical content.')
    if (/<svg\b/i.test(source) && name !== 'src/design/LibraryIcon.vue')
      issue('INLINE_SVG', name, 'Page-authored SVG must be replaced by a registered library asset.')
    if (/data:image\//i.test(source))
      issue('INLINE_IMAGE', name, 'Inline static images must be registered library assets.')
    if (/(?:src|href)\s*=\s*["'](?:https?:)?\/\/|url\(\s*["']?(?:https?:)?\/\//i.test(source))
      issue('REMOTE_VISUAL', name, 'Remote static visual references are not allowed.')
    // public/chunk-error.html is the last-resort page the router shows when a
    // dynamic import fails. Its whole point is to load no chunks, so it cannot
    // import the token stylesheet either; it carries its own colours on
    // purpose. Every other file still has to use the approved tokens.
    if (
      !name.startsWith('src/styles/') &&
      name !== 'public/chunk-error.html' &&
      /#[\da-f]{3,8}\b|rgba?\(\s*\d|hsla?\(\s*\d/i.test(source)
    )
      issue('INLINE_COLOR', name, 'Use approved design tokens or the shared chart palette.')
    for (const match of source.matchAll(/\bgetVisualAsset\(\s*['"]([^'"]+)['"]/g)) {
      if (!Object.hasOwn(catalog.assets || {}, match[1]))
        issue('ASSET_ROLE_UNKNOWN', name, `Unknown static asset role: ${match[1]}.`)
    }
    for (const match of source.matchAll(
      /<(?:LibraryIcon|library-icon)\b[^>]*?(?<!:)\bname=['"]([^'"]+)['"]/g,
    )) {
      if (!Object.hasOwn(catalog.icons || {}, match[1]))
        issue('ICON_ROLE_UNKNOWN', name, `Unknown static icon role: ${match[1]}.`)
    }
  }
  return {
    status: errors.length ? 'failed' : 'passed',
    staticAssetRoles: Object.keys(catalog.assets || {}).length,
    icons: Object.keys(catalog.icons || {}).length,
    approvedAssetsReferenced: referenced.size,
    scannedFiles: files.length,
    errors,
    boundaries: [
      'Runtime user uploads, article content, conversation text and chart data remain governed by the business API.',
      'This static check does not replace browser rendering, dynamic-key validation, or review of chart semantics and CSS layout.',
    ],
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = inspectDesignSources()
  console.log(JSON.stringify(report, null, 2))
  process.exitCode = report.status === 'passed' ? 0 : 1
}
