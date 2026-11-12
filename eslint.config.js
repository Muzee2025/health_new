// ESLint flat config for 心域智链 (Vue 3 + Vitest).
// Phase 1 scope: .js / .mjs / .ts / .vue under src/ and scripts/, plus public/sw.js.
// Out of scope on purpose: docs/ (documentation + design reference sources),
// backend/ (own lint via Ruff), generated assets and tmp/.
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import vitest from '@vitest/eslint-plugin'
import tseslint from 'typescript-eslint'
import globals from 'globals'

export default [
  {
    name: 'xinyu/ignores',
    ignores: [
      'node_modules/**',
      'dist/**',
      'coverage/**',
      'tmp/**',
      'deliverables/**',
      'backend/**',
      'docs/**',
      '.venv/**',
      'venv/**',
      'scripts/archive/**',
      'src/assets/**',
      'public/assets/**',
    ],
  },
  js.configs.recommended,
  // typescript-eslint presets are scoped to .ts files only: the Vue SFCs use
  // plain <script>, and scoping keeps the JS rules untouched.
  ...tseslint.configs.recommended.map((config) => ({ ...config, files: ['**/*.ts'] })),
  // `flat/essential` only: the `recommended` preset also ships template
  // formatting rules (max-attributes-per-line, html-indent, ...) that fight
  // Prettier — formatting is Prettier's job here.
  ...pluginVue.configs['flat/essential'],
  {
    name: 'xinyu/browser',
    files: ['src/**/*.{js,ts,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser },
    },
  },
  {
    name: 'xinyu/node-scripts',
    // Capture/check scripts drive Playwright, so their `page.evaluate()`
    // callbacks run against browser globals as well.
    files: ['scripts/**/*.mjs', 'vite.config.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.node, ...globals.browser },
    },
  },
  {
    name: 'xinyu/service-worker',
    files: ['public/sw.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'script',
      globals: { ...globals.serviceworker, ...globals.browser },
    },
  },
  {
    name: 'xinyu/vitest',
    // Only vitest-owned tests. scripts/tests/ runs under `node --test`
    // (see package.json "assets:source-test"), so it must NOT get vitest rules.
    files: ['**/*.{test,spec}.{js,ts}'],
    plugins: { vitest },
    languageOptions: {
      globals: { ...vitest.environments.env.globals },
    },
    rules: { ...vitest.configs.recommended.rules },
  },
  {
    // Shared tuning for the unused-code family. `caughtErrors: 'none'` restores
    // the pre-ESLint-9 default: a defensive `catch (e) {}` that only wants to
    // keep the flow going is normal, not dead code.
    // `ignoreRestSiblings` is what makes the omit idiom `({ content, ...rest })`
    // legal — `content` is named only to be excluded from the rest object.
    name: 'xinyu/unused-vars-js',
    files: ['**/*.{js,mjs,vue}'],
    rules: {
      'no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrors: 'none',
          ignoreRestSiblings: true,
        },
      ],
      // Empty catch is the deliberate "best effort, ignore failure" form used
      // across the capture/check scripts and the IndexedDB abort path.
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    // Same tuning for TypeScript, but through the TS-aware rule. Using the base
    // rule on .ts re-enables it over typescript-eslint's own and misreports
    // parameter names that only exist in type signatures.
    name: 'xinyu/unused-vars-ts',
    files: ['**/*.ts'],
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrors: 'none',
          ignoreRestSiblings: true,
        },
      ],
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    name: 'xinyu/overrides',
    rules: {
      // The repo names single-word views (Layout.vue, Login.vue, ...); renaming
      // them is a refactor decision, not a lint fix. Revisit in phase 2.
      'vue/multi-word-component-names': 'off',
    },
  },
]
