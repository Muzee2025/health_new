// CLI-only loader. Importing this module does not load optional packages or run a script.
import { createRequire } from 'node:module'
import { basename, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const definitions = {
  playwright: {
    env: 'PLAYWRIGHT_MODULE_PATH',
    valid: (value) => typeof value?.chromium?.launch === 'function',
  },
  sharp: {
    env: 'SHARP_MODULE_PATH',
    valid: (value) => typeof value === 'function',
  },
}
const knownErrorCodes = new Set([
  'MODULE_NOT_FOUND',
  'ERR_PACKAGE_PATH_NOT_EXPORTED',
  'ERR_REQUIRE_ESM',
  'ERR_DLOPEN_FAILED',
  'ERR_INVALID_ARG_TYPE',
])

/**
 * Resolve and load dependencies before the caller reads inputs or writes output.
 * Explicit paths take precedence over normal Node resolution (including NODE_PATH).
 * A broken explicit path never silently falls back to another installation.
 * --check-deps reports package availability and exits before the caller's main work;
 * it does not launch a browser or check whether a browser executable is installed.
 */
export function loadScriptDependencies(moduleUrl, names, { playwrightAliases = [] } = {}) {
  const require = createRequire(moduleUrl)
  const modules = {}
  const checks = names.map((name) => {
    if (!Object.hasOwn(definitions, name)) throw new Error('Unknown script dependency')
    const definition = definitions[name]
    const envNames = [definition.env, ...(name === 'playwright' ? playwrightAliases : [])]
    const selectedEnv = envNames.find((key) => process.env[key])
    const check = {
      name,
      available: false,
      source: selectedEnv || 'node-resolution',
      env: definition.env,
      phase: 'resolve',
    }
    try {
      const entry = require.resolve(selectedEnv ? resolve(process.env[selectedEnv]) : name)
      check.phase = 'load'
      const loaded = require(entry)
      check.phase = 'exports'
      if (!definition.valid(loaded)) {
        check.code = 'INVALID_EXPORTS'
        return check
      }
      modules[name] = loaded
      check.available = true
      delete check.phase
    } catch (error) {
      // Report only known codes and variable names, never configured values or raw stacks.
      check.code = knownErrorCodes.has(error?.code) ? error.code : 'LOAD_ERROR'
    }
    return check
  })
  const ok = checks.every((check) => check.available)
  const checkOnly = process.argv.includes('--check-deps')
  if (checkOnly) {
    console.log(
      JSON.stringify({
        script: basename(fileURLToPath(moduleUrl)),
        checkOnly: true,
        ok,
        dependencies: checks,
      }),
    )
  }
  if (!ok) {
    for (const check of checks.filter((item) => !item.available)) {
      console.error(
        `[dependencies] ${check.name}: ${check.phase}/${check.code}. ` +
          `Set ${check.env} to an existing module directory or entry file, ` +
          'or use a working local/NODE_PATH installation. No install is performed.',
      )
    }
  }
  // Stopping here is intentional: exitCode alone would continue top-level builds/captures.
  if (checkOnly || !ok) process.exit(ok ? 0 : 2)
  return modules
}
