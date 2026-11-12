import manifest from '../assets/manifest.json'
import catalog from './library-catalog.json'

// Only this module resolves image URLs. Legacy files are excluded before bundling.
const assetUrls = import.meta.glob(
  ['../assets/**/*.{svg,png,webp}', '!../assets/avatars/**/psych-*'],
  { eager: true, query: '?url&no-inline', import: 'default' },
)
const manifestById = new Map(manifest.assets.map((asset) => [asset.id, asset]))

export function getApprovedAsset(id) {
  const asset = manifestById.get(id)
  if (!asset || asset.status !== 'approved') throw new Error(`Unapproved library asset: ${id}`)
  if (
    !asset.license ||
    !asset.source ||
    !asset.sha256 ||
    /(^|\/)\.\.(\/|$)|^[/]|:/.test(asset.path)
  ) {
    throw new Error(`Invalid library asset record: ${id}`)
  }
  const url = assetUrls[`../assets/${asset.path}`]
  if (!url) throw new Error(`Missing approved library file: ${id}`)
  return Object.freeze({ ...asset, url })
}

export function getVisualAsset(role) {
  const id = catalog.assets[role]
  if (!id) throw new Error(`Unknown library asset role: ${role}`)
  return getApprovedAsset(id)
}

export function getLibraryIconRecord(name) {
  const record = catalog.icons[name]
  if (!record) throw new Error(`Unknown library icon: ${name}`)
  if (record.kind === 'element-plus') return Object.freeze({ ...record })
  const asset = getApprovedAsset(record.assetId)
  if (record.kind === 'symbol' && !/^[a-z][a-z0-9-]*$/.test(record.symbol))
    throw new Error(`Invalid library symbol: ${name}`)
  return Object.freeze({
    ...record,
    asset,
    url: record.kind === 'symbol' ? `${asset.url}#${record.symbol}` : asset.url,
  })
}

export { catalog as libraryCatalog }
