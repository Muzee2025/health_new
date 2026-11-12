// Build isolated production artifacts plus module-origin metadata for request QA.
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
import { build } from 'vite'
const root = process.cwd()
const output = path.resolve(process.env.PERF_BUILD_OUTPUT || 'tmp/frontend-audit')
assert(
  output.startsWith(path.resolve(root, 'tmp') + path.sep),
  'Audit builds belong in ignored tmp',
)
assert(!fs.existsSync(output), 'Audit output must be a new path; existing evidence is retained')
await build({
  build: { outDir: output, emptyOutDir: false, manifest: true },
  plugins: [
    {
      name: 'record-module-origins',
      generateBundle(_options, bundle) {
        const report = {}
        for (const [name, item] of Object.entries(bundle))
          if (item.type === 'chunk') {
            const ids = Object.keys(item.modules).map((id) => id.replaceAll('\\', '/'))
            const kinds = []
            if (ids.some((id) => id.includes('/node_modules/echarts/'))) kinds.push('echarts')
            if (ids.some((id) => id.includes('/node_modules/zrender/'))) kinds.push('zrender')
            if (ids.some((id) => id.includes('/node_modules/chart.js/'))) kinds.push('chartjs')
            if (ids.some((id) => id.includes('/node_modules/element-plus/')))
              kinds.push('element-plus')
            report[name] = {
              kinds,
              imports: item.imports,
              dynamicImports: item.dynamicImports,
              moduleCount: ids.length,
            }
          }
        this.emitFile({
          type: 'asset',
          fileName: '.vite/module-origins.json',
          source: JSON.stringify(report, null, 2),
        })
      },
    },
  ],
})
