#!/usr/bin/env node
/**
 * Compile every `src/ui36/**.vue` with DuetWebControl 3.6's OWN Vue 2.7 compiler.
 *
 * Why this exists: once the repo root carries the Vue 3 toolchain, nothing in it can
 * even parse a Vue 2 SFC, so `ui36/`'s only automated safety net would be the full
 * webpack build — which takes minutes and needs more RAM than it can always get.
 *
 * This is the cheap net underneath that: it runs in about a second and catches what a
 * hand-written Vue 2 template actually gets wrong — malformed markup, unclosed tags,
 * bad interpolation expressions, `<script setup>` that Vue 2.7 cannot compile.
 *
 * What it deliberately does NOT catch, so nobody mistakes a pass for a green light:
 *   - wrong Vuetify 2 prop or slot NAMES (e.g. Vuetify 4's `density` or `variant`
 *     surviving a translation). Those are valid markup; only the running component
 *     knows they are wrong.
 *   - module resolution errors — that is the webpack build's job (ci-local.sh build36).
 * A pass here means "this will compile", not "this will render correctly".
 *
 *   DWC36_DIR=/path/to/DuetWebControl-3.6  node scripts/check-ui36.mjs
 */
import { createRequire } from 'node:module'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dwcDir = process.env.DWC36_DIR

if (!dwcDir || !existsSync(dwcDir)) {
    console.error(
        'DWC36_DIR is not set or does not exist. Point it at a DuetWebControl 3.6 checkout\n'
        + 'with dependencies installed — this borrows its Vue 2.7 compiler, which the plugin\n'
        + 'itself cannot depend on (the repo root builds against Vue 3 for the 3.7 package).\n'
        + 'scripts/ci-local.sh build36 keeps such a checkout in .ci-local/DuetWebControl-36.',
    )
    process.exit(2)
}

const compilerPath = join(dwcDir, 'node_modules', 'vue', 'compiler-sfc')
if (!existsSync(compilerPath)) {
    console.error(`No Vue 2.7 compiler at ${compilerPath} — run npm install in the DWC 3.6 checkout.`)
    process.exit(2)
}

const sfc = createRequire(import.meta.url)(compilerPath)

/** Every .vue file below src/ui36, in a stable order. */
function collect(dir) {
    if (!existsSync(dir)) {
        return []
    }
    const files = []
    for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
        const full = join(dir, entry.name)
        if (entry.isDirectory()) {
            files.push(...collect(full))
        } else if (entry.name.endsWith('.vue')) {
            files.push(full)
        }
    }
    return files
}

const root = join(repo, 'src', 'ui36')
const files = collect(root)
if (files.length === 0) {
    console.error(`No .vue files in ${root}.`)
    process.exit(2)
}

let failed = 0
for (const file of files) {
    const name = relative(repo, file)
    const source = readFileSync(file, 'utf8')
    // Scoped-style id; also what compileScript/compileTemplate use to correlate output.
    const id = `data-v-${name.replace(/\W/g, '')}`
    try {
        // NB: Vue 2.7's parse() returns the descriptor DIRECTLY. Vue 3 wraps it as
        // { descriptor, errors }, so code copied from a Vue 3 project silently reads
        // undefined here and "fails" every file.
        const descriptor = sfc.parse({ source, filename: name })
        if (descriptor.errors?.length) {
            throw new Error(descriptor.errors.map((e) => e.msg ?? e.message ?? String(e)).join('; '))
        }
        if (descriptor.scriptSetup) {
            sfc.compileScript(descriptor, { id })
        }
        if (descriptor.template) {
            const result = sfc.compileTemplate({ source: descriptor.template.content, filename: name, id })
            if (result.errors?.length) {
                throw new Error(result.errors.map(String).join('; '))
            }
            for (const tip of result.tips ?? []) {
                console.log(`  ~    ${name}: ${tip}`)
            }
        }
        console.log(`  OK   ${name}`)
    } catch (e) {
        failed++
        console.log(`  FAIL ${name}: ${e instanceof Error ? e.message : String(e)}`)
    }
}

console.log(`\n${files.length - failed}/${files.length} DWC 3.6 SFCs compiled with Vue 2.7.`)
if (failed > 0) {
    process.exit(1)
}
console.log('Compiles only — Vuetify 2 prop/slot correctness still needs a real DWC 3.6.')
