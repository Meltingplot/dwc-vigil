import { fileURLToPath } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'
import { dwcVitestConfig } from 'dwc-plugin-test-kit/vitest'

/**
 * Vitest covers the two halves of the plugin that run on Vue 3: the shared,
 * framework-neutral `src/core/` and the DWC 3.7 shell in `src/ui37/`.
 *
 * `src/ui36/` is NOT here — it is Vue 2.7 and has its own nested Jest project under
 * tests/ui36/ (`npm run test:ui36`), because one package.json cannot hold both Vue
 * majors and the root has to be the Vue 3 one: it is what DWC 3.7's plugin builder
 * reads and installs from.
 *
 * dwc-plugin-test-kit supplies the config: the `@/…` → stub aliases standing in for the
 * modules DWC 3.7 externalises, happy-dom, and a deduped single copy of Vue/Vuetify.
 */
const config = dwcVitestConfig({
    // vue() comes from here rather than from the kit so it resolves against this
    // repo's own node_modules.
    plugins: [vue()],
    test: {
        // The kit defaults to TypeScript sources; Vigil is plain JS.
        include: ['tests/core/**/*.test.js', 'tests/ui37/**/*.test.js'],
        coverage: {
            include: ['src/core/**', 'src/ui37/**'],
        },
    },
})

// The kit's machine stub has no startSbcPlugin, which is the one machine-store action
// Vigil uses. Patch the alias rather than passing a `resolve` override, which would
// replace the kit's dedupe list along with its aliases.
config.resolve.alias['@/stores/machine'] = fileURLToPath(
    new URL('./tests/dwc-stubs/machine.js', import.meta.url),
)

export default defineConfig(config)
