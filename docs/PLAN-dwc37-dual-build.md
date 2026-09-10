# Plan: dual DWC 3.6 / 3.7 builds for Vigil

**Status:** proposal, nothing implemented yet.
**Reference implementation:** [jaysuk/ClosedLoopTuningPlugin](https://github.com/jaysuk/ClosedLoopTuningPlugin)
(`docs/PLAN-dwc36-backport.md`, `scripts/stage-dwc36.mjs`, `src/core/host.ts`, `src/ui36/`, `src/ui37/`,
`.github/workflows/release.yml`). Read those files before implementing; this plan describes how to apply
their pattern to Vigil, not how to invent a new one.

Findings below were verified against the actual sources on 2026-09-10: the ClosedLoopTuning repo,
`Duet3D/DuetWebControl` at `v3.6-dev` and `v3.7-dev` (`scripts/build-plugin-pkg.js`, `PLUGINS.md`,
`src/plugins/index.ts`, `src/stores/machine.ts`), and `jaysuk/dwc-plugin-test-kit`.

---

## 0. Why this is two builds, not one

DWC 3.6 and 3.7 are different framework stacks. A plugin ZIP built for one does not load on the other,
and DWC refuses to install it (`checkVersion` compares `dwcVersion` major.minor).

| | DWC 3.6 | DWC 3.7 |
|---|---|---|
| Framework | Vue **2.7** (Options API) | Vue **3.5** |
| UI | Vuetify **2.7** | Vuetify **4** |
| State | Vuex 3 (`@/store`) | Pinia (`@/stores/machine`) |
| Plugin API | `registerRoute` from `@/routes` | `registerRoute`, `unregisterRoute`, `registerPluginMessages` from `@/plugins` (or `"DuetWebControl"`) |
| Build | vue-cli / webpack: `npm run build-plugin-pkg -- <dir>` in the DWC checkout, ZIP lands in `DuetWebControl/dist/` | Vite 8 IIFE bundle: `node scripts/build-plugin-pkg.js <dir>`, ZIP lands in `<dir>/<id>-<ver>.zip` (plus `-srcmap.zip`) |
| Node | 18 works | Vite 8 needs Node ≥ 22 |
| chart.js in the checkout | 2.9 | 4.5 (but **not** externalised — a plugin must bundle its own) |
| Plugin npm deps | not installed by the builder | builder runs `npm install` in the plugin dir for anything missing, bundles `dependencies` into the IIFE |
| `dsf/` directory | copied into the ZIP, `dsfFiles` populated | same |
| `dwcVersion` / `sbcDsfVersion: "auto-major"` | resolved to `3.6` | resolved to `3.7` |

The important consequences for Vigil:

- **The Python daemon needs no change for the packaging.** Both builders copy `dsf/` verbatim and fill
  in `dsfFiles`. See §7.6 for the DSF 3.7 runtime caveat, which is a separate concern.
- **All data flow already bypasses the DWC store.** The dashboard talks to the daemon over plain
  `fetch('/machine/Vigil/…')`; that is DSF's HTTP endpoint mechanism and is identical on both
  generations. The only DWC coupling on the frontend is:
  - `registerRoute` (entry point),
  - reading `plugins.get('Vigil').pid` from the object model (backend running?),
  - dispatching `machine/startSbcPlugin` (backend recovery after an upgrade).
  That is the entire "host" surface: three calls. ClosedLoopTuning's adapter has ten.
- **The "partially started after upgrade" workaround stays relevant on 3.7.** DSF still re-registers
  with `pid = -1`, and DWC 3.7's install wizard has a "start when finished" checkbox that defaults to
  off. `startSbcPlugin(plugin: string)` exists on the 3.7 Pinia machine store.

---

## 1. How ClosedLoopTuning does it (the pattern to copy)

```
src/
  index.ts        →  export * from "./ui37/index";      # what a 3.7 checkout builds
  model/, core/   →  framework-neutral logic + i18n     # shipped to BOTH generations unchanged
  core/host.ts    →  HostAdapter interface: no Vue types cross it
  ui37/           →  Vue 3 shell: index.ts, host.ts (Pinia), *.vue (Vuetify 4)
  ui36/           →  Vue 2.7 shell: index.ts, host.ts (Vuex), *.vue (Vuetify 2)
scripts/
  stage-dwc36.mjs →  copies model/ core/ i18n/ ui36/ into a temp tree, writes a one-line
                     src/index.ts → "./ui36/index", vendors chart.js 4 (+ its dependency closure)
                     into <stage>/src/node_modules/ so webpack finds it before DWC 3.6's chart.js 2.9,
                     copies plugin.json unchanged
  check-ui36.mjs  →  compiles every ui36/*.vue with the 3.6 checkout's Vue 2.7 compiler-sfc (~1 s)
```

- **One `plugin.json`**, `dwcVersion: "auto-major"`; each builder stamps its own major.minor. There is
  no second manifest to keep in sync.
- **3.7 build**: DWC 3.7's builder pointed straight at the repo. Its own npm deps (`chart.js`) come
  from the plugin's `package.json` and are bundled.
- **3.6 build**: stage → `npm run build-plugin-pkg -- <stage>` in the 3.6 checkout → rename the result
  to `<id>-<ver>-dwc36.zip`.
- **One release workflow, one tag, two ZIPs** attached to the same GitHub Release. The 3.6 half is
  guarded on `src/ui36` existing so the pipeline worked before the backport landed.
- **Tests**: vitest + `dwc-plugin-test-kit` cover the shared logic and the Vue 3 shell; `ui36` only
  gets the compile check (`check-ui36`) plus the real 3.6 build, and is excluded from the Vue 3
  type check via `"dwcTypecheckIgnore": ["ui36"]`. They accept that as a known gap (their §7.2).
- **Self-updater** narrows release assets per generation (`assetPattern`). Vigil has no self-updater,
  so this part does not apply.

---

## 2. Where Vigil differs (and what that changes)

| ClosedLoopTuning | Vigil | Consequence |
|---|---|---|
| 3.7 first, 3.6 backported | 3.6 today, 3.7 is the new work | Phase order is inverted: the existing code *is* `ui36/`; the new shell is `ui37/` |
| TypeScript, `<script setup>` | plain JS, Options API | No type checking either way; DWC 3.7's `typeCheckPlugin` skips pure-JS plugins. Keep Options API in `ui37/` too (Vue 3 supports it) so the two shells' `<script>` blocks stay near-identical and the diff is mostly templates |
| DWC-only plugin | ships `dsf/` + Python daemon | Packaging is handled by both builders. Daemon must be verified against dsf-python 3.7 (§7.6) |
| brings chart.js 4 | uses DWC 3.6's chart.js 2.9 via bare `import Chart from 'chart.js'` | Vigil must own a chart.js dependency for 3.7. Recommended: migrate the four charts to the chart.js 4 API once, in shared code, and vendor chart.js 4 into the 3.6 build exactly like upstream (§4) |
| vitest / Vue 3 tests only | Jest + `@vue/vue2-jest` + Vuex store mocks, 60 frontend tests | Vue 2 and Vue 3 cannot both be `vue` in one `package.json`. Needs a decision (§5) |
| i18n via `registerPluginMessages` / `mergeLocaleMessage` | literal captions, `translated: true` | Simpler: 3.7's `registerRoute` supports `translated` the same way. No i18n work required |
| `build.bat` / `build36.bat` | `scripts/build-zip.js` (raw-source ZIP, not installable) + `version.js` | Replace `build-zip.js` with real builds via the two DWC checkouts; keep `version.js --write` and run it before both builds |
| Release names: `<id>-<ver>.zip` = 3.7, `-dwc36.zip` = 3.6 | existing users download `Vigil-<ver>.zip` for 3.6 | Recommend explicit suffixes for **both** (`Vigil-<ver>-dwc36.zip`, `Vigil-<ver>-dwc37.zip`) so a 3.6 user's habit does not hand them the wrong file. DWC rejects the wrong one anyway, but only after the upload |

---

## 3. Target layout

```
src/
  index.js                  import './ui37/index'         (DWC 3.7's findEntryFile picks src/index.js;
                                                           the 3.6 stage script generates its own)
  core/                     framework-neutral, shipped to both, unit-tested once
    host.js                 JSDoc HostAdapter: { pluginEntry(): object|null, startBackend(): Promise }
    backend.js              today's src/backend.js, refactored to take a HostAdapter instead of a Vuex store
    api.js                  apiGet / apiPost / downloadBlob / waitForBackend (extracted from VigilDashboard.vue)
    charts.js               chart.js 4 registration + config builders for pie/heater/fan/history charts
    format.js               time / distance formatting (from StatCard, AxisTable)
  ui36/                     Vue 2.7 + Vuetify 2 (today's files, moved)
    index.js                registerRoute from '@/routes'; ensureBackendRunning(createHost())
    host.js                 Vuex adapter over '@/store'
    VigilDashboard.vue
    components/*.vue
  ui37/                     Vue 3 + Vuetify 4 (new)
    index.js                registerRoute / unregisterRoute from '@/plugins'; Events.on('dwcPluginUnloaded')
    host.js                 Pinia adapter over useMachineStore()
    VigilDashboard.vue
    components/*.vue
dsf/                        unchanged
scripts/
  version.js                unchanged
  stage-dwc36.mjs           adapted from upstream: INCLUDE = ["core", "ui36"], VENDOR = ["chart.js"]
  check-ui36.mjs            adapted verbatim (DWC36_DIR)
  build36.sh / build37.sh   local convenience wrappers (upstream has .bat; we want POSIX)
tests/
  core/*.test.js            vitest, no Vue
  ui37/*.test.js            vitest + dwc-plugin-test-kit (mountInDwc, setModel)
  ui36/                     nested npm project holding today's Jest suite (see §5)
  test_*.py                 unchanged
```

`src/routes.js`, `src/store.js`, `src/__mocks__/` (Jest stubs for `@/routes` and `@/store`) move into
`tests/ui36/` with the Jest config that needs them. They must never be in `src/` once the 3.7 builder
is pointed at the repo: DWC 3.7 externalises `@/…` imports, but a stray `src/store.js` is harmless
only by luck.

### 3.1 The host adapter (three members)

```js
// src/core/host.js — documentation only, no code crosses this boundary except plain values/promises
/**
 * @typedef {object} HostAdapter
 * @property {() => (object|null)} pluginEntry  Live reactive read of model.plugins.get('Vigil').
 *   MUST read through the store on every call (never cache) so a computed/watch that calls it
 *   re-evaluates when DSF reports a new pid.
 * @property {() => Promise<void>} startBackend  machine store's startSbcPlugin('Vigil').
 */
```

```js
// src/ui36/host.js
import store from '@/store'
export function createHost() {
  return {
    pluginEntry: () => {
      const plugins = store.state.machine?.model?.plugins
      return plugins instanceof Map ? plugins.get(PLUGIN_ID) ?? null : plugins?.[PLUGIN_ID] ?? null
    },
    startBackend: () => Promise.resolve(store.dispatch('machine/startSbcPlugin', PLUGIN_ID)),
  }
}
```

```js
// src/ui37/host.js
import { useMachineStore } from '@/stores/machine'
export function createHost() {
  const machine = () => useMachineStore()   // resolve per call: safe at plugin-load time and in components
  return {
    pluginEntry: () => machine().model.plugins.get(PLUGIN_ID) ?? null,
    startBackend: () => machine().startSbcPlugin(PLUGIN_ID),
  }
}
```

`VigilDashboard.vue` in both shells replaces `mapState('machine/model', …)` with a computed that
calls `host.pluginEntry()`. Vuex and Pinia both track the read, so `backendRunning` stays reactive
and the existing `watch: { backendRunning }` keeps working. `isBackendRunning(pluginEntry)` in
`core/backend.js` becomes a pure function of the entry, which also simplifies its tests.

---

## 4. chart.js: migrate once to v4, vendor into 3.6

Today's four chart components use the chart.js **2.9** API (`scales.xAxes[]`, `scaleLabel.labelString`,
`ticks.beginAtZero`, top-level `legend`, `chart.config.options.scales.yAxes[0]…` mutation) and get
chart.js from DWC 3.6's `node_modules`. DWC 3.7 does not externalise chart.js at all (it is not in
`PLUGIN_GLOBALS`), so a 3.7 build with a bare `import Chart from 'chart.js'` fails to resolve unless the
plugin declares the dependency, and the version it then gets is whatever we declare.

Two options:

1. **Keep chart.js 2 for `ui36/`, write chart.js 4 configs for `ui37/`.** Two sets of chart code,
   diverging forever. Rejected.
2. **Migrate to chart.js 4 once in `src/core/charts.js`** (config builders returning plain objects;
   registration via `chart.js/auto`), use it from both shells, and vendor chart.js 4 + its dependency
   closure (`@kurkle/color`) into the staged 3.6 tree exactly as upstream does. **Recommended.** The
   4 KB of chart config becomes unit-testable without a DOM, and the 3.6 bundle simply carries its
   own chart.js (~70 KB gzipped) instead of sharing DWC's.

Why vendoring instead of `npm install chart.js@4` in the 3.6 checkout: DWC 3.6's own temperature and
layer charts are written against 2.9 and would break. Webpack resolves packages by walking up from the
importing file, so `<stage>/src/node_modules/chart.js` wins for our files only.

API translation to apply in `core/charts.js`:

| chart.js 2.9 (today) | chart.js 4 |
|---|---|
| `import Chart from 'chart.js'` | `import Chart from 'chart.js/auto'` (in `core/charts.js` only) |
| `scales: { xAxes: [{…}], yAxes: [{…}] }` | `scales: { x: {…}, y: {…} }` |
| `scaleLabel: { display, labelString }` | `title: { display, text }` |
| `ticks: { beginAtZero: true }` | `beginAtZero: true` on the scale |
| `legend: {…}`, `tooltips: {…}` | `plugins: { legend: {…}, tooltip: {…} }` |
| `type: 'horizontalBar'` | `type: 'bar'`, `indexAxis: 'y'` |
| `options.scales.yAxes[0].scaleLabel.labelString = …` | `options.scales.y.title.text = …` |

DWC 3.7's in-tree `InputShaping` plugin is the reference for Chart.js v4 usage inside DWC.

---

## 5. Test toolchain: the one decision that must be made up front

`@vue/vue2-jest`, `vue-template-compiler` and `@vue/test-utils@1` require `vue@2.7` at the package root.
`dwc-plugin-test-kit`, `@vue/test-utils@2` and `vuetify@4` require `vue@3`. One `package.json` cannot
satisfy both, and the root `package.json` is also what DWC 3.7's builder reads (it runs `npm install`
in the plugin dir for anything missing and bundles `dependencies`), so the root must be the Vue 3 one.

| Option | Verdict |
|---|---|
| **A. Root = Vue 3 toolchain (vitest, test-kit); today's Jest/Vue 2 suite moves to a nested project `tests/ui36/package.json` with its own lockfile and `node_modules`** | **Recommended.** Keeps all 60 existing frontend tests, including the backend-recovery ones which are the most valuable. CI runs `npm ci && npm test` in both. Costs one extra `npm ci` (~30 s) |
| B. Drop the Vue 2 component tests; keep only `check-ui36.mjs` + the real 3.6 build (what upstream does) | Loses `VigilDashboard.test.js`. Acceptable only if A proves unworkable |
| C. npm alias (`"vue2": "npm:vue@2.7"`) and remap in Jest | `vue2-jest` resolves `vue/compiler-sfc` by bare name; fragile. Rejected |

Under A the split is:

- `tests/core/` — vitest, no Vue, imports `src/core/*` directly (`backend.test.js` ports 1:1,
  `jest.fn` → `vi.fn`).
- `tests/ui37/` — vitest + `dwc-plugin-test-kit`: `mountInDwc(VigilDashboard)`, `setModel({ plugins:
  new Map([['Vigil', { pid: -1 }]]) })`, assert the warning banner and that `startSbcPlugin` is invoked.
  Check whether the kit's fake machine store exposes `startSbcPlugin`; if not, stub it via `dwc`.
- `tests/ui36/` — the current Jest suite, moved, with `jest.config.js`, `setup.js`, the `@/routes` and
  `@/store` stubs, and a `moduleNameMapper` entry `'^@/(.*)$': '<rootDir>/../../src/ui36/$1'` plus
  `'^chart\\.js/auto$'` → the existing chart mock.

Root `package.json` after the split:

```jsonc
{
  "dependencies": { "chart.js": "^4.5.0" },                 // bundled into the 3.7 IIFE, vendored into 3.6
  "devDependencies": {
    "vitest", "@vue/test-utils": "^2", "vue": "^3.5", "vuetify": "^4", "@vitejs/plugin-vue",
    "happy-dom", "dwc-plugin-test-kit", "eslint", "eslint-plugin-vue", "vue-eslint-parser"
  },
  "scripts": {
    "lint": "eslint src/ --ext .js,.vue",
    "test": "vitest run",
    "test:ui36": "npm --prefix tests/ui36 test",
    "check-ui36": "node scripts/check-ui36.mjs",
    "stage-dwc36": "node scripts/stage-dwc36.mjs"
  }
}
```

ESLint: `plugin:vue/recommended` (Vue 3 rules) for `src/ui37/` and `src/core/`, an override with
`plugin:vue/vue2-recommended` for `src/ui36/**`.

---

## 6. Phases

Each phase is independently committable and leaves the 3.6 ZIP installable.

### Phase 0 — host seam, no behaviour change (3.6 only)
1. Add `src/core/host.js` (JSDoc), `src/core/backend.js` taking a host, `src/core/api.js`.
2. `src/index.js`: `ensureBackendRunning(createHost())`; `VigilDashboard.vue`: computed
   `backendRunning` via `host.pluginEntry()` instead of `mapState`.
3. Tests: `backend.test.js` switches from a fake Vuex store to a fake host (smaller, clearer).
4. **Verify:** `npm test`, `npm run lint`, full 3.6 build via a real `v3.6-dev` checkout, install on a
   3.6 DWC, confirm the banner + Start Backend still work after a plugin upgrade.

### Phase 1 — directory restructure + 3.6 staging
1. Move today's Vue files to `src/ui36/`, entry to `src/ui36/index.js`; `src/index.js` becomes
   `import './ui36/index'` **for now** (flipped to `ui37` in Phase 4).
2. Add `scripts/stage-dwc36.mjs` (INCLUDE `core`, `ui36`; VENDOR empty until Phase 3) and
   `scripts/check-ui36.mjs`.
3. CI: the existing build job switches to stage → `build-plugin-pkg -- <stage>` → rename to
   `Vigil-<ver>-dwc36.zip`. Also run `check-ui36` in that job (it already has the 3.6 checkout
   with `node_modules`).
4. Update `tests/frontend/integration/plugin-structure.test.js` (entry path, stubs no longer in `src/`)
   and drop `scripts/build-zip.js` + the `build` npm script.
5. **Verify:** ZIP from the staged build is functionally identical to Phase 0's.

### Phase 2 — split the test toolchains (§5 option A)
1. `tests/ui36/` nested project with the Jest suite; root moves to vitest + test-kit.
2. Port `backend.test.js` (and any other Vue-free tests) to `tests/core/` under vitest.
3. CI frontend job: root `npm ci`, `npm run lint`, `npm test`, then `npm run test:ui36`.
4. **Verify:** same test count passes as before, split across the two runners.

### Phase 3 — chart.js 4 in shared code, vendored into 3.6 (§4)
1. `src/core/charts.js` with config builders + tests (pure objects, no canvas).
2. `ui36/components/*Chart.vue` import from `../../core/charts.js`; `chart.js/auto` resolves to the
   vendored copy.
3. `stage-dwc36.mjs`: `VENDOR = ["chart.js"]` (copies the dependency closure from the root
   `node_modules`, so `npm ci` at the root is a prerequisite of the 3.6 build).
4. **Verify on a real DWC 3.6:** all four charts render, DWC's own temperature chart is unaffected
   (proves the vendored copy did not leak), no console errors.

### Phase 4 — the DWC 3.7 shell
Suggested order, building after each step (upstream's advice: never write everything then build):
1. `src/ui37/host.js`, `src/ui37/index.js` (registerRoute with `translated: true`, `ensureBackendRunning`,
   `Events.on('dwcPluginUnloaded', id => id === 'Vigil' && unregisterRoute('/Vigil'))`). Flip
   `src/index.js` to `import './ui37/index'`. Get an empty page routing in a 3.7 DWC.
2. Port components in dependency order: `StatCard`, `CounterTabs`, `ExportButton`, `AxisTable`,
   `VitalsCard`, the four charts (thin wrappers over `core/charts.js`), the three dialogs, then
   `VigilDashboard.vue`.
3. `tests/ui37/` mount tests via the test kit.
4. CI: new `build-dwc37` job (Node 22+, checkout `v3.7-dev`, `npm install` in DWC, `npm ci` in the
   plugin so the builder's own install is a no-op, `node scripts/build-plugin-pkg.js ../plugin`,
   rename to `Vigil-<ver>-dwc37.zip`, keep `-srcmap.zip` out of the artifact).
5. **Verify on a real DWC 3.7 + DSF 3.7:** install, daemon starts, dashboard polls, every tab,
   dialog, export and reset works, upgrade-over-existing triggers the banner and Start Backend works,
   stopping the plugin in Settings → Plugins removes the menu entry (unregisterRoute).

Vuetify 2 → 4 translation table for the components Vigil actually uses (from a tag inventory of
`src/`; each is a silent-breakage risk because the old prop is still valid markup):

| Vuetify 2 (today) | Vuetify 4 |
|---|---|
| `v-simple-table` | `v-table` |
| `v-list-item-icon` + `v-list-item-title` | `v-list-item` with `prepend-icon` / `#prepend` slot; `v-list-item-title` remains |
| `v-tabs` + `v-tab` + `v-tabs-items` | `v-tabs` + `v-tab` (`value`) + `v-tabs-window` / `v-window` |
| `v-timeline` / `v-timeline-item` (`color`, `small`) | still exist; `dot-color`, `size="small"` |
| `v-select` `item-text` / `dense` / `outlined` | `item-title` / `density="compact"` / `variant="outlined"` |
| `v-btn` `text` / `outlined` / `depressed`; `<v-icon left>` | `variant="text"` / `"outlined"` / `"flat"`; `prepend-icon` or `<v-icon start>` |
| `v-alert` `outlined` / `dismissible` | `variant="outlined"` / `closable` |
| `v-chip small`, `v-icon small` / `x-large` | `size="small"` / `size="x-large"` |
| `v-menu` `offset-y`, activator `{ on, attrs }` | drop `offset-y`; activator slot is `{ props }` → `v-bind="props"` |
| `v-textarea` / `v-checkbox` `outlined` / `dense` | `variant` / `density` |
| colour `grey lighten-1` | `grey-lighten-1` |
| `v-dialog`, `v-snackbar`, `v-card*`, `v-row`, `v-col`, `v-spacer`, `v-divider`, `v-progress-circular`, `v-container` | unchanged in practice |
| Vue 2 `beforeDestroy` | `beforeUnmount` |

### Phase 5 — release with two ZIPs
1. `release.yml`: resolve the latest stable tag **per major** (`v3.6.x` and `v3.7.x`; while no stable
   3.7 exists, fall back to the latest `v3.7.0-rc.N` or `v3.7-dev` explicitly and say so in the notes).
   The current regex picks the single highest tag, which will silently become 3.7 the day it ships.
2. Two build jobs (or one job with two Node setups; upstream does one job with two checkouts), both
   ZIPs attached to the same release, notes stating which DWC each was built against.
3. README: an install matrix (DWC 3.6 → `-dwc36.zip`, DWC 3.7 → `-dwc37.zip`), and a note that
   DWC rejects the other one with a version mismatch.
4. Bump `plugin.json` to the next minor.

---

## 7. Landmines (verified in the sources or found by upstream — do not rediscover)

### 7.1 Never point DWC 3.7's builder at a tree that contains Vue 2 packages at the root
`installPluginDependencies` runs `npm install` in the plugin dir if any `dependencies` **or
`devDependencies`** are missing, then removes what it added. Keep `vue@2`, `vuetify@2`, `vuex` and
`@vue/vue2-jest` out of the root `package.json` (that is §5 option A) so nothing Vue 2 shaped is ever
installed next to a Vite 8 build. Always run `npm ci` at the root in CI before the 3.7 build so the
builder's install step is a no-op.

### 7.2 The 3.6 builder copies the whole `src/` into `DuetWebControl/src/plugins/Vigil/`
Anything under `src/` is copied, whether imported or not. For plain JS webpack only bundles what the
entry imports, so a stray `ui37/` would probably not break the 3.6 build — but "probably" is why the
stage script exists: it also gives the 3.6 build its own `src/index.js` and the vendored chart.js.
Always build 3.6 from the staged tree, never from the repo. Clean `DuetWebControl/src/plugins/Vigil`
and `dist/Vigil-*.zip` before each run (an interrupted run leaves a stale copy that gets compiled again).

### 7.3 `-srcmap.zip` sorts before `.zip`
DWC 3.7's builder emits `Vigil-<ver>-srcmap.zip` next to `Vigil-<ver>.zip`. `-` sorts before `.`, so a
naive `ls Vigil-*.zip | head -1` picks the sourcemap archive. Filter it out explicitly (upstream
shipped this bug once).

### 7.4 `ui36/` has no automated safety net beyond compiling
Vuetify 4 props surviving in a Vuetify 2 template (or vice versa) are valid markup. `check-ui36.mjs`
catches malformed SFCs in a second; the Jest mount tests catch script errors; only a real DWC 3.6
catches a wrong prop name. Budget a manual smoke test on both generations for every UI change.

### 7.5 Reactivity of the plugin entry
`host.pluginEntry()` must read `model.plugins` through the store on every call. Caching the entry
(or the Map) at host creation time makes `backendRunning` freeze at its first value and the
recovery banner never appears. Upstream documents the identical requirement for their `model()`.

### 7.6 DSF 3.7 on the SBC side (Vigil-specific, not in upstream's plan)
The 3.7 ZIP carries `sbcDsfVersion: 3.7`, so it installs only on DSF 3.7, which ships dsf-python 3.7.
The daemon's monkey patches (`CLAUDE.md` §3: `PluginManifest._data`, `BoardState`, `resolve_path`,
`BaseConnection.connect` `recv(50)`) were written against dsf-python 3.6 and are wrapped in
`try/except ImportError` — which does **not** protect against a class that still imports but changed
shape. Before Phase 4's smoke test: clone `dsf-python` at `v3.7-dev`, re-read the five files listed in
`CLAUDE.md`, and check each patch still applies (or is no longer needed). Run the pytest suite with the
mocks pointed at whatever changed. This is the one place the dual build touches Python.

### 7.7 Node versions in CI
DWC 3.6 (vue-cli 5) builds on Node 18; DWC 3.7 (Vite 8) needs Node ≥ 22. Use separate jobs with their
own `setup-node`, or two `setup-node` steps in one job. Do not try to build both on one Node.

### 7.8 `translated: true` means opposite things in 3.6 App.vue only when a key is used
Vigil passes a literal caption with `translated: true`, which is correct on both generations. If i18n
is ever added, drop the flag and use `registerPluginMessages` (3.7) / `i18n.mergeLocaleMessage` (3.6)
per upstream §7.5.

### 7.9 `dwcPluginUnloaded` exists only on 3.7
On 3.7, unregister the route and clear the poll timer when Vigil is stopped from Settings → Plugins;
3.6 has no such event and nothing to unregister. Keep that code in `ui37/index.js` only.

---

## 8. Verification checklist (before the first dual release)

- [ ] `npm test` (vitest: core + ui37) and `npm run test:ui36` (Jest) both green, total test count ≥ today's
- [ ] `pytest tests/` green, plus the dsf-python 3.7 patch review from §7.6
- [ ] `DWC36_DIR=… npm run check-ui36` compiles every `ui36` SFC
- [ ] `build36.sh` produces `Vigil-<ver>-dwc36.zip`; `build37.sh` produces `Vigil-<ver>-dwc37.zip`
- [ ] Each ZIP installs on its own generation and is **refused** by the other (dwcVersion mismatch)
- [ ] On both generations: dashboard loads, all tiers/tabs, four charts, history drill-down, service log,
      counter reset, service event, JSON + CSV export
- [ ] On both generations: upgrade-over-existing shows the "backend stopped" banner and Start Backend
      brings the endpoints back; DWC's own charts still render on 3.6 (no chart.js leak)
- [ ] On 3.7: stopping the plugin removes the menu entry; starting it again brings it back without a reload
- [ ] Release run attaches both ZIPs and the notes name both DWC refs

---

## 9. Effort and scope

- Phases 0–3 are refactors of ~1,800 lines of existing Vue 2 code plus build plumbing; low risk if the
  3.6 smoke test is repeated after each.
- Phase 4 is the cost centre: 13 SFCs (~1,600 lines) re-expressed in Vuetify 4. Vigil's templates are
  cards, tables, tabs and dialogs — none of the stepper/wizard cases upstream flags as worst — so
  expect close to 1:1 line counts.
- Ongoing cost: every UI change lands twice. Keeping logic in `core/` and the SFC `<script>` blocks
  thin (Options API in both) is what keeps that to "twice the template", not "twice the plugin".

Open decisions to settle before Phase 1:

1. ZIP naming: explicit `-dwc36` / `-dwc37` suffixes on both (recommended) vs upstream's bare name for
   the newer generation.
2. Test split: §5 option A (recommended) vs dropping the Vue 2 component tests.
3. Whether the 3.7 release should target `v3.7-dev` / release candidates until a stable 3.7 tag exists,
   and whether to label such builds as pre-release on GitHub.
