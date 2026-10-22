import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { inspectDesignSources } from '../check-design-sources.mjs';

const scratch = fileURLToPath(new URL('../../tmp/design-source-fixtures/', import.meta.url));
fs.mkdirSync(scratch, { recursive: true });
function fixture() {
  const root = fs.mkdtempSync(path.join(scratch, 'case-'));
  const write = (name, content) => {
    const target = path.join(root, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content);
  };
  const svg = '<svg xmlns="http://www.w3.org/2000/svg"><symbol id="assessment" /></svg>';
  write('src/assets/icons/icon-fixture.svg', svg);
  const entry = { id: 'icon-fixture', path: 'icons/icon-fixture.svg', status: 'approved', license: 'LicenseRef-Project-Original', source: 'Synthetic test fixture', sha256: crypto.createHash('sha256').update(svg).digest('hex') };
  const manifest = { assets: [entry, { ...entry, id: 'legacy-fixture', status: 'legacy-unverified' }] };
  const catalog = { schemaVersion: 1, assets: { brandLogo: entry.id }, icons: { assessment: { kind: 'symbol', assetId: entry.id, symbol: 'assessment' } }, charts: { styleSource: 'docs/design/chart-style.js', optionSource: 'docs/design/chart-options.js', cssSource: 'docs/design/chart-surfaces.css', dataPolicy: 'business-api-only' } };
  for (const name of ['styleSource', 'optionSource', 'cssSource']) write(catalog.charts[name], '/* synthetic shared source */');
  const save = () => {
    write('src/assets/manifest.json', JSON.stringify(manifest));
    write('src/design/library-catalog.json', JSON.stringify(catalog));
  };
  save();
  return { root, write, catalog, manifest, save };
}

test('approved library visuals coexist with dynamic business data', () => {
  const f = fixture();
  f.write('src/views/Example.vue', '<template><LibraryIcon name="assessment"/><img :src="article.cover_url || logo.url"/></template><script setup>const logo=getVisualAsset("brandLogo"); const series=apiRecords.map(record=>record.value)</script>');
  assert.equal(inspectDesignSources(f.root).status, 'passed');
});

test('legacy IDs fail even when their bytes equal an approved file', () => {
  const f = fixture();
  f.catalog.assets.brandLogo = 'legacy-fixture';
  f.save();
  assert.ok(inspectDesignSources(f.root).errors.some(error => error.code === 'ASSET_NOT_APPROVED'));
});

test('unknown sprite symbols and changed approved bytes are rejected', () => {
  const f = fixture();
  f.catalog.icons.assessment.symbol = 'missing-symbol';
  f.write('src/assets/icons/icon-fixture.svg', '<svg/>');
  f.save();
  const codes = inspectDesignSources(f.root).errors.map(error => error.code);
  assert.ok(codes.includes('SYMBOL_UNKNOWN'));
  assert.ok(codes.includes('ASSET_HASH_CHANGED'));
});

test('asset paths cannot leave the library directory', () => {
  const f = fixture();
  f.manifest.assets[0].path = '../../outside.svg';
  f.save();
  assert.ok(inspectDesignSources(f.root).errors.some(error => error.code === 'ASSET_SOURCE_INVALID'));
});

test('page-authored icons, static colors, direct assets and demo imports fail', () => {
  const f = fixture();
  f.write('src/views/Bypass.vue', '<template><svg><path/></svg><span style="color:#123456">📈</span><LibraryIcon name="unknown"/></template><script setup>import logo from "../assets/unregistered.svg"; import { getChartDemoData } from "../../docs/design/chart-demo-data.js"; const image=getVisualAsset("unknown"); chart.setOption({series:[]})</script>');
  const codes = inspectDesignSources(f.root).errors.map(error => error.code);
  for (const code of ['DIRECT_ASSET_REFERENCE', 'INLINE_SVG', 'INLINE_COLOR', 'DECORATIVE_EMOJI', 'DEMO_DATA_IN_BUSINESS', 'RAW_CHART_OPTION', 'ASSET_ROLE_UNKNOWN', 'ICON_ROLE_UNKNOWN']) assert.ok(codes.includes(code), code);
});

test('URL constructors and removed global icon tags cannot bypass the registry', () => {
  const f = fixture();
  f.write('src/views/Legacy.vue', '<template><el-icon><arrow-down/></el-icon><el-empty/></template><script setup>const url=new URL("../assets/unregistered.svg",import.meta.url)</script>');
  const codes = inspectDesignSources(f.root).errors.map(error => error.code);
  for (const code of ['DIRECT_ASSET_REFERENCE', 'UNREGISTERED_ICON_COMPONENT', 'DEFAULT_EMPTY_ART']) assert.ok(codes.includes(code), code);
});

test('PascalCase component names have the same source rules', () => {
  const f = fixture();
  f.write('src/views/CaseVariant.vue', '<template><ElIcon><ArrowDown/></ElIcon><ElEmpty/><library-icon name="unknown"/></template>');
  const codes = inspectDesignSources(f.root).errors.map(error => error.code);
  for (const code of ['UNREGISTERED_ICON_COMPONENT', 'DEFAULT_EMPTY_ART', 'ICON_ROLE_UNKNOWN']) assert.ok(codes.includes(code), code);
});
