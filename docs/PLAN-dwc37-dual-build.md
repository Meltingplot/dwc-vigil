# Plan: dual DWC 3.6 / 3.7 builds for Vigil

**Status: implemented.** Phases 0–5 landed on 2026-09-10; what follows is the plan as written,
kept as the record of why the build looks the way it does. What actually shipped, and where it
departed from the plan, is in §10 at the end.

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
| `build.bat` / `build36.bat` | `scripts/ci-local.sh` (local mirror of `ci.yml`: stages `python`, `matrix`, `frontend`, `build`; one DWC 3.6 checkout under `.ci-local/`) + `version.js`; `scripts/build-zip.js` (raw-source ZIP, not installable) | Drop `build-zip.js`. Grow `ci-local.sh` into the two-build runner (`build36` / `build37` stages, §3.2) instead of adding `build36.sh` / `build37.sh`; keep `version.js --write` and run it once before both builds |
| 3.6 built with `npm run build-plugin-pkg` (populates `dwcFiles` / `dsfFiles`) | `ci.yml` and `ci-local.sh` call `npm run build-plugin` (manifest without those arrays; `collect_zip` checks the ZIP layout instead) | Switch 3.6 to `build-plugin-pkg` as part of Phase 1 so both generations ship the same manifest shape (3.7's `build-plugin-pkg.js` always populates the arrays); extend the local manifest check accordingly (§3.2) |
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
  ci-local.sh               local CI runner (exists); gains build36 / build37 stages (§3.2)
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

### 3.2 Local CI runner: `scripts/ci-local.sh` and `.ci-local/`

`scripts/ci-local.sh` (PR #30) reproduces `.github/workflows/ci.yml` on a workstation. Everything
it needs lives in the gitignored `.ci-local/` directory; nothing is installed system-wide. What it
does today, and what the dual build needs from it:

| Stage | Today (3.6 only) | After the dual build |
|---|---|---|
| `python` | pytest + coverage in `.ci-local/venv` | unchanged |
| `matrix` | pytest on Python 3.10–3.12 via Docker (`python:<v>-slim`, repo copied read-only) | unchanged |
| `frontend` | `npm ci`, `npm run lint`, `npx jest tests/frontend/*.test.js`, `npx jest tests/frontend/integration/` | `npm ci`, `npm run lint`, `npm test` (vitest: `tests/core`, `tests/ui37`), then `npm run test:ui36` (`npm ci` + Jest inside `tests/ui36/`, §5) |
| `build` | fetch/update DWC `$DWC_REF` into `.ci-local/DuetWebControl`, `npm install` there, `version.js --write` (snapshot + restore), `npm run build-plugin $ROOT`, `collect_zip` | becomes an alias for `build36` + `build37`; `all` runs both |
| `build36` (new) | – | `npm run check-ui36` against the 3.6 checkout, `node scripts/stage-dwc36.mjs .ci-local/stage-36`, `npm run build-plugin-pkg -- $WORK/stage-36` in `.ci-local/DuetWebControl-36`, copy `dist/Vigil-<ver>.zip` to `.ci-local/dist/Vigil-<ver>-dwc36.zip`, `collect_zip` with expected major.minor `3.6` |
| `build37` (new) | – | refuse to run on Node < 22 (§7.7), fetch/update `.ci-local/DuetWebControl-37` at `$DWC37_REF`, `npm install` there, `npm ci` at the repo root (so the builder's own install is a no-op, §7.1), `node scripts/build-plugin-pkg.js $ROOT` from the 3.7 checkout, move `$ROOT/Vigil-<ver>.zip` to `.ci-local/dist/Vigil-<ver>-dwc37.zip`, delete `$ROOT/Vigil-<ver>-srcmap.zip`, `$ROOT/dist/`, `$ROOT/pkg/` (§7.11), `collect_zip` with expected major.minor `3.7` |

Env overrides: `DWC_REF` becomes `DWC36_REF` (default `v3.6-dev`) and `DWC37_REF` (default
`v3.7-dev`); `PYTHON` stays. The stage names `python | matrix | frontend | build36 | build37 | build | all`
are the CLI surface documented in the README's "Running CI locally" section; update it in the same
commit.

```
.ci-local/
  venv/                  pytest + pytest-cov
  DuetWebControl-36/     persistent v3.6-dev checkout (git fetch --depth 1 + checkout --force per run)
  DuetWebControl-37/     persistent v3.7-dev checkout
  stage-36/              output of stage-dwc36.mjs, wiped before every build36
  dist/                  Vigil-<ver>-dwc36.zip, Vigil-<ver>-dwc37.zip (only these two files)
  version-backup/        plugin.json / package.json snapshots restored by the EXIT trap
```

Rules the runner enforces that the dual build must keep:

- **Version stamping is transactional.** `stamp_version` snapshots `plugin.json` / `package.json`,
  runs `version.js --write`, and the EXIT trap restores them even when a build dies. Stamp once,
  before `build36`, and restore after `build37`, so both ZIPs carry the same version; the working
  tree must be clean after any exit path (`git status --short` empty, checked in §8).
- **`dsf/__pycache__` is stripped before every build**, and `collect_zip` fails if bytecode is in
  the ZIP. Both builders copy `dsf/` verbatim (§0), and a local `pytest` run always leaves bytecode
  behind, so this stays in front of *both* build stages (the 3.6 stage script copies `dsf/` too,
  so strip before staging).
- **`collect_zip <zip> <expected major.minor>`** keeps today's checks (`plugin.json` at the ZIP root,
  a built `dwc/js/Vigil.*.js`, `dsf/vigil-daemon.py`, no `__pycache__`, `id`, stamped `version`,
  `sbcExecutable`, `dwcVersion` and `sbcDsfVersion` equal to the checkout's major.minor) and gains:
  no `*.zip` entry inside the ZIP (§7.10), and, once both builds go through `build-plugin-pkg`,
  `dwcFiles` and `dsfFiles` present, non-empty, and listing `vigil-daemon.py`. The expected
  major.minor is read from the respective checkout's `package.json`, as today, so `DWC36_REF` /
  `DWC37_REF` pointing at a tag keeps the check meaningful.
- **`ci.yml` and `ci-local.sh` change together.** Every CI step added or changed in Phases 1–5
  lands in the runner in the same commit, and the runner is what verifies a phase before it is
  pushed. The `python` and `matrix` stages do not change; the `frontend` stage changes in Phase 2,
  the build stages in Phases 1 and 4.

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

`ci-local.sh`'s `frontend` stage calls exactly these scripts (`lint`, `test`, `test:ui36`) rather
than `npx jest …` directly, so the runner, `ci.yml` and a developer's shell run the same commands.

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
   `Vigil-<ver>-dwc36.zip` → unpack into its own artifact directory and upload that as artifact
   `Vigil-dwc36` (see §7.10, this keeps the downloaded artifact directly installable). Also run
   `check-ui36` in that job (it already has the 3.6 checkout with `node_modules`).
4. Update `tests/frontend/integration/plugin-structure.test.js` (entry path, stubs no longer in `src/`)
   and drop `scripts/build-zip.js` + the `build` npm script.
5. `ci-local.sh`: rename the `build` stage to `build36` (keep `build` as an alias), `DWC_REF` →
   `DWC36_REF`, checkout dir → `.ci-local/DuetWebControl-36`, run `check-ui36` + stage script +
   `build-plugin-pkg` on the staged tree, copy the result to `.ci-local/dist/Vigil-<ver>-dwc36.zip`,
   extend `collect_zip` (`dwcFiles` / `dsfFiles`, no nested `*.zip`). Update the README section.
6. **Verify:** `scripts/ci-local.sh all` green; ZIP from the staged build is functionally identical
   to Phase 0's (same entry list in `unzip -l` apart from the manifest arrays).

### Phase 2 — split the test toolchains (§5 option A)
1. `tests/ui36/` nested project with the Jest suite; root moves to vitest + test-kit.
2. Port `backend.test.js` (and any other Vue-free tests) to `tests/core/` under vitest.
3. CI frontend job: root `npm ci`, `npm run lint`, `npm test`, then `npm run test:ui36`.
4. `ci-local.sh` `frontend` stage: same four commands (replaces the two `npx jest` calls). The nested
   `npm ci` in `tests/ui36/` writes `tests/ui36/node_modules` and `tests/ui36/package-lock.json`;
   ignore the former, commit the latter.
5. **Verify:** `scripts/ci-local.sh frontend` reports the same total test count as before, split
   across the two runners.

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
   rename to `Vigil-<ver>-dwc37.zip`, unpack it into its own artifact directory and upload that as
   artifact `Vigil-dwc37`; the `-srcmap.zip` must not land in that directory, see §7.3 and §7.10).
   `ci-local.sh`: matching `build37` stage (§3.2) with the Node ≥ 22 guard, `DWC37_REF`,
   `.ci-local/DuetWebControl-37`, the move-out of `Vigil-<ver>.zip` and the cleanup of `dist/`,
   `pkg/` and `-srcmap.zip` from the repo root (§7.11); `build` and `all` now run both builds.
   Add `/pkg/` and `/Vigil-*.zip` to `.gitignore` (`dist/` is already ignored).
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
   DWC rejects the other one with a version mismatch. The "Building" section points at
   `scripts/ci-local.sh build36` / `build37` instead of a hand-run `npm run build-plugin`, and
   "Running CI locally" lists the new stages and `DWC36_REF` / `DWC37_REF`.
4. Bump `plugin.json` to the next minor.
5. Dry-run the release build locally first: `DWC36_REF=v3.6.<latest> DWC37_REF=<3.7 tag or rc>
   scripts/ci-local.sh build` must produce both ZIPs with `dwcVersion` matching the tags, which is
   the same pair of refs `release.yml` resolves in step 1.

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
This matters most locally: `.ci-local/DuetWebControl-36` is a *persistent* checkout that
`ci-local.sh` only fetches and force-checks-out (untracked files survive), and the 3.6 builder removes
`src/plugins/Vigil` only on success, not in its error path. `collect_zip` picks the newest
`dist/Vigil-*.zip` by mtime today; with two ZIP names in play, wipe `dist/Vigil-*.zip` before the build
and match the exact expected name afterwards instead.

### 7.3 `-srcmap.zip` sorts before `.zip`
DWC 3.7's builder emits `Vigil-<ver>-srcmap.zip` next to `Vigil-<ver>.zip`. `-` sorts before `.`, so a
naive `ls Vigil-*.zip | head -1` picks the sourcemap archive. Filter it out explicitly (upstream
shipped this bug once). `ci-local.sh`'s `collect_zip` uses `ls -1t … | head -1` (newest by mtime),
which is no safer: the sourcemap archive is written *after* the plugin ZIP and would win. Every
CI/local build hits this, not only tagged releases: `version.js` stamps `X.Y.Z-dev.N`, which the
builder's prerelease regex (`-(alpha|beta|rc)`) does not match, so dev builds get hidden sourcemaps
and always produce the `-srcmap.zip`. Address by exact name (`Vigil-$VERSION.zip`, with `$VERSION`
from `node scripts/version.js`) rather than by glob.

### 7.10 CI artifacts must stay installable: no ZIP inside a ZIP
GitHub always wraps an uploaded artifact in a ZIP of its own on download. Uploading `Vigil-<ver>.zip`
as-is therefore yields `Vigil-plugin.zip` containing `Vigil-<ver>.zip`, which DWC rejects (no
`plugin.json` at the root). Today's `ci.yml` already solves this: it unpacks the plugin ZIP into a
directory and uploads the *contents*, so the artifact ZIP GitHub serves has `plugin.json`, `dsf/` and
`dwc/` at its root and installs directly. The dual build keeps that rule, with two additions:

- **One artifact per generation** (`Vigil-dwc36`, `Vigil-dwc37`), each holding one unpacked plugin
  tree. Never put both ZIPs, or both unpacked trees, into one artifact: the former is ZIP-in-ZIP, the
  latter collides on `plugin.json`. The artifact name is what the download is called, so it should
  carry the generation.
- **Unpack only the plugin ZIP.** The 3.7 builder writes `Vigil-<ver>-srcmap.zip` next to the real
  package and a `pkg/` staging directory that mirrors the ZIP layout. Filter `-srcmap.zip` out before
  unpacking (or upload `pkg/` directly, which is already the unpacked tree), otherwise the sourcemap
  archive ends up inside the artifact as a stray file.
- **Release assets are different.** `gh release create` / `softprops/action-gh-release` attach the
  ZIP files themselves, unwrapped, so the two renamed ZIPs are uploaded as-is there. Only the
  `actions/upload-artifact` path needs the unpack step.
- Verify in CI, not by eye: after unpacking, assert `test -f <dir>/plugin.json` and that
  `unzip -l` of the produced plugin ZIP lists no `*.zip` entry, then fail the job otherwise.
  `ci-local.sh`'s `collect_zip` already asserts `plugin.json` at the ZIP root and is the place for
  the "no nested `*.zip`" check too, so a local `build37` catches a sourcemap archive that slipped
  into `pkg/` before CI does.

### 7.11 DWC 3.7's builder writes into the plugin directory, i.e. the repo root
`build-plugin-pkg.js` (3.7) puts its outputs *inside the plugin dir*: `dist/` (Vite output),
`pkg/` (the assembled tree), `Vigil-<ver>.zip` and `Vigil-<ver>-srcmap.zip`; `installPluginDependencies`
may also `npm install` into the plugin's `node_modules` and undo that afterwards. In CI the plugin
checkout is throwaway; locally it is the working tree. So: add `/pkg/` and `/Vigil-*.zip` to
`.gitignore` (`dist/` is already there), have `build37` move the plugin ZIP to `.ci-local/dist/`
and delete `dist/`, `pkg/` and the `-srcmap.zip` afterwards (also on failure, via the same EXIT trap
that restores the version files), and make `stage-dwc36.mjs` copy only `core/` and `ui36/` so a
leftover `dist/` or `pkg/` from a 3.7 run never reaches the 3.6 stage. The 3.6 builder has the
opposite shape (outputs land in the DWC checkout's `dist/`), which is why the two stages must not
share a `collect_zip` path assumption.

### 7.12 `.ci-local/` sits inside the repo, so Node's upward module resolution can reach the root `node_modules`
Both DWC checkouts live under `$ROOT/.ci-local/`. Webpack (3.6) and Vite (3.7) resolve bare imports
by walking up from the importing file, and the 3.7 builder's `isPackageInstalled` does the same walk
explicitly. From `.ci-local/DuetWebControl-36/src/plugins/Vigil/…` that walk passes DWC's own
`node_modules` first (so `vue`, `vuetify`, `vuex` are DWC's), but anything DWC 3.6 does *not* ship
and the repo root does (after §5: `chart.js` 4, vitest, `@vue/test-utils@2`, …) resolves silently
from `$ROOT/node_modules` in a local build and fails in CI, where `plugin/` and `DuetWebControl/`
are siblings. Vendoring (§4) is the intended path for `chart.js`; for everything else the rule is
that a 3.6 build which only passes locally is broken. Cheap guard in `build36`: grep the staged
build's webpack stats / the emitted chunk for `../../..` paths escaping the DWC checkout, or simply
keep `npm test` + `build36` green in CI before trusting a local green. The nested Jest project in
`tests/ui36/` has the mirror-image problem (SFCs under `src/ui36/` resolve `vue` and `vuex` upward
to the Vue 3 root): its `jest.config.js` needs `moduleDirectories: ['<rootDir>/node_modules',
'node_modules']` plus explicit `moduleNameMapper` entries for `vue`, `vuex` and `vuetify`, which
belongs to Phase 2 and is verified by `ci-local.sh frontend`.

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
Locally, `ci-local.sh` uses whatever `node` is on `PATH` and prints its version per stage. `build37`
must check `node -v` (major ≥ 22) up front and die with a hint, otherwise Vite fails late with an
opaque error. Whether DWC 3.6 still builds on the same Node ≥ 22 has to be verified once (vue-cli 5 /
webpack 5 generally do); if it does, one host Node covers both stages, if not, run `build36` in
`node:18` via Docker the way the `matrix` stage runs pytest, rather than juggling `nvm` inside the
script.

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
- [ ] `scripts/ci-local.sh all` green end to end: `build36` produces `.ci-local/dist/Vigil-<ver>-dwc36.zip`,
      `build37` produces `.ci-local/dist/Vigil-<ver>-dwc37.zip`, `collect_zip` passes for both (right
      `dwcVersion`, `dwcFiles` / `dsfFiles`, no `__pycache__`, no nested `*.zip`)
- [ ] After `ci-local.sh all`, `git status --short` is empty: version files restored, no `dist/`,
      `pkg/`, `Vigil-*.zip` or `tests/ui36/node_modules` showing up as untracked (§7.11)
- [ ] The same commit is green in GitHub Actions (rules out a local-only resolution, §7.12)
- [ ] Each ZIP installs on its own generation and is **refused** by the other (dwcVersion mismatch)
- [ ] On both generations: dashboard loads, all tiers/tabs, four charts, history drill-down, service log,
      counter reset, service event, JSON + CSV export
- [ ] On both generations: upgrade-over-existing shows the "backend stopped" banner and Start Backend
      brings the endpoints back; DWC's own charts still render on 3.6 (no chart.js leak)
- [ ] On 3.7: stopping the plugin removes the menu entry; starting it again brings it back without a reload
- [ ] Release run attaches both ZIPs and the notes name both DWC refs
- [ ] The two CI artifacts each download as a ZIP with `plugin.json` at the root, contain no nested
      `*.zip`, and install directly on their generation (§7.10)

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
4. Whether `build36` runs on the host Node (if vue-cli 5 builds on Node ≥ 22) or in a `node:18`
   Docker container like the `matrix` stage (§7.7). Decide in Phase 4 when `build37` forces Node 22
   locally.


---

## 10. What shipped (2026-09-10)

Implemented across six commits, one per phase. The plan held up; the notes below are the places
where reality differed or a decision had to be made.

### Open decisions, settled

1. **ZIP naming** — explicit suffixes on both (`Vigil-<ver>-dwc36.zip`, `Vigil-<ver>-dwc37.zip`),
   as recommended. Neither generation keeps the bare name.
2. **Test split** — §5 option A. All 60 original frontend tests survive; the suite now stands at
   133 frontend tests (100 vitest across `tests/core` + `tests/ui37`, 33 Jest in `tests/ui36`) and
   212 Python tests.
3. **3.7 release target** — `release.yml` resolves the newest `v3.7.x` tag and falls back to the
   newest `v3.7.0-<alpha|beta|rc>.N` (today: `v3.7.0-rc.1`), then to `v3.7-dev`. The release itself
   is *not* marked pre-release — that would hide it from 3.6 users, whose package is built against a
   stable `v3.6.x` either way — but the notes say which ref each asset was built against and add an
   explicit warning line while no stable 3.7 exists.
4. **Node for `build36`** — it stays on the host Node. The problem turned out to be the other way
   round: a workstation on Node 18 cannot run the 3.7 build at all. So `build37` checks `node -v`
   and, when the host is older than 22, runs the DWC install and the build in a `node:22-slim`
   container the way the `matrix` stage runs old Pythons (`BUILD37_DOCKER=0` refuses instead). CI
   uses two `setup-node` steps, per §7.7.

### Departures from the plan

- **`stage-dwc36.mjs` also stages `dsf/`.** Upstream's plugin has no SBC half, so their script only
  copies `src/`. Both builders read `dsf/`, `dwc/` and `sd/` from the *plugin directory* rather than
  from `src/`, so without this the 3.6 package would have shipped with no daemon and an empty
  `dsfFiles`. It filters `__pycache__` on the way, rather than trusting the caller to have stripped it.
- **`core/format.js` landed in Phase 0**, not later — it is pure extraction and it shrinks Phase 4.
- **The host adapter has an `undefined` case.** `pluginEntry()` returns `undefined` when there is no
  machine object model at all, distinct from `null` for "no entry yet". Without it, `ensureBackendRunning`
  polls for 30 s in every environment that has no DWC — including the Jest run that imports
  `ui36/index.js`. §3.1's two members are otherwise unchanged.
- **`VigilDashboard` takes the host as a prop** (defaulting to `createHost()`). Both adapters read a
  module singleton, which a mounted component cannot substitute, and the plan wants the existing
  dashboard tests kept.
- **The DWC stubs went to `tests/ui36/dwc-stubs/`**, not `tests/ui36/__mocks__/` — Jest resolves a
  manual mock relative to the *resolved* module path, so the stubs and their `__mocks__` directory
  have to sit together.
- **§7.6 found a real breakage.** dsf-python 3.7 renamed `BaseConnection.connect` to `_connect`, so
  the patch working around the truncating `recv(50)` was landing on a method nothing calls: on DSF 3.7
  the daemon would have failed to connect with the exact `JSONDecodeError: Unterminated string` that
  patch exists to prevent, and the `try/except ImportError` would have hidden nothing because there
  was no error. It now patches whichever names the class has, and `tests/test_dsf_patches.py`
  exercises every patch against both library shapes. Of the rest: `BoardState` (still missing
  `timedOut`) and `Axis.letter` are still needed on 3.7; `PluginManifest.data` and
  `NetworkInterfaceType.ethernet` are fixed upstream and are now marked 3.6-only.
- **`vitest.config.mjs`, not `.js`** — the root `package.json` is CommonJS, and the test kit's config
  helper is ESM.

### Verified

- `scripts/ci-local.sh all` green end to end, with `DWC36_REF=v3.6.3 DWC37_REF=v3.7.0-rc.1` (the same
  pair `release.yml` resolves today): both ZIPs built, `collect_zip` passing for each, `git status
  --short` empty afterwards and `.ci-local/dist/` holding exactly the two packages.
- The 3.6 bundle reports Chart.js v4.5.0 while DuetWebControl's own app bundle still reports v2.9.4 —
  the vendored copy does not leak into DWC's charts.
- The 3.7 bundle externalises `DWC.registerRoute` / `DWC.unregisterRoute` / `DWC.Events` / `DWC.Vue`
  and bundles its own Chart.js; DWC 3.7's own type check passes over the repo, `src/ui36/` included.

### Not verified — still owed

The whole of §8's second half needs real hardware and has not been done: installing each package on
its own generation (and confirming the other is refused), the dashboard, charts, dialogs, exports and
counter reset on both, the upgrade-over-existing banner path, and — on 3.7 — that stopping the plugin
removes the menu entry. §7.4 stands: for `ui36` in particular, a wrong Vuetify 2 prop is valid markup
that only a running DWC 3.6 will catch.
