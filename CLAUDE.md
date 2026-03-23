# DWC + DSF Plugin Developer Guide
> Condensed lessons learned from building `dwc-meltingplot-config`.
> Target: DWC 3.6 (`v3.6-dev`) — Vue 2.7 + Vuetify 2.7 + Vuex 3, DSF v3.6 Python backend.

## ⚠️ MANDATORY: Do Not Guess API Interfaces
**NEVER** guess or assume dsf-python, DWC, or DSF API signatures. Always clone the upstream
source and read the actual code before writing against any interface:
```bash
git clone --branch v3.6-dev --depth 1 https://github.com/Duet3D/dsf-python.git /tmp/dsf-python
```
Then read the relevant source file to verify constructor parameters, method signatures, and
enum values. Key files:
- `src/dsf/connections/subscribe_connection.py` — `SubscribeConnection(subscription_mode, filter_str="", filter_list=None)`
- `src/dsf/connections/command_connection.py` — `CommandConnection(debug=False, timeout=3)`
- `src/dsf/connections/base_command_connection.py` — `add_http_endpoint()`, `set_plugin_data()`, etc.
- `src/dsf/http.py` — `HttpEndpointConnection`, `HttpEndpointUnixSocket`, `HttpResponseType`
- `src/dsf/connections/__init__.py` — `SubscriptionMode`, `InterceptionMode`, `ConnectionMode`

---
## 1. Plugin Manifest (`plugin.json`)
```jsonc
{
  "id": "MyPlugin",
  "name": "My Plugin",
  "version": "0.0.0",
  "data": {
    "myKey": "defaultValue"        // Pre-declare ALL keys used with SetPluginData
  }
  // "sbcData": {}                 // ⚠️ DSF v3.6 IGNORES this field entirely — do NOT use
}
```
**Rules:**
- `data` is the only field DSF reads for plugin key-value storage.
- Every key you plan to write with `cmd.set_plugin_data(id, key, value)` **must** be pre-declared in `data`.
- `sbcData` is silently ignored — there is no `SbcData` property in the DSF ObjectModel.
---
## 2. Plugin Registration (Frontend)
```javascript
// src/index.js
import { registerRoute } from '@/routes'
import MyPlugin from './MyPlugin.vue'
registerRoute(MyPlugin, {
    Plugins: {
        MyPlugin: {
            icon: 'mdi-cog',
            caption: 'My Plugin',
            path: '/MyPlugin'
        }
    }
})
```
- `registerRoute` adds the entry to the Plugins menu automatically.
- Path becomes `/plugins/MyPlugin` in the browser.
- Icons: use `mdi-*` (Material Design Icons).
---
## 3. DSF Python Bugs You MUST Patch
All patches go at the top of your daemon file, wrapped in `try/except ImportError: pass` so tests work without the real dsf library.
### 3.1 `plugin.data` is always empty
`PluginManifest.__init__` creates `_data` as a plain `dict`. The deserialization method skips plain dicts. Fix: replace with `ModelDictionary`.
```python
try:
    from dsf.object_model.plugins.plugin_manifest import PluginManifest as _PM
    from dsf.object_model.model_dictionary import ModelDictionary as _MD
    _orig_init = _PM.__init__
    def _patched_init(self):
        _orig_init(self)
        self._data = _MD(False)
    _PM.__init__ = _patched_init
except ImportError:
    pass
```
### 3.2 `resolve_path()` returns a Response object, not a string
```python
response = cmd.resolve_path("0:/sys")
real_path = getattr(response, "result", response)
if not isinstance(real_path, str):
    real_path = str(real_path)
```
### 3.3 `BoardState` enum missing values (crashes `get_object_model()`)
DSF may report states like `timedOut` that aren't in the enum. The setter raises `ValueError`, which crashes the entire `get_object_model()` call.
```python
try:
    import dsf.object_model.boards.boards as _boards_mod
    from dsf.object_model.boards.boards import Board as _Board
    from enum import Enum
    class _PatchedBoardState(str, Enum):
        unknown = "unknown"
        flashing = "flashing"
        flashFailed = "flashFailed"
        resetting = "resetting"
        running = "running"
        timedOut = "timedOut"
    _boards_mod.BoardState = _PatchedBoardState
    def _safe_state_setter(self, value):
        try:
            if value is None or isinstance(value, _PatchedBoardState):
                self._state = value
            elif isinstance(value, str):
                self._state = _PatchedBoardState(value)
        except (ValueError, KeyError):
            self._state = _PatchedBoardState.unknown
    _Board.state = _Board.state.setter(_safe_state_setter)
except ImportError:
    pass
```
### 3.4 No `get_file()` / `put_file()` on CommandConnection
These methods **do not exist**. Use `cmd.resolve_path()` + standard `open()` for all file I/O.
---
## 4. DSF ObjectModel API Rules
| Pattern | Correct | Wrong |
|---------|---------|-------|
| Access typed object attributes | `getattr(board, "firmware_version", "")` | `board.get("firmwareVersion")` |
| Access plugin dict | `model.plugins.get("MyPlugin")` | `getattr(model.plugins, "MyPlugin")` |
| Access directories | `getattr(model.directories, "system", "")` | `model.directories["system"]` |
| JSON → Python naming | `firmware_version` (snake_case) | `firmwareVersion` (camelCase) |
- `model.plugins` is a `ModelDictionary` (dict subclass) — `.get()` is fine.
- `Board`, `Plugin`, `Directories` are **typed ModelObjects** — use `getattr()`.
- DSF auto-converts JSON camelCase to Python snake_case.
---
## 5. File I/O on the Printer
```
Virtual path:   "0:/sys/config.g"
                     ↓  cmd.resolve_path("0:/sys")
Real FS path:   "/opt/dsf/sd/sys/config.g"
```
**Pattern:**
1. At daemon startup, call `cmd.resolve_path()` for each directory.
2. Store the mapping: `{"0:/sys/": "/opt/dsf/sd/sys/"}`.
3. Use standard `open()` with the resolved path for all reads/writes.
**Trailing slashes:** DSF directory values lack them (`0:/sys`). Add them yourself (`0:/sys/`).
---
## 6. Persistent Data Location
```
/opt/dsf/plugins/MyPlugin/    ← ⚠️ WIPED on uninstall/upgrade
/opt/dsf/sd/MyPlugin/         ← ✅ Survives upgrades, safe for settings/data
```
- DSF deletes the entire plugin directory on full uninstall.
- During upgrade, DSF removes tracked files but extra files survive.
- **Always** store settings, caches, and user data under `/opt/dsf/sd/YourPlugin/`.
---
## 7. HTTP Endpoints
DSF uses exact path matching (no path parameters). Use query strings for dynamic values.
### Backend Registration
```python
def register_endpoints(cmd, manager):
    endpoints = []
    ROUTES = [
        ("GET",  "status",  handle_status),
        ("POST", "sync",    handle_sync),
        ("GET",  "diff",    handle_diff),
    ]
    for method, path, handler in ROUTES:
        ep = cmd.add_http_endpoint(method, f"/machine/MyPlugin/{path}")
        asyncio.ensure_future(_serve(ep, cmd, manager, handler))
        endpoints.append(ep)
    return endpoints
async def _serve(ep, cmd, manager, handler_func):
    while True:
        http_conn = await ep.accept()
        asyncio.ensure_future(_handle(http_conn, cmd, manager, handler_func))
async def _handle(http_conn, cmd, manager, handler_func):
    request = await http_conn.read_request()
    queries = getattr(request, "queries", {}) or {}
    body = getattr(request, "body", "") or ""
    response = handler_func(cmd, manager, body, queries)
    await http_conn.send_response(
        response.get("status", 200),
        response.get("body", ""),
        HttpResponseType.JSON,
    )
```
### Handler Pattern
```python
def handle_status(_cmd, manager, _body, _queries):
    return {"status": 200, "body": json.dumps({"status": "ok"})}
def handle_action(_cmd, manager, body, queries):
    file_param = queries.get("file", "")
    if not file_param:
        return {"status": 400, "body": json.dumps({"error": "file required"})}
    try:
        result = manager.do_something(file_param)
        return {"status": 200, "body": json.dumps(result)}
    except Exception as exc:
        logger.error("Error: %s", exc)
        return {"status": 500, "body": json.dumps({"error": str(exc)})}
```
### Frontend Calls
```javascript
async fetchStatus() {
  try {
    const resp = await fetch('/machine/MyPlugin/status')
    if (!resp.ok) {
      const err = await resp.json()
      this.error = err.error || 'Request failed'
      return
    }
    this.data = await resp.json()
  } catch (err) {
    this.error = 'Network error: ' + err.message
  }
}
```
- Use plain `fetch()` — DWC doesn't expose `$fetch` to plugins.
- Always check `resp.ok` before parsing.
---
## 8. Frontend: Vue 2.7 + Vuetify 2.7 Patterns
### Accessing Plugin Data from Vuex
```javascript
import { mapState } from 'vuex'
export default {
  computed: {
    ...mapState('machine/model', {
      pluginData(state) {
        // state.plugins is a Map in DWC 3.6
        if (state.plugins instanceof Map) {
          return state.plugins.get('MyPlugin')?.data || {}
        }
        // Fallback for tests (plain object)
        return state.plugins?.MyPlugin?.data || {}
      }
    }),
    myValue() {
      return this.pluginData.myKey || 'default'
    }
  }
}
```
**Critical:** `state.plugins` is a **Map**, not a plain object. Always guard with `instanceof Map`.
### Component Structure
```vue
<template>
  <v-card>
    <v-card-title>Title</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" md="6">
          <v-text-field v-model="inputValue" label="Setting" />
        </v-col>
      </v-row>
    </v-card-text>
    <v-card-actions>
      <v-btn color="primary" :loading="loading" @click="doAction">
        <v-icon left>mdi-play</v-icon> Run
      </v-btn>
    </v-card-actions>
  </v-card>
</template>
<script>
export default {
  name: 'MyComponent',
  props: {
    status: { type: String, default: '' }
  },
  data() {
    return { loading: false, inputValue: '' }
  },
  methods: {
    async doAction() {
      this.loading = true
      try {
        // ... fetch call
      } finally {
        this.loading = false
      }
    }
  }
}
</script>
```
### Reactivity Gotchas (Vue 2)
- Adding new object properties: use `this.$set(obj, 'newKey', value)` — plain assignment is not reactive.
- Array mutation: use `splice`, `push`, `Vue.set` — index assignment (`arr[i] = x`) is not reactive.
- Computed properties auto-update; `data()` properties need manual `$set` for nested additions.
---
## 9. Testing Strategy
### Backend (pytest)
**pyproject.toml:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["dsf"]
```
**Mocking DSF (required — dsf library not installed locally):**
```python
import sys, types
from unittest.mock import MagicMock
@pytest.fixture(autouse=True)
def mock_dsf(monkeypatch):
    dsf = types.ModuleType("dsf")
    dsf_conn = types.ModuleType("dsf.connections")
    dsf_http = types.ModuleType("dsf.http")
    dsf_om = types.ModuleType("dsf.object_model")
    class FakeHttpResponseType:
        JSON = "JSON"
        File = "File"
        PlainText = "PlainText"
    dsf_http.HttpResponseType = FakeHttpResponseType
    dsf_conn.CommandConnection = MagicMock
    for name, mod in [("dsf", dsf), ("dsf.connections", dsf_conn),
                       ("dsf.http", dsf_http), ("dsf.object_model", dsf_om)]:
        monkeypatch.setitem(sys.modules, name, mod)
```
**Import daemon AFTER mocks are set up:**
```python
def _import_daemon():
    spec = importlib.util.spec_from_file_location("daemon", "dsf/my-daemon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```
**Mock ObjectModel objects with SimpleNamespace:**
```python
from types import SimpleNamespace
model = SimpleNamespace(
    boards=[SimpleNamespace(firmware_version="3.5.1", name="Duet 3")],
    directories=SimpleNamespace(system="0:/sys", macros="0:/macros"),
    plugins={"MyPlugin": SimpleNamespace(data={"myKey": "value"})}
)
```
### Frontend (Jest 29 + @vue/test-utils 1.x)
**jest.config.js:**
```javascript
module.exports = {
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.vue$': '@vue/vue2-jest',
    '^.+\\.js$': 'babel-jest'
  },
  testMatch: ['**/tests/frontend/**/*.test.js'],
  setupFiles: ['./tests/frontend/setup.js'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' }
}
```
**tests/frontend/setup.js:**
```javascript
import Vue from 'vue'
import Vuetify from 'vuetify'
Vue.use(Vuetify)
document.body.setAttribute('data-app', 'true')
global.createVuetify = () => new Vuetify()
```
**Test pattern:**
```javascript
import { shallowMount } from '@vue/test-utils'
import MyComponent from '../../src/components/MyComponent.vue'
function mountComponent(propsData = {}) {
  return shallowMount(MyComponent, {
    vuetify: global.createVuetify(),
    propsData
  })
}
it('renders status', () => {
  const w = mountComponent({ status: 'ok' })
  expect(w.text()).toContain('ok')
})
```
**Mocking Vuex store with plugin data (Map):**
```javascript
function createStore(pluginData = {}) {
  return new Vuex.Store({
    modules: {
      'machine/model': {
        namespaced: true,
        state: {
          plugins: new Map([
            ['MyPlugin', { data: pluginData }]
          ])
        }
      }
    }
  })
}
```
---
## 10. CI/CD (.github/workflows/ci.yml)
```yaml
name: CI
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
jobs:
  python-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python-version }}" }
      - run: pip install pytest
      - run: pytest tests/ -v
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "18", cache: "npm" }
      - run: npm ci
      - run: npm run lint
      - run: npm test
  build:
    needs: [python-tests, frontend-tests]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { path: plugin }
      - uses: actions/checkout@v4
        with: { repository: Duet3D/DuetWebControl, ref: v3.6-dev, path: DuetWebControl }
      - uses: actions/setup-node@v4
        with: { node-version: "18" }
      - run: npm install
        working-directory: DuetWebControl
      - run: npm run build-plugin ../plugin
        working-directory: DuetWebControl
      - uses: actions/upload-artifact@v4
        with: { name: plugin-zip, path: "DuetWebControl/dist/*.zip" }
```
---
## 11. Upstream API Verification
The dsf-python, DWC, and DSF libraries are **not installed locally**. Before using any API:
```bash
# Clone upstream to /tmp and read the actual source
git clone --branch v3.6-dev --depth 1 https://github.com/Duet3D/dsf-python.git /tmp/dsf-python
git clone --branch v3.6-dev --depth 1 https://github.com/Duet3D/DuetWebControl.git /tmp/DuetWebControl
```
**Key source locations in dsf-python:**
- `src/dsf/object_model/object_model.py` — ObjectModel (`.boards`, `.plugins`, `.state`)
- `src/dsf/object_model/boards/boards.py` — Board (`.firmware_version`, `.name`)
- `src/dsf/object_model/plugins/plugin_manifest.py` — PluginManifest (`.data`, `.id`)
- `src/dsf/object_model/directories/directories.py` — Directories (`.system`, `.macros`)
- `src/dsf/connections/base_command_connection.py` — CommandConnection methods
---
## 12. Quick-Start Checklist for a New Plugin
1. [ ] Create `plugin.json` with `data` field (not `sbcData`) — pre-declare all keys
2. [ ] Create `src/index.js` with `registerRoute`
3. [ ] Create main Vue component with tabs/cards using Vuetify 2.7
4. [ ] Access plugin data via `state.plugins.get('ID')?.data` with Map guard
5. [ ] Create Python daemon with DSF monkey-patches at the top
6. [ ] Resolve virtual paths at startup, store mapping
7. [ ] Store persistent data in `/opt/dsf/sd/YourPlugin/`, not the plugin dir
8. [ ] Register HTTP endpoints with `cmd.add_http_endpoint()`
9. [ ] Use `getattr()` for ObjectModel access, never `.get()` on typed objects
10. [ ] Set up pytest with dsf module mocks (before daemon import)
11. [ ] Set up Jest with Vue 2 test utils and Vuetify setup
12. [ ] Create CI workflow: Python tests → Frontend lint+tests → DWC build
13. [ ] Use `cmd.set_plugin_data()` to write, `plugin.data[key]` to read
14. [ ] Handle network errors distinctly from config errors in responses
---
## 13. Common Pitfalls Summary
| Pitfall | Fix |
|---------|-----|
| `plugin.data` always empty | Monkey-patch `PluginManifest.__init__` to use `ModelDictionary` |
| `resolve_path()` returns object | Extract with `getattr(response, "result", response)` |
| `BoardState` crash on unknown values | Replace enum + add safe setter |
| `get_file()`/`put_file()` doesn't exist | Use `resolve_path()` + `open()` |
| `state.plugins` is a Map | Guard with `instanceof Map` |
| Plugin dir wiped on upgrade | Use `/opt/dsf/sd/YourPlugin/` |
| `sbcData` ignored | Use `data` field only |
| camelCase in Python | dsf-python auto-converts to snake_case |
| Dict `.get()` on typed objects | Use `getattr(obj, "attr", default)` |
| Trailing slashes missing | DSF omits them — add manually |
| Tests import daemon before mocks | Set up sys.modules mocks first, then import |
| Vue 2 reactivity for new keys | Use `this.$set()` |
| `SubscribeConnection()` missing args | Constructor requires `subscription_mode`; filter goes in `filter_str`/`filter_list`, NOT `connect()` |
| `get_object_model()` in PATCH loop | First call: `get_object_model()` for full model. Loop: `get_object_model_patch()` for JSON patches |
| Guessing API signatures | **Never guess** — clone dsf-python v3.6 and read the actual source before using any API |
