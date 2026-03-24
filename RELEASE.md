# Vigil v1.0.0 — Machine Usage Monitoring for Duet 3D Printers

We're excited to release Vigil v1.0.0, a DuetWebControl plugin that brings comprehensive machine usage monitoring and maintenance tracking to your Duet 3D printer.

## What is Vigil?

Vigil runs as a background daemon on your SBC and continuously tracks how your printer is being used — from total operating hours and print statistics to per-component wear metrics. It's designed for service centers, print farms, and anyone who wants data-driven insight into their machine's health and usage patterns.

## Key Features

### Three-Tier Counter System
- **Lifetime** — cumulative totals that never reset, capturing the full history of your machine
- **Service** — individually resettable counters for maintenance cycles (e.g., between nozzle changes or bearing replacements)
- **Session** — in-memory counters for the current runtime

### Time Tracking
- Machine operating hours, print time, pause duration, and heater warmup time
- Automatic detection based on real-time DSF ObjectModel status transitions

### Job Statistics
- Total jobs, successful completions, and cancellations
- Visual pie chart for job outcome breakdown

### Movement & Filament
- Per-axis travel distance (X, Y, Z) with intelligent homing grace period to avoid false readings
- Per-extruder filament usage (net positive extrusion, excluding retracts)
- Automatic unit formatting (mm → m → km)

### Thermal & Fan Tracking
- Per-heater on-time and full-load seconds (95%+ duty cycle)
- Per-fan runtime tracking
- Interactive bar charts for component usage comparison

### System Vitals
- **Board**: MCU temperature, input voltage (Vin), 12V rail — with daily min/max tracking
- **SBC**: CPU temperature, CPU load average, available memory
- **Uptime**: Firmware and SBC uptime with automatic reboot detection
- **Storage**: Free volume space monitoring

### 30-Day History & Trending
- Automatic daily snapshots of all counters
- Interactive history chart with metric selector — drill down into specific heaters, fans, axes, or filament usage

### Service Event Logging
- Log maintenance events with timestamps and descriptions
- Scope-based or key-based counter resets with full audit trail
- Complete service log viewable in the UI

### Data Export
- Export all data in JSON or CSV format for external analysis

## Technical Highlights

- **Real-time tracking** via DSF ObjectModel subscription with incremental PATCH updates
- **Crash-safe persistence** using atomic writes with SHA-256 checksums and XOR parity recovery
- **Automatic schema migration** for seamless future upgrades
- **Data stored in `/opt/dsf/sd/Vigil/`** — survives plugin upgrades and reinstalls
- **Responsive dashboard** built with Vue 2.7 + Vuetify 2.7, with 5-second polling

## Requirements

- Duet 3D printer with SBC (Raspberry Pi or similar)
- DSF v3.6+
- DuetWebControl v3.6+
- Python 3.10+

## Installation

Upload the plugin ZIP through DuetWebControl's **Settings → Plugins → Install Plugin** dialog. Vigil will start automatically and begin tracking immediately.

## License

LGPL-3.0-or-later
