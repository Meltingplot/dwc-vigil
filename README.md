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

Upload the plugin ZIP through DuetWebControl: **Settings > Plugins > Install Plugin**.

Vigil starts automatically and begins tracking immediately.

## Architecture

```
src/                        # Frontend (Vue 2.7 + Vuetify 2.7)
  index.js                  # Plugin registration
  VigilDashboard.vue        # Main dashboard view
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
