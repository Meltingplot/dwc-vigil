# DWC + DSF Plugin Developer Guide (3.6 and 3.7)
> Lessons learned building `dwc-meltingplot-config` and `dwc-vigil`.
> This plugin ships **one source tree** for **two generations** of DuetWebControl / DSF:

| | Generation 3.6 | Generation 3.7 |
|---|---|---|
| DWC framework | Vue **2.7** (Options API) + Vuetify **2.7** + Vuex 3 | Vue **3.5** (Options API kept) + Vuetify **4** + Pinia |
| DWC plugin API | `registerRoute` from `@/routes`; store via `@/store` | `registerRoute`, `unregisterRoute` from `@/plugins`; store via `@/stores/machine`; `Events` from `@/utils/events` |
| DWC builder | webpack: `npm run build-plugin-pkg -- <dir>` in the DWC checkout, Node 18 | Vite 8: `node scripts/build-plugin-pkg.js <dir>`, Node **>= 22** |
| dsf-python | hand-written `@property` model classes, `BaseConnection.connect`, Python >= 3.7 | `model_prop` descriptors, `BaseConnection._connect`, Python **>= 3.11** |
| Upstream refs | `Duet3D/DuetWebControl@v3.6-dev`, `Duet3D/dsf-python@v3.6-dev` | `Duet3D/DuetWebControl@v3.7-dev`, `Duet3D/dsf-python@v3.7-dev` |
| Package | `Vigil-<ver>-dwc36.zip` | `Vigil-<ver>-dwc37.zip` |

DWC refuses a package built for the other generation (`dwcVersion` major.minor check), so
every change has to be considered for **both** and verified on **both**.

---
## ⚠️ MANDATORY RULE 1: Do Not Guess API Interfaces
**NEVER** guess or assume dsf-python, DWC, or DSF API signatures. Clone **both** upstream
branches and read the actual code before writing against any interface:
```bash
git clone --branch v3.6-dev --depth 1 https://github.com/Duet3D/dsf-python.git /tmp/dsf-python
git clone --branch v3.7-dev --depth 1 https://github.com/Duet3D/dsf-python.git /tmp/dsf-python-37
git clone --branch v3.6-dev --depth 1 https://github.com/Duet3D/DuetWebControl.git /tmp/DuetWebControl
git clone --branch v3.7-dev --depth 1 https://github.com/Duet3D/DuetWebControl.git /tmp/DuetWebControl-37
```
Key dsf-python files (same paths in both branches, different contents):
- `src/dsf/connections/subscribe_connection.py` — `SubscribeConnection` constructor **differs** (§5)
- `src/dsf/connections/base_connection.py` — `connect` (3.6) vs `_connect` (3.7)
- `src/dsf/connections/base_command_connection.py` — `add_http_endpoint()`, `set_plugin_data()`, `resolve_path()`
- `src/dsf/object_model/utils.py` — **3.7 only**: `model_prop`, `nullable_model_prop`, `_set_model_prop`
- `src/dsf/object_model/job/gcode_fileinfo.py`, `plugins/plugin_manifest.py`, `boards/boards.py` — model classes
- `src/dsf/http.py` — `HttpEndpointConnection`, `HttpResponseType`

The real 3.7 library runs locally for spot checks (it needs `python-dateutil`):
```bash
pip install --target /tmp/pylib python-dateutil
PYTHONPATH=/tmp/dsf-python-37/src:/tmp/pylib:dsf python3 -c "..."   # import dsf/vigil-daemon.py and poke the model
```

## ⚠️ MANDATORY RULE 2: Every Note Carries a Generation Tag
Every note, pitfall row, monkey-patch, workaround and code comment added to this guide, to
the patch block at the top of `dsf/vigil-daemon.py`, or to `docs/` **must** state which
generation it applies to, using one of exactly three tags:

| Tag | Meaning |
|---|---|
| **[3.6 only]** | Verified on 3.6; verified **not** needed / not applicable on 3.7 |
| **[3.7 only]** | Verified on 3.7; verified **not** needed / not applicable on 3.6 |
| **[both]** | Verified on 3.6 **and** 3.7 |

Rules:
1. A tag is a claim about **both** generations. Before writing `[3.6 only]` you have checked
   3.7 (and vice versa). Something found on one generation and not yet checked on the other
   is written as `[3.6, 3.7 unchecked]` and is a TODO, not a finished note.
2. Say what it was verified against: upstream branch or tag plus date, e.g.
   `verified dsf-python v3.7-dev @ 2026-09-12`. Upstream `-dev` branches move; a dated tag
   tells the next reader whether to re-verify.
3. A bug report from a printer must be tied to the generation the printer runs (DSF/DWC
   version from the log or `Settings → General`) before it is turned into a note.
4. Untagged notes are not merged. When you touch an untagged note, tag it (verifying as
   needed) rather than leaving it.
5. When the generations differ, the difference goes into the §5 or §13 tables, not just
   into prose, so it can be found by scanning.

---
## 1. Repository Layout [both]
```
src/
  index.js          import './ui37/index'   — what DWC 3.7's builder compiles; the 3.6
                                              stage script generates its own one-liner
  core/             framework-neutral, shipped to BOTH generations unchanged
    host.js         JSDoc HostAdapter: { pluginEntry(), startBackend() } — the ONLY DWC seam
    backend.js      SBC backend state (PID lookup, start, "partially started" recovery)
    api.js          fetch() calls to the daemon's DSF HTTP endpoints
    charts.js       Chart.js 4 configs (bundled on 3.7, vendored into the 3.6 build)
    format.js       formatting helpers
  ui36/             Vue 2.7 + Vuetify 2 shell: index.js, host.js (Vuex), *.vue
  ui37/             Vue 3.5 + Vuetify 4 shell: index.js, host.js (Pinia), *.vue — same file names
dsf/                Python daemon, identical in both packages (one daemon, two dsf-python shapes)
tests/
  core/  ui37/      vitest + dwc-plugin-test-kit (Vue 3)
  ui36/             nested npm project: Jest + @vue/vue2-jest (Vue 2.7), own node_modules
  test_*.py         pytest, dsf mocked; test_dsf_patches.py runs every patch against BOTH shapes
scripts/
  stage-dwc36.mjs   assembles core/ + ui36/ + dsf/ + plugin.json for the 3.6 builder, vendors chart.js
  check-ui36.mjs    compiles src/ui36/*.vue with the 3.6 checkout's Vue 2.7 compiler
  ci-local.sh       local mirror of ci.yml: python | matrix | frontend | build36 | build37 | build | all
docs/PLAN-dwc37-dual-build.md   why the build looks like this; §7 landmines, §10 what shipped
```
**Rule:** logic goes into `core/`; the two shells should differ in templates and imports only.
Nothing in `core/` may import a store or anything Vue-version-specific.

---
## 2. Plugin Manifest (`plugin.json`) [both]
```jsonc
{
  "id": "Vigil",
  "version": "1.3.0",
  "dwcVersion": "auto-major",     // each builder stamps its own major.minor → one manifest, two ZIPs
  "sbcRequired": true,
  "sbcDsfVersion": "auto-major",
  "sbcExecutable": "vigil-daemon.py",
  "sbcOutputRedirected": true,     // stdout → console "success", stderr → "error": log to stderr
  "sbcPythonDependencies": ["dsf-python"],
  "data": { "status": "idle", "machineHours": 0 }   // pre-declare EVERY key written with set_plugin_data
  // "sbcData": {}                 // [3.6 only verified, 3.7 unchecked] DSF ignores this field — never use it
}
```
- `data` is the only field DSF reads for plugin key-value storage. Every key you write with
  `cmd.set_plugin_data(id, key, value)` **must** be pre-declared. [both]
- One manifest serves both builds; never keep a second one in sync by hand. [both]

---
## 3. Plugin Registration (Frontend)
### 3.1 Entry points — one per generation
```javascript
// src/ui36/index.js  [3.6 only]
import { registerRoute } from '@/routes'
registerRoute(VigilDashboard, { Plugins: { Vigil: { icon: 'mdi-chart-box-outline', caption: 'Vigil', translated: true, path: '/Vigil' } } })
ensureBackendRunning(createHost())

// src/ui37/index.js  [3.7 only]
import { registerRoute, unregisterRoute } from '@/plugins'
import Events from '@/utils/events'
registerRoute(VigilDashboard, { /* same shape */ })
ensureBackendRunning(createHost())
Events.on('dwcPluginUnloaded', id => { if (id === PLUGIN_ID) unregisterRoute('/Vigil') })  // 3.6 has no such event
```
- Path becomes `/plugins/Vigil` in the browser. Icons: `mdi-*`. [both]
- `translated: true` marks the caption as display text, not an i18n key. [both]
- `@/routes`, `@/store` (3.6) and `@/plugins`, `@/stores/*`, `@/utils/events` (3.7) are
  provided by DWC at build time; in tests they are stubs (§10).

### 3.2 The host adapter — the only DWC coupling [both]
`src/core/host.js` documents a two-member `HostAdapter`; each shell implements it:
```javascript
// src/ui36/host.js  [3.6 only] — Vuex root store is a module singleton
import store from '@/store'
pluginEntry:  () => getPluginEntry(store.state?.machine?.model)
startBackend: () => Promise.resolve(store.dispatch('machine/startSbcPlugin', PLUGIN_ID))

// src/ui37/host.js  [3.7 only] — Pinia store resolved per call (keeps the read reactive)
import { useMachineStore } from '@/stores/machine'
pluginEntry:  () => getPluginEntry(useMachineStore().model)
startBackend: () => Promise.resolve(useMachineStore().startSbcPlugin(PLUGIN_ID))
```
- `pluginEntry()` must read through the store on **every** call — never cache — or the
  dashboard's `backendRunning` computed freezes at its first value. [both]
- It returns `null` for "no entry yet" and `undefined` for "no object model at all" (tests,
  no connection); `ensureBackendRunning` gives up immediately on `undefined`. [both]
- `model.plugins` is a **Map** keyed by plugin id on both generations; guard with
  `instanceof Map` because tests may pass a plain object. [both]

### 3.3 Plugin upgrades leave the SBC backend stopped [both]
Installing a newer ZIP over an existing installation puts the plugin into DWC's
**"partially started"** state: the DWC resources load, but the Python daemon is dead and
every `/machine/Vigil/*` endpoint returns 404. Upstream behaviour on both generations:
1. `InstallPlugin` (DCS) runs `UninstallPlugin { ForUpgrade = true }` first, which stops the
   daemon and rewrites `plugins.json` without the plugin (no auto-start on boot either).
2. `InstallPlugin` re-registers the plugin with `Pid = -1` and never starts it.
3. DWC only issues `StartPlugin` when the install was "Upload & Start" (3.6) or the install
   wizard's "start when finished" box was ticked (3.7, **off by default**).
4. DWC then reports `partiallyStarted` because `(plugin.pid >= 0) != enabledPlugins.includes(id)`.

**Workaround** (`src/core/backend.js`): `ensureBackendRunning(host)` polls the object model
until the PID is known and dispatches `startSbcPlugin` when `pid <= 0` (`-1` stopped, `0`
shutting down, `> 0` running). `StartPlugin` defaults to `SaveState = true`, which also
restores the autostart entry. The dashboard shows a banner with a manual **Start Backend**
button while `backendRunning === false`.

---
## 4. dsf-python Bugs the Daemon Patches
All patches live at the top of `dsf/vigil-daemon.py`, each wrapped in `try/except Exception:
pass` so an unpatchable library never stops the daemon, and each **tagged with its
generation** in its comment. `tests/test_dsf_patches.py` runs every patch against fake
libraries of both shapes. `_patch_property_setter()` swaps a property setter whether the
property is hand-written (3.6) or a `model_prop` (3.7) — both store the value in `_<name>`.

| Patch | Tag | What goes wrong |
|---|---|---|
| `PluginManifest.__init__` seeds `_data = ModelDictionary(False)` | **[3.6 only]** | 3.6 creates `_data` as a plain `dict`, which the deserializer skips → `plugin.data` always empty. 3.7 declares `model_prop('data', ModelDictionary, ...)`; the re-seed is a harmless no-op there |
| `BoardState` enum + safe `Board.state` setter | **[both]** | Enum lacks `timedOut` in both; the setter raises `ValueError` and takes down the whole `get_object_model()` |
| `NetworkInterfaceType.ethernet` + safe setter | **[3.6 only]** | 3.6 lacks `ethernet` (DSF 3.6.3-rc.1 reports it). 3.7 has the value; the safe setter stays as a guard |
| Safe `Axis.letter` setter | **[both]** | `'\x00'` from unconfigured axes when the plugin starts before `config.g` ran |
| `BaseConnection.connect`/`_connect` reads a full JSON greeting | **[both]** | Upstream does `self.socket.recv(50)`; the greeting carries a GUID and is longer → `JSONDecodeError: Unterminated string`. **3.7 renamed the method to `_connect`**: patch whichever names the class has, or the patch lands on a method nothing calls and fails silently |
| `dsf.object_model.utils._set_model_prop` accepts `None` for dictionaries/collections | **[3.7 only]** | Non-nullable `model_prop`s (`GCodeFileInfo.custom_info`, `ObjectModel.globals`, `PluginManifest.data`) have no `None` branch; DSF sends `"customInfo": null` in PATCH updates → `TypeError: GCodeFileInfo._custom_info must be of type ModelDictionary ... Got NoneType`, and the whole patch is dropped. `ModelDictionary.update_from_json(None)` already means "clear", so route `None` there. 3.6 has getter-only `custom_info` that the deserializer skips |

Verified against dsf-python v3.6-dev and v3.7-dev (3.7.0-beta.1) on 2026-09-10; the
`_set_model_prop` patch against v3.7-dev @ b1af5bb on 2026-09-12.

### 4.1 Things that are the same on both and are NOT bugs [both]
- `resolve_path()` returns a **Response object**, not a string: `real = getattr(resp, "result", resp)`.
- There is **no** `get_file()` / `put_file()` on `CommandConnection`. Use `resolve_path()` + `open()`.
- `from dsf.object_model import HttpEndpointType` and `from dsf.http import HttpResponseType` work on both.

---
## 5. dsf-python 3.6 vs 3.7 API Differences (verified 2026-09-12)
| Topic | 3.6 (`v3.6-dev`) | 3.7 (`v3.7-dev`) | What the daemon does |
|---|---|---|---|
| `SubscribeConnection.__init__` | `(subscription_mode, filter_str="", filter_list=None, debug=False)` | `(subscription_mode, filter_list=[], debug=False)` — **`filter_str` removed, second positional is now the list** | Passes only `subscription_mode`; if a filter is ever added, pass `filter_list=[...]` **by keyword** |
| `BaseConnection` connect method | `connect(init_message, socket_file)` | `_connect(init_message, socket_file)` | Patches both names (§4) |
| `SubscribeConnection.get_object_model()` in PATCH mode | Every call blocks for the next full model | First call: full model. Later calls **drain queued patches without blocking** and return the cached model; also runs `subscribe_to_keys` callbacks | Calls `get_object_model()` once, then `get_object_model_patch()` in the loop — identical on both |
| Model classes | Hand-written `@property` + `_x` storage; getter-only props are skipped when deserializing | `model_prop` / `nullable_model_prop` descriptors from `dsf.object_model.utils`; non-nullable props reject `None` (§4) | `_patch_property_setter()` handles both |
| `PluginManifest.data` | plain `dict` (bug, §4) | `ModelDictionary` | Patch is 3.6-only |
| `set_plugin_data(plugin, key, value)` | `value: str` | `value: object` | Always sends strings |
| Python requirement | `>= 3.7` | `>= 3.11` | CI tests 3.10–3.12 with dsf mocked; real 3.7 spot checks need 3.11+ |
| `has_data_available()` | absent | present | Not used |
| `subscribe_to_keys()` | absent | present | Not used |

Same on both: `CommandConnection(debug=False, timeout=3)`; `TimeoutError` from
`get_object_model_patch()` when idle (3 s default) is the loop heartbeat — catch it, don't exit.

---
## 6. DSF ObjectModel API Rules [both]
| Pattern | Correct | Wrong |
|---------|---------|-------|
| Access typed object attributes | `getattr(board, "firmware_version", "")` | `board.get("firmwareVersion")` |
| Access plugin dict | `model.plugins.get("Vigil")` | `getattr(model.plugins, "Vigil")` |
| Access directories | `getattr(model.directories, "system", "")` | `model.directories["system"]` |
| JSON → Python naming | `firmware_version` (snake_case) | `firmwareVersion` (camelCase) |
- `model.plugins` is a `ModelDictionary` (dict subclass) — `.get()` is fine.
- `Board`, `Plugin`, `Directories` are **typed ModelObjects** — use `getattr()`.
- dsf-python auto-converts JSON camelCase to Python snake_case.
- Loop pattern: first `get_object_model()` for the full model, then `get_object_model_patch()`
  + `object_model.update_from_json(patch)` for every subsequent update.

---
## 7. File I/O on the Printer [both]
```
Virtual path:   "0:/sys/config.g"
                     ↓  cmd.resolve_path("0:/sys")  → Response, take .result
Real FS path:   "/opt/dsf/sd/sys/config.g"
```
1. At daemon startup, call `cmd.resolve_path()` for each directory.
2. Store the mapping `{"0:/sys/": "/opt/dsf/sd/sys/"}`; DSF omits trailing slashes — add them.
3. Use standard `open()` on the resolved path.

---
## 8. Persistent Data Location [both]
```
/opt/dsf/plugins/Vigil/    ← WIPED on uninstall/upgrade
/opt/dsf/sd/Vigil/         ← survives upgrades: settings, caches, user data go here
```

---
## 9. HTTP Endpoints [both]
DSF uses exact path matching (no path parameters); use query strings for dynamic values.
The endpoint mechanism is identical on both generations and is the only channel between
the shells and the daemon — which is why `core/` has no DWC dependency beyond the host adapter.
```python
ep = cmd.add_http_endpoint(HttpEndpointType.GET, "Vigil", "status")   # → /machine/Vigil/status
ep.set_endpoint_handler(handler)         # async def handler(http_conn): request = await http_conn.read_request() ...
await http_conn.send_response(200, json.dumps(body), HttpResponseType.JSON)
```
Frontend: plain `fetch('/machine/Vigil/status')`, check `resp.ok` before parsing; DWC does
not expose `$fetch` to plugins on either generation. Handlers return
`{"status": 200, "body": json.dumps(...)}`; network errors and config errors are reported
distinctly. Register endpoints before the subscribe loop starts.

---
## 10. Frontend Patterns
### 10.1 Shared rules [both]
- Keep the **Options API** in both shells (Vue 3 supports it) so the two `<script>` blocks
  stay near-identical and the diff between `ui36/` and `ui37/` is mostly templates.
- Components take the host adapter as a prop (default `createHost()`), so tests can mount
  them with a fake host; never import a store from a component.
- Chart.js is **4.x in shared code**. DWC 3.7 does not expose chart.js to plugins (bundled by
  the Vite build); DWC 3.6 ships 2.9 for its own charts, so the stage script vendors our 4.x
  into `<stage>/src/node_modules/`, which webpack finds before the checkout's copy.
- ESLint: no Vue preset at the root; `plugin:vue/recommended` for `src/ui36/**`,
  `plugin:vue/vue3-recommended` for `src/ui37/**`, `src/core/**`, `src/index.js`.

### 10.2 Vue 2.7 + Vuetify 2 shell [3.6 only]
- Reactivity: new object keys need `this.$set(obj, key, value)`; array index assignment is
  not reactive (`splice`/`push`); `beforeDestroy` is the teardown hook.
- Vuex reads go through the host adapter, not `mapState('machine/model', ...)`.

### 10.3 Vue 3.5 + Vuetify 4 shell [3.7 only]
- `v-model` on a component is `modelValue` / `update:modelValue`; teardown is `beforeUnmount`.
- Vuetify 4 renamed props: e.g. `dense` → `density`, `outlined` → `variant="outlined"`. A
  Vuetify 2 prop that survives a port is **valid markup**: only the running component knows
  it is wrong. The `tests/ui37/components.test.js` pattern mounts against real Vuetify 4 and
  fails on `[Vue warn]` / `Failed to resolve` — keep that for every ported component.
- `dwcPluginUnloaded` fires when the plugin is stopped from Settings → Plugins; unregister
  the route so the menu entry disappears without a reload.

---
## 11. Testing
### 11.1 Backend (pytest) [both]
`pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["dsf"]`. dsf-python is **not**
installed locally: mock `dsf`, `dsf.connections`, `dsf.http`, `dsf.object_model` in
`sys.modules` **before** importing the daemon via `importlib.util.spec_from_file_location`.
Mock ObjectModel objects with `SimpleNamespace`. Any new dsf-python patch gets a case in
`tests/test_dsf_patches.py`, which is parametrised over both library shapes
(`connect` = 3.6, `_connect` = 3.7); a 3.x-only patch must be shown to be inert on the other.

### 11.2 Frontend — two toolchains [both]
One `package.json` cannot hold both Vue majors, and the root must be the Vue 3 one because
DWC 3.7's builder reads and installs from it. Hence:
```bash
npm ci && npm --prefix tests/ui36 ci   # once after cloning
npm test            # vitest: tests/core + tests/ui37 (Vue 3, dwc-plugin-test-kit: mountInDwc, setModel)
npm run test:ui36   # jest:   tests/ui36 (Vue 2.7, @vue/vue2-jest, @vue/test-utils 1.x)
npm run lint
pytest tests/ -v
```
- `tests/ui36/jest.config.js` pins `vue`, `vuex`, `vuetify`, `@vue/test-utils` to the nested
  `node_modules`; a missing pin shows up as a Vue 3 runtime failing to mount a Vue 2 component. [3.6 only]
- DWC modules are stubbed: `tests/ui36/dwc-stubs/{routes,store}.js` for `@/routes`, `@/store`
  [3.6 only]; the test kit's aliases plus `tests/dwc-stubs/machine.js` (adds `startSbcPlugin`)
  for `@/stores/machine` [3.7 only].
- `npm run check-ui36` (needs `DWC36_DIR=<3.6 checkout>`) compiles every `src/ui36/*.vue` with
  the checkout's Vue 2.7 compiler in ~1 s. It catches malformed SFCs, not wrong Vuetify props. [3.6 only]

---
## 12. Build, CI and Release [both]
- `ci.yml`: `python-tests` (3.10–3.12) → `frontend-tests` (Node 18: lint, vitest, nested
  Jest) → `build-dwc36` (Node 18, `stage-dwc36.mjs` + `build-plugin-pkg` in a v3.6-dev
  checkout) and `build-dwc37` (Node 22, `build-plugin-pkg.js ../plugin` in a v3.7-dev checkout).
- **3.6 is never built from the repo directly**: its builder copies the whole of
  `<pluginDir>/src` and would compile `ui37/` against Vuetify 2. Stage first. [3.6 only]
- **3.7's builder writes into the plugin directory** (`dist/`, `pkg/`, `Vigil-*.zip`,
  `Vigil-*-srcmap.zip`); they are gitignored and the local runner removes them. Address the
  package ZIP by exact name — `-srcmap.zip` sorts before `.zip`. [3.7 only]
- Run `npm ci` at the repo root before the 3.7 build so the builder's own
  `installPluginDependencies()` is a no-op; never let it resolve packages next to a Vite build. [3.7 only]
- CI artifacts are uploaded **unpacked** (GitHub wraps artifacts in a ZIP of their own; a
  ZIP-in-ZIP is not installable). `collect_zip` in `ci-local.sh` checks: `plugin.json` at the
  root, a built `dwc/js/Vigil.*.js`, `dsf/vigil-daemon.py`, no `__pycache__`, no nested ZIP,
  `dwcVersion` equal to the checkout's major.minor.
- `dsf/__pycache__` is stripped before every build — both builders copy `dsf/` verbatim and a
  local `pytest` run leaves bytecode behind.
- `release.yml`: one tag, two assets. 3.6 is built against the newest `v3.6.x` tag; 3.7 against
  the newest `v3.7.x` tag, falling back to the newest `v3.7.0-(alpha|beta|rc).N`, then `v3.7-dev`.
  The version is stamped into `plugin.json`/`package.json` once so both ZIPs carry the same one.
- **Pre-releases (`X.Y.Z-(alpha|beta|rc).N`) may only be cut from `main`**; the `guard` job
  refuses any other ref. Never dispatch `release.yml` on a feature branch.
- `scripts/ci-local.sh` mirrors all of this locally in `.ci-local/` (`DWC36_REF`, `DWC37_REF`,
  `BUILD37_DOCKER=0`, `PYTHON` overrides). `ci.yml` and `ci-local.sh` change together.

---
## 13. Quick Checklist for a Change
1. [ ] Which generation does this touch? Tag every note/patch/comment per Rule 2.
2. [ ] Verified the API against **both** `v3.6-dev` and `v3.7-dev` sources (Rule 1).
3. [ ] Logic in `core/`; only templates/imports differ between `ui36/` and `ui37/`.
4. [ ] New `set_plugin_data` keys pre-declared in `plugin.json#data`.
5. [ ] New dsf-python patch: at the top of the daemon, `try/except`, generation-tagged
       comment, test in `test_dsf_patches.py` for both shapes.
6. [ ] `getattr()` on typed ModelObjects, `.get()` only on ModelDictionaries.
7. [ ] Persistent data under `/opt/dsf/sd/Vigil/`, never the plugin dir.
8. [ ] Ported component mounted against real Vuetify 4 with the no-warnings assertion (3.7)
       and compiled via `check-ui36` (3.6).
9. [ ] `npm test`, `npm run test:ui36`, `npm run lint`, `pytest` green; `ci-local.sh build`
       produces both ZIPs when the build or manifest changed.
10. [ ] Real-hardware items still owed are listed in `docs/PLAN-dwc37-dual-build.md` §10.

---
## 14. Common Pitfalls
| Pitfall | Tag | Fix |
|---------|-----|-----|
| `plugin.data` always empty | 3.6 only | Monkey-patch `PluginManifest.__init__` to use `ModelDictionary` |
| `"customInfo": null` → `TypeError ... Got NoneType`, patch dropped | 3.7 only | Wrap `dsf.object_model.utils._set_model_prop`: `None` → `update_from_json(None)` / `[]` for dict/collection props |
| `connect()` `recv(50)` truncates init message (`Unterminated string`) | both | Patch a full-JSON read onto `connect` **and** `_connect` (3.7 renamed it) |
| `BoardState` crash on `timedOut` | both | Replace enum + safe setter |
| `NetworkInterfaceType` crash on `ethernet` | 3.6 only | Replace enum + safe setter |
| `Axis.letter` crash on `'\x00'` | both | Safe setter → `AxisLetter.none` |
| `SubscribeConnection(mode, "filter")` — second positional means different things | both | Pass `filter_list=[...]` by keyword; `filter_str` does not exist on 3.7 |
| `get_object_model()` called in the PATCH loop | both | Once for the full model, then `get_object_model_patch()`; on 3.7 later calls silently drain patches instead of blocking |
| `resolve_path()` returns an object | both | `getattr(response, "result", response)` |
| `get_file()`/`put_file()` don't exist | both | `resolve_path()` + `open()` |
| `state.plugins`/`model.plugins` is a Map | both | Guard with `instanceof Map` |
| Plugin dir wiped on upgrade | both | Use `/opt/dsf/sd/Vigil/` |
| "partially started" after installing an update | both | `ensureBackendRunning(host)` → `startSbcPlugin` when `pid <= 0` (§3.3) |
| `sbcData` in the manifest | 3.6 verified, 3.7 unchecked | Use `data` only |
| camelCase in Python | both | dsf-python converts to snake_case |
| Trailing slashes missing on directories | both | Add them |
| Tests import the daemon before the dsf mocks | both | `sys.modules` mocks first, then `spec_from_file_location` |
| Patch tested against one library shape only | both | `test_dsf_patches.py` is parametrised over both; add the case |
| New object keys not reactive | 3.6 only | `this.$set()` |
| Vuetify 2 prop surviving a port (`dense`, `outlined`, …) | 3.7 only | Mount against real Vuetify 4, fail on `[Vue warn]` |
| `@/routes` / `@/store` imported in 3.7 code | 3.7 only | Use `@/plugins` and `@/stores/machine` |
| Pointing DWC 3.7's builder at a tree with Vue 2 packages at the root | 3.7 only | Root `package.json` is the Vue 3 one; Vue 2 lives in `tests/ui36/` |
| Pointing DWC 3.6's builder at the repo | 3.6 only | `scripts/stage-dwc36.mjs` first |
| 3.7 build on Node < 22 | 3.7 only | `ci-local.sh` falls back to `node:22-slim`; CI uses a separate `setup-node` |
| Nested ZIP in a CI artifact | both | Upload the unpacked tree |
| `dsf/__pycache__` in the ZIP | both | Strip before staging/building |
| Pre-release dispatched on a feature branch | both | Only from `main`; the `guard` job refuses otherwise |
| Untagged note in this guide | both | Tag it per Rule 2 before merging |
