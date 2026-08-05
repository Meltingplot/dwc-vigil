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

Upload the plugin ZIP through DuetWebControl: **Settings > Plugins > Install Plugin**, then click **Start** next to Vigil.

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
src/                        # Frontend (Vue 2.7 + Vuetify 2.7)
  index.js                  # Plugin registration, recovers a stopped backend
  VigilDashboard.vue        # Main dashboard view
  backend.js                # SBC backend state (PID lookup, start, auto-recovery)
  routes.js / store.js      # Jest-only stubs for DWC's @/routes and @/store
  components/               # UI components (charts, cards, dialogs)

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
npm ci
pip install pytest
```

### Tests

```bash
# Frontend
npm test

# Linting
npm run lint

# Backend
pytest tests/ -v
```

### Building

The plugin is built using the DWC plugin build system:

```bash
git clone --branch v3.6-dev https://github.com/Duet3D/DuetWebControl.git ../DuetWebControl
cd ../DuetWebControl
npm install
npm run build-plugin ../dwc-vigil
```

The resulting ZIP will be in `DuetWebControl/dist/`.

## License

[MIT](https://opensource.org/licenses/MIT)

Copyright (c) Meltingplot GmbH
