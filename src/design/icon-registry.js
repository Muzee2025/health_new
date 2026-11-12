// @ts-nocheck
// Browser-side design reference source, not application code: the icon map is
// built by re-exporting Element Plus icon components through a data-driven
// lookup, whose inferred `export`/`source` members are not visible to
// TypeScript. Excluded from type checking on purpose; icon registration is
// covered by `npm run assets:check`.
import { defineComponent, h } from 'vue'
import {
  House,
  Search,
  ArrowLeft,
  ArrowDown,
  Location,
  View,
  Collection,
  QuestionFilled,
  SwitchButton,
  User,
  Star,
  StarFilled,
  Plus,
} from '@element-plus/icons-vue'
import { getLibraryIconRecord, libraryCatalog } from './asset-registry'

const controls = Object.freeze({
  House,
  Search,
  ArrowLeft,
  ArrowDown,
  Location,
  View,
  Collection,
  QuestionFilled,
  SwitchButton,
  User,
  Star,
  StarFilled,
  Plus,
})
for (const record of Object.values(libraryCatalog.icons)) {
  if (
    record.kind === 'element-plus' &&
    (!controls[record.export] || record.source !== '@element-plus/icons-vue')
  )
    throw new Error('Invalid standard library icon registration')
}

export function renderLibraryIcon(name, attrs = {}) {
  const record = getLibraryIconRecord(name)
  const common = {
    'aria-hidden': 'true',
    ...attrs,
    class: ['library-icon', attrs.class],
    'data-library-icon': name,
    'data-library-source': record.assetId || record.source,
  }
  if (record.kind === 'element-plus') return h('span', common, [h(controls[record.export])])
  if (record.kind === 'symbol')
    return h('svg', { ...common, viewBox: '0 0 24 24' }, [h('use', { href: record.url })])
  return h('span', {
    ...common,
    style: [
      attrs.style,
      { maskImage: `url("${record.url}")`, WebkitMaskImage: `url("${record.url}")` },
    ],
    class: ['library-icon', 'library-icon--asset', attrs.class],
  })
}

// Component-valued props (Element Plus timeline) still resolve through the catalog.
export function createLibraryIconComponent(name) {
  getLibraryIconRecord(name)
  return defineComponent({
    name: 'CatalogIcon',
    inheritAttrs: false,
    setup:
      (_props, { attrs }) =>
      () =>
        renderLibraryIcon(name, attrs),
  })
}

export const interventionIcon = createLibraryIconComponent('support')
