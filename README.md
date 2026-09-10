# Vigil — Machine Usage Monitoring for Duet 3D Printers

A [DuetWebControl](https://github.com/Duet3D/DuetWebControl) plugin that tracks machine usage, component wear, and maintenance history on Duet 3D printers with an SBC.

## Features

- **Three-tier counters** — lifetime (never reset), service (reset per maintenance cycle), and session (current runtime)
- **Time tracking** — machine hours, print time, pause duration, heater warmup
- **Job statistics** — total jobs, completions, cancellations with pie chart breakdown
- **Movement tracking** — per-axis travel distance (X, Y, Z) with homing grace period to avoid false readings
- **Filament tracking** — per-extruder net filament usage (positive extrusion only, excluding retracts)
- **Thermal tracking** — per-heater on-time and full-load seconds (95%+ duty cycle)
- **Fan tracking** — per-fan runtime
- **System vitals** — board MCU temp, Vin, 12V rail (daily min/max); SBC CPU temp, load, free memory; firmware/SBC uptime with reboot detection; free storage
- **30-day history** — automatic daily snapshots with interactive chart and metric drill-down
- **Service log** — log maintenance events, reset individual counters with full audit trail
- **Data export** — JSON and CSV formats

## Requirements

- Duet 3D printer with SBC (Raspberry Pi or similar)
- DSF v3.6+
- DuetWebControl v3.6+
- Python 3.10+

## Installation

There is one ZIP per DuetWebControl generation — they are different framework stacks,
and DWC refuses to install the wrong one (it compares the package's `dwcVersion` against
its own, but only after the upload):

| Your DuetWebControl | Download |
|---|---|
| 3.6.x | `Vigil-<version>-dwc36.zip` |
| 3.7.x | `Vigil-<version>-dwc37.zip` |

Upload it through DuetWebControl: **Settings > Plugins > Install Plugin**, then click
**Start** next to Vigil.

### Updating

Installing a newer ZIP over an existing installation is an *upgrade*: DSF stops the
SBC daemon, replaces the files, and — by design — does **not** start it again
(`InstallPlugin` sets `pid = -1`, and the plugin is removed from the DSF autostart
list). The DWC part stays enabled in your browser settings, so DWC reports the
plugin as **partially started** with all HTTP endpoints returning 404.

Vigil recovers from this on its own: as soon as DWC loads its resources it notices
the stopped daemon and asks DSF to start it, which also restores the boot autostart
entry. If that does not work — for example because DSF refused the start — open
**Plugins → Vigil**; a warning banner with a **Start Backend** button is shown while
the daemon is down. Pressing **Start** in **Settings > Plugins** does the same thing.

Reload DWC (Ctrl+Shift+R) after the upgrade so the browser picks up the new
frontend chunks — the file names change with every build.

## Troubleshooting

### Plugin state is "partially started"

DWC shows this when the SBC part and the DWC part disagree — either the daemon is
not running while the DWC part is enabled, or the other way around.

1. **After an upgrade** — expected, see [Updating](#updating). Vigil starts the
   daemon itself once DWC loads it; reload DWC if the state does not clear, or use
   the **Start Backend** button on the Vigil page.
2. **Start does not stick** (state falls back to "partially started" / "stopped"):
   the daemon exited. Vigil logs the reason to stderr, which DSF captures:
   ```bash
   journalctl -u duetpluginservice -n 100
   ```
   Startup failures are printed with a full traceback.
3. **Daemon runs but the dashboard is missing** — the DWC part failed to load and
   DWC disabled it. Check the browser console, reload with Ctrl+Shift+R, then press
   **Start** again.

If the daemon is started before `duetcontrolserver` is ready (boot, DSF restart),
Vigil retries the DCS connection for ~30 s before giving up instead of exiting
immediately.

## Architecture

```
src/
  index.js                  # Entry point every DWC builder compiles
  core/                     # Framework-neutral, shipped to every DWC generation
    host.js                 # The DWC seam: object model read + start the backend
    backend.js              # SBC backend state (PID lookup, start, auto-recovery)
    api.js                  # Calls to the daemon's DSF HTTP endpoints
    charts.js               # Chart.js 4 configuration for all four charts
    format.js               # Duration / distance / temperature / byte formatting
  ui36/                     # DWC 3.6 shell (Vue 2.7 + Vuetify 2.7)
    index.js                # Plugin registration, recovers a stopped backend
    host.js                 # Vuex implementation of the host adapter
    VigilDashboard.vue      # Main dashboard view
    components/             # UI components (charts, cards, dialogs)
  ui37/                     # DWC 3.7 shell (Vue 3.5 + Vuetify 4) — same files
    index.js                # As above, plus unregisterRoute on dwcPluginUnloaded
    host.js                 # Pinia implementation of the host adapter
    VigilDashboard.vue
    components/

dsf/                        # Backend (Python, runs on SBC)
  vigil-daemon.py           # Main daemon — DSF subscription & lifecycle
  vigil_tracker.py          # Counter logic & ObjectModel diffing
  vigil_persistence.py      # Crash-safe atomic file I/O with checksums
  vigil_api.py              # HTTP endpoint handlers
  vigil_time.py             # Time formatting utilities
```

Data is persisted to `/opt/dsf/sd/Vigil/` using atomic writes with SHA-256 checksums and XOR parity recovery, so it survives plugin upgrades and unexpected shutdowns.

## Development

### Prerequisites

```bash
npm ci                      # root: Vue 3 toolchain (vitest, eslint, build helpers)
npm --prefix tests/ui36 ci  # nested: Vue 2.7 toolchain for the DWC 3.6 shell's tests
pip install pytest
```

### Tests

The frontend has two test toolchains, because the two UI shells are two Vue majors and
one `package.json` cannot hold both — the root is the Vue 3 one, since that is what DWC
3.7's plugin builder reads and installs from.

```bash
npm test          # vitest: src/core/ + src/ui37/ (Vue 3, dwc-plugin-test-kit)
npm run test:ui36 # jest:   src/ui36/ (Vue 2.7) — nested project in tests/ui36/
npm run lint      # eslint, Vue 2 rules for ui36/ and Vue 3 rules for the rest
pytest tests/ -v  # the Python daemon
```

`tests/ui36/` has its own `package.json`, lockfile and `node_modules`; `npm run
test:ui36` does not install them, so run `npm --prefix tests/ui36 ci` once after
cloning (`scripts/ci-local.sh frontend` does it for you).

### Building

DWC 3.6 and 3.7 are different framework stacks (Vue 2.7 / Vuetify 2 / Vuex against Vue
3.5 / Vuetify 4 / Pinia), and DWC refuses to install a package built for the other one —
it compares the manifest's `dwcVersion` against its own major.minor. So there are two
packages, built by each generation's own plugin builder from one source tree and one
`plugin.json` (`"dwcVersion": "auto-major"`, which each builder resolves for itself).

| Your DWC | Install |
|---|---|
| 3.6.x | `Vigil-<version>-dwc36.zip` |
| 3.7.x | `Vigil-<version>-dwc37.zip` |

The easy way to build either is the local CI runner, which keeps its DWC checkouts in
`.ci-local/`:

```bash
scripts/ci-local.sh build36     # -> .ci-local/dist/Vigil-<version>-dwc36.zip
scripts/ci-local.sh build37     # -> .ci-local/dist/Vigil-<version>-dwc37.zip
scripts/ci-local.sh build       # both
```

**DWC 3.7** builds with Vite 8 and needs Node >= 22; the runner falls back to a
`node:22-slim` container when the host Node is older (`BUILD37_DOCKER=0` to refuse
instead). Its builder is pointed straight at the repo and compiles `src/index.js`, which
imports `ui37` only. Note that it writes its outputs *into the plugin directory* — the
working tree — so `dist/`, `pkg/` and `Vigil-*.zip` are gitignored and the runner
removes them again on every exit path.

**DWC 3.6** is never built against the repo directly. Its builder copies (and compiles
from) the whole of `<pluginDir>/src`, which would mean feeding Vuetify 4 sources to a
3.6 checkout, so `scripts/stage-dwc36.mjs` first assembles a tree holding only
`src/core/`, `src/ui36/`, `dsf/`, `plugin.json` and a generated `src/index.js`. It also
vendors the plugin's own Chart.js 4 into that tree: DWC 3.6 ships Chart.js 2.9 and its
own charts are written against it, so the plugin carries its copy rather than upgrading
the checkout. By hand:

```bash
git clone --branch v3.6-dev https://github.com/Duet3D/DuetWebControl.git ../DuetWebControl
cd ../DuetWebControl && npm install && cd -
npm ci
node scripts/stage-dwc36.mjs /tmp/vigil-stage-36
cd ../DuetWebControl
npm run build-plugin-pkg -- /tmp/vigil-stage-36
```

Either ZIP *is* the installable plugin package (`plugin.json` sits at its root, with
`dwcFiles` / `dsfFiles` listing its contents) — upload it as-is.

`npm run check-ui36` compiles every `src/ui36/*.vue` with the 3.6 checkout's own Vue 2.7
compiler in about a second (`DWC36_DIR=<checkout>`). It catches malformed SFCs, not
wrong Vuetify props — only a real DWC 3.6 catches those.

### Running CI locally

`scripts/ci-local.sh` reproduces the GitHub Actions pipeline
(`.github/workflows/ci.yml`) on a workstation. Everything it needs lives in the
gitignored `.ci-local/` directory (Python virtualenv, DuetWebControl checkouts, staged
source trees, built ZIPs) — nothing is installed system-wide.

```bash
scripts/ci-local.sh            # python, frontend, build (default)
scripts/ci-local.sh python     # pytest in .ci-local/venv
scripts/ci-local.sh frontend   # npm ci + lint + vitest (core, ui37) + jest (ui36)
scripts/ci-local.sh build36    # DWC 3.6 checkout + stage + build-plugin-pkg + ZIP checks
scripts/ci-local.sh build37    # DWC 3.7 checkout + build-plugin-pkg + ZIP checks
scripts/ci-local.sh build      # build36 + build37
scripts/ci-local.sh matrix     # pytest on Python 3.10-3.12 via Docker
```

The `matrix` stage needs Docker; it mirrors the CI's Python version matrix, which a
single local interpreter cannot cover.

The build stages temporarily run `scripts/version.js --write` (as CI does) and restore
`plugin.json` / `package.json` afterwards, so the working tree stays clean. They also
drop `dsf/__pycache__` before building — every DWC builder copies `dsf/` verbatim, so
bytecode left behind by a previous `pytest` run would otherwise end up inside the plugin
ZIP. Each ZIP is copied to `.ci-local/dist/` under a name carrying its DWC generation,
after its layout and manifest are verified (`plugin.json` at the root, a built DWC JS
resource, the daemon, no bytecode, no nested ZIP, and a `dwcVersion` matching the
checkout it was built against).

Overrides: `DWC36_REF=<ref>` / `DWC37_REF=<ref>` select the DuetWebControl refs the two
packages are built against (defaults `v3.6-dev` and `v3.7-dev`), `BUILD37_DOCKER=0`
refuses the Node 22 container fallback instead of using it, and `PYTHON=<interpreter>`
selects the interpreter used for the venv.

## License

[MIT](https://opensource.org/licenses/MIT)

Copyright (c) Meltingplot GmbH
