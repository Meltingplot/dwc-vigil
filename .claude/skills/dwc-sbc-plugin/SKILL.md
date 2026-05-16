---
name: dwc-sbc-plugin
description: Bootstrap or extend a Duet Web Control (DWC) / Duet Software Framework (DSF/SBC) plugin for Duet 3 boards. Use when the user wants to create a new DWC plugin, add an SBC (Single Board Computer) Python daemon, register HTTP endpoints with DSF, persist plugin data via the ObjectModel, or write tests for a DWC/DSF plugin. Targets DWC 3.6 (Vue 2.7 + Vuetify 2.7 + Vuex 3) and DSF v3.6 (dsf-python).
---

# DWC + DSF Plugin Skill

Distilled from building `dwc-meltingplot-config` and `dwc-vigil`. Targets **DWC 3.6
(`v3.6-dev`)** — Vue 2.7 + Vuetify 2.7 + Vuex 3 — and **DSF v3.6** Python backend.

---

## ⚠️ MANDATORY: Never guess API signatures

`dsf-python`, DWC, and DSF are **not installed locally**. Before writing against any
interface, clone the upstream source and read the actual code:

```bash
git clone --branch v3.6-dev --depth 1 https://github.com/Duet3D/dsf-python.git /tmp/dsf-python
git clone --branch v3.6-dev --depth 1 https://github.com/Duet3D/DuetWebControl.git /tmp/DuetWebControl
```

Key files in `dsf-python`:

- `src/dsf/connections/subscribe_connection.py` — `SubscribeConnection(subscription_mode, filter_str="", filter_list=None)`
- `src/dsf/connections/command_connection.py` — `CommandConnection(debug=False, timeout=3)`
- `src/dsf/connections/base_command_connection.py` — `add_http_endpoint()`, `set_plugin_data()`, `resolve_path()`
- `src/dsf/http.py` — `HttpEndpointConnection`, `HttpEndpointUnixSocket`, `HttpResponseType`
- `src/dsf/connections/__init__.py` — `SubscriptionMode`, `InterceptionMode`, `ConnectionMode`
- `src/dsf/object_model/object_model.py` — `ObjectModel.boards`, `.plugins`, `.state`, `.directories`
- `src/dsf/object_model/boards/boards.py` — `Board.firmware_version`, `.name`, `.state`
- `src/dsf/object_model/plugins/plugin_manifest.py` — `PluginManifest.data`, `.id`
- `src/dsf/object_model/directories/directories.py` — `Directories.system`, `.macros`

---

## Workflow

Make a todo list for this workflow and work through it in order.

### 1. Scaffold the manifest (`plugin.json`)

```jsonc
{
  "id": "MyPlugin",
  "name": "My Plugin",
  "author": "...",
  "version": "0.0.0",
  "license": "MIT",
  "dwcVersion": "auto-major",
  "sbcRequired": true,            // omit for DWC-only plugins
  "sbcDsfVersion": "auto-major",
  "sbcExecutable": "my-daemon.py",
  "sbcOutputRedirected": true,
  "sbcPermissions": [
    "commandExecution",
    "objectModelReadWrite",
    "registerHttpEndpoints",
    "fileSystemAccess"
  ],
  "sbcPythonDependencies": ["dsf-python"],
  "data": {                       // pre-declare EVERY key used with set_plugin_data
    "status": "idle"
  }
  // "sbcData": {}                // ⚠️ DSF v3.6 IGNORES this field — never use it
}
```

Rules:
- `data` is the only field DSF reads for plugin key-value storage.
- Every key that `cmd.set_plugin_data(id, key, value)` writes **must** be pre-declared in `data`.
- `sbcData` is silently ignored — there is no `SbcData` property in the DSF ObjectModel.

### 2. Frontend registration (`src/index.js`)

```javascript
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
- Browser path becomes `/plugins/MyPlugin`.
- Icons: `mdi-*` (Material Design Icons).

### 3. Patch the four known DSF Python bugs

Wrap each patch in `try/except ImportError: pass` at the top of the daemon so tests
run without the real dsf library.

**3a. `plugin.data` is always empty** — `PluginManifest.__init__` uses a plain `dict`,
which deserialization skips. Replace with `ModelDictionary`:

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

**3b. `resolve_path()` returns a Response object, not a string:**

```python
response = cmd.resolve_path("0:/sys")
real_path = getattr(response, "result", response)
if not isinstance(real_path, str):
    real_path = str(real_path)
```

**3c. `BoardState` enum missing values** — DSF reports states like `timedOut` that
aren't in the enum; the setter raises `ValueError` and crashes `get_object_model()`:

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

**3d. `get_file()` / `put_file()` do not exist** — use `cmd.resolve_path()` +
standard `open()` for all file I/O.

### 4. ObjectModel access rules

| Pattern                  | Correct                                            | Wrong                                  |
|--------------------------|----------------------------------------------------|----------------------------------------|
| Typed object attributes  | `getattr(board, "firmware_version", "")`           | `board.get("firmwareVersion")`         |
| Plugin dict              | `model.plugins.get("MyPlugin")`                    | `getattr(model.plugins, "MyPlugin")`   |
| Directories              | `getattr(model.directories, "system", "")`         | `model.directories["system"]`          |
| JSON → Python naming     | `firmware_version` (snake_case)                    | `firmwareVersion` (camelCase)          |

- `model.plugins` is a `ModelDictionary` (dict subclass) — `.get()` is fine.
- `Board`, `Plugin`, `Directories` are typed `ModelObject`s — use `getattr()`.
- dsf-python auto-converts JSON camelCase to Python snake_case.

### 5. Subscription loop

```python
# Open with subscription_mode; pass filters as a LIST, not pipe-delimited string
sub = SubscribeConnection(SubscriptionMode.PATCH, filter_list=["state/status", "boards/**"])
sub.connect()

model = sub.get_object_model()                    # first call: full model
while True:
    try:
        patch = sub.get_object_model_patch()      # loop: JSON patches
        # apply patch / react
    except TimeoutError:
        # 3 s default timeout is a heartbeat — use it for periodic saves & shutdown checks
        pass
```

- `filter_str` is obsolete — use `filter_list=[...]`.
- Never call `get_object_model()` inside the patch loop.

### 6. Virtual ↔ real filesystem paths

```
Virtual path:  "0:/sys/config.g"
                    ↓  cmd.resolve_path("0:/sys")
Real FS path:  "/opt/dsf/sd/sys/config.g"
```

1. At daemon startup, call `cmd.resolve_path()` once per directory.
2. Store the mapping: `{"0:/sys/": "/opt/dsf/sd/sys/"}`.
3. Use standard `open()` with the resolved path for all I/O.
4. DSF omits trailing slashes (`0:/sys`) — add them yourself (`0:/sys/`).

### 7. Persistent data location

```
/opt/dsf/plugins/MyPlugin/    ← ⚠️ WIPED on uninstall/upgrade
/opt/dsf/sd/MyPlugin/         ← ✅ Survives upgrades; safe for settings & data
```

- Full uninstall deletes the entire plugin directory.
- During upgrade DSF removes tracked files but extras survive.
- **Always** store settings, caches, and user data under `/opt/dsf/sd/YourPlugin/`.

### 8. HTTP endpoints

DSF uses **exact path matching** — no path parameters. Use query strings for
dynamic values.

```python
def register_endpoints(cmd, manager):
    endpoints = []
    ROUTES = [
        ("GET",  "status",  handle_status),
        ("POST", "sync",    handle_sync),
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

def handle_status(_cmd, manager, _body, _queries):
    return {"status": 200, "body": json.dumps({"status": "ok"})}
```

Frontend uses plain `fetch()` — DWC does not expose `$fetch` to plugins. Always check
`resp.ok` before parsing.

### 9. Frontend: Vuex plugin data access

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
    })
  }
}
```

**Critical:** `state.plugins` is a `Map`, not a plain object — always guard with
`instanceof Map`.

Vue 2 reactivity gotchas:
- New object keys: use `this.$set(obj, 'newKey', value)`.
- Array index assignment is not reactive — use `splice` / `push` / `Vue.set`.

### 10. Tests

**Backend (`pyproject.toml`):**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["dsf"]
```

Mock dsf modules **before** importing the daemon (the dsf library is not installed
locally):

```python
import sys, types, importlib.util
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def mock_dsf(monkeypatch):
    dsf = types.ModuleType("dsf")
    dsf_conn = types.ModuleType("dsf.connections")
    dsf_http = types.ModuleType("dsf.http")
    dsf_om = types.ModuleType("dsf.object_model")
    class FakeHttpResponseType:
        JSON = "JSON"; File = "File"; PlainText = "PlainText"
    dsf_http.HttpResponseType = FakeHttpResponseType
    dsf_conn.CommandConnection = MagicMock
    for name, mod in [("dsf", dsf), ("dsf.connections", dsf_conn),
                       ("dsf.http", dsf_http), ("dsf.object_model", dsf_om)]:
        monkeypatch.setitem(sys.modules, name, mod)

def _import_daemon():
    spec = importlib.util.spec_from_file_location("daemon", "dsf/my-daemon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

Mock ObjectModel objects with `SimpleNamespace`:

```python
from types import SimpleNamespace
model = SimpleNamespace(
    boards=[SimpleNamespace(firmware_version="3.5.1", name="Duet 3")],
    directories=SimpleNamespace(system="0:/sys", macros="0:/macros"),
    plugins={"MyPlugin": SimpleNamespace(data={"myKey": "value"})}
)
```

**Frontend (`jest.config.js`):**

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

`tests/frontend/setup.js`:

```javascript
import Vue from 'vue'
import Vuetify from 'vuetify'
Vue.use(Vuetify)
document.body.setAttribute('data-app', 'true')
global.createVuetify = () => new Vuetify()
```

Vuex store mock with plugin data as a `Map`:

```javascript
function createStore(pluginData = {}) {
  return new Vuex.Store({
    modules: {
      'machine/model': {
        namespaced: true,
        state: { plugins: new Map([['MyPlugin', { data: pluginData }]]) }
      }
    }
  })
}
```

### 11. CI (`.github/workflows/ci.yml`)

Three jobs: Python matrix tests → Frontend lint+tests → DWC build (check out
`Duet3D/DuetWebControl@v3.6-dev` alongside the plugin and run `npm run build-plugin
../plugin`). Upload the resulting `dist/*.zip` as an artifact.

---

## Quick-Start Checklist

1. [ ] `plugin.json` with `data` field (not `sbcData`) — pre-declare all keys
2. [ ] `src/index.js` with `registerRoute`
3. [ ] Main Vue component using Vuetify 2.7
4. [ ] Plugin data access via `state.plugins.get('ID')?.data` with `Map` guard
5. [ ] Python daemon with **all four** DSF monkey-patches at the top
6. [ ] Resolve virtual paths at startup; store the mapping
7. [ ] Persistent data under `/opt/dsf/sd/YourPlugin/`
8. [ ] HTTP endpoints registered with `cmd.add_http_endpoint()`
9. [ ] `getattr()` for ObjectModel typed objects, `.get()` only for `ModelDictionary`
10. [ ] pytest with dsf module mocks set up **before** daemon import
11. [ ] Jest with Vue 2 test-utils + Vuetify setup
12. [ ] CI: Python tests → Frontend tests → DWC build
13. [ ] `cmd.set_plugin_data()` to write, `plugin.data[key]` to read
14. [ ] Distinct error responses for network vs. config failures

---

## Pitfall Cheat Sheet

| Pitfall                                          | Fix                                                                    |
|--------------------------------------------------|------------------------------------------------------------------------|
| `plugin.data` always empty                       | Monkey-patch `PluginManifest.__init__` to use `ModelDictionary`        |
| `resolve_path()` returns object                  | `getattr(response, "result", response)`                                |
| `BoardState` crash on unknown values             | Replace enum + add safe setter                                         |
| `get_file()` / `put_file()` doesn't exist        | `resolve_path()` + `open()`                                            |
| `state.plugins` is a `Map`                       | Guard with `instanceof Map`                                            |
| Plugin dir wiped on upgrade                      | Store in `/opt/dsf/sd/YourPlugin/`                                     |
| `sbcData` ignored                                | Use `data` field only                                                  |
| camelCase in Python                              | dsf-python auto-converts to snake_case                                 |
| Dict `.get()` on typed objects                   | `getattr(obj, "attr", default)`                                        |
| Trailing slashes missing                         | Add them manually                                                      |
| Tests import daemon before mocks                 | Set up `sys.modules` mocks first, then import                          |
| Vue 2 reactivity for new keys                    | `this.$set()`                                                          |
| `SubscribeConnection()` missing args             | Constructor needs `subscription_mode`; filter via `filter_list`        |
| `get_object_model()` in PATCH loop               | First call full model; loop uses `get_object_model_patch()`            |
| `filter_str` pipe-delimited                      | Use `filter_list=[...]` instead                                        |
| `SubscribeConnection` 3 s timeout                | Catch `TimeoutError` — it's the heartbeat for saves & shutdown checks  |
| Guessing API signatures                          | Clone dsf-python v3.6 and read the actual source                       |
