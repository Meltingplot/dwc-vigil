"""
Vigil Tracker — Data model and tracking logic for three counter tiers.

Tracks: machine hours, print hours, jobs, axis travel, filament usage, heater time.
Three tiers: lifetime (never reset), service (individually resettable), session (in-memory).

The update() method accepts a dsf-python ObjectModel directly.  Attributes are
accessed via getattr() with snake_case names (dsf-python auto-converts from
camelCase).  Enum values (MachineStatus, HeaterState, AxisLetter) inherit from
str, so plain string comparisons work.
"""

import copy
import logging
import time
from datetime import date

from vigil_persistence import (
    empty_state,
    _empty_counters,
    _empty_vitals,
    atomic_save,
    append_daily_snapshot,
    get_data_path,
)
from vigil_time import MonotonicTimer, DayTracker, utc_now_iso, today_iso

logger = logging.getLogger("vigil.tracker")


class VigilTracker:
    """Tracks machine statistics across three counter tiers."""

    def __init__(self, data: dict | None = None):
        self._data = data if data is not None else empty_state()
        self._session = _empty_counters()
        self._dirty = False
        self._timer = MonotonicTimer()
        self._day_tracker = DayTracker()

        # Previous values for delta calculations
        self._prev_axis_pos = {}      # axis_name → position
        self._prev_axis_homed = {}    # axis_name → bool
        self._axis_homed_at = {}      # axis_name → monotonic timestamp of False→True
        self._prev_extruder_pos = {}  # extruder_index → position
        self._prev_status = None
        self._prev_job_file = None
        self._prev_firmware_uptime = None
        self._prev_sbc_uptime = None

        # Ensure new state fields exist (schema migration for existing data)
        if "vitals" not in self._data:
            self._data["vitals"] = _empty_vitals()
        if "uptime" not in self._data:
            self._data["uptime"] = {
                "firmware_uptime_secs": None,
                "sbc_uptime_secs": None,
                "firmware_reboots": 0,
                "sbc_reboots": 0,
            }
        if "volume_free_bytes" not in self._data:
            self._data["volume_free_bytes"] = None
        # Ensure new counter fields exist in lifetime/service tiers
        for tier in [self._data["lifetime"], self._data["service"]]:
            tier.setdefault("pause_seconds", 0.0)
            tier.setdefault("warmup_seconds", 0.0)
            tier.setdefault("fans", {})

        # Day baseline for history snapshots (lifetime values at start of day)
        self._day_baseline = copy.deepcopy(self._data["lifetime"])
        self._vitals_baseline = copy.deepcopy(self._data["vitals"])

        # Check for date gap at startup (close previous day)
        self._handle_startup_gap()

    def _handle_startup_gap(self):
        """If last_saved is from a previous day, that day's snapshot is already final."""
        last_saved = self._data.get("last_saved", "")
        gap_date = self._day_tracker.detect_gap(last_saved)
        if gap_date is not None:
            logger.info("Date gap detected since %s — starting fresh baseline", gap_date)
            # The previous day's data was saved at shutdown, so the snapshot
            # should already have been written. Reset baseline for today.
            self._day_baseline = copy.deepcopy(self._data["lifetime"])
            self._vitals_baseline = copy.deepcopy(self._data["vitals"])
            self._data["vitals"] = _empty_vitals()

    @property
    def dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self):
        self._dirty = False

    @property
    def data(self) -> dict:
        return self._data

    @property
    def session(self) -> dict:
        return self._session

    # --- Update from Object Model ---

    def update(self, model):
        """
        Process an ObjectModel update.
        Called on each SubscribeConnection cycle (~250ms).
        model is a dsf-python ObjectModel instance (or any object with the same
        attribute structure, e.g. SimpleNamespace in tests).
        """
        dt = self._timer.tick()
        if dt <= 0:
            return

        state = getattr(model, "state", None)
        status = getattr(state, "status", None) if state is not None else None
        if status is not None:
            status = str(status)
            self._update_time_counters(status, dt)
            self._update_job_tracking(status, model)
            self._prev_status = status

        self._update_axis_travel(model)
        self._update_extruder_travel(model)
        self._update_heaters(model, dt)
        self._update_fans(model, dt)
        self._update_board_vitals(model)
        self._update_sbc_vitals(model)
        self._update_uptime(model)
        self._update_volume(model)

        # Check day change
        self._check_day_change()

    def _update_time_counters(self, status: str, dt: float):
        """Update machine and print time counters."""
        if status != "off":
            self._add("machine_seconds", dt)

        if status == "processing":
            self._add("print_seconds", dt)

        if status in ("pausing", "paused"):
            self._add("pause_seconds", dt)

        if status == "busy" and self._prev_job_file is not None and self._prev_status in (None, "idle", "busy"):
            # Warm-up is the "busy" phase before "processing" starts during a job
            self._add("warmup_seconds", dt)

    def _update_job_tracking(self, status: str, model):
        """Track job start/end transitions."""
        job = getattr(model, "job", None)
        job_file_info = getattr(job, "file", None) if job is not None else None
        job_file = getattr(job_file_info, "file_name", None) if job_file_info is not None else None

        # Job start: file_name transitions from None to value
        if job_file is not None and self._prev_job_file is None:
            self._add("jobs_total", 1)
            self._dirty = True

        # Job end: only count when status reaches a terminal state
        if self._prev_status == "processing" and status != "processing":
            if status == "idle":
                self._add("jobs_successful", 1)
                self._dirty = True
            elif status == "cancelling":
                self._add("jobs_cancelled", 1)
                self._dirty = True
            # pausing/busy/changingTool are transient — don't count yet

        self._prev_job_file = job_file

    HOMING_GRACE_SECS = 10.0

    def _update_axis_travel(self, model):
        """Track axis travel distances. Only tracks homed axes to avoid
        false deltas from homing moves resetting positions.

        Any homed state change (unhomed→homed OR homed→unhomed) starts a
        10s grace period that suppresses tracking.  This covers multi-tap
        homing sequences and the moves leading into/out of homing where
        the PATCH subscription may miss brief intermediate state changes.
        """
        move = getattr(model, "move", None)
        if move is None:
            return
        axes = getattr(move, "axes", None)
        if axes is None:
            return

        now = time.monotonic()

        for axis in axes:
            letter = getattr(axis, "letter", None)
            pos = getattr(axis, "machine_position", None)
            homed = getattr(axis, "homed", False)
            if letter is None or pos is None:
                continue
            letter = str(letter)

            was_homed = self._prev_axis_homed.get(letter, False)
            self._prev_axis_homed[letter] = homed

            # Any homed state change starts/restarts the grace period
            if homed != was_homed:
                self._axis_homed_at[letter] = now
                self._prev_axis_pos.pop(letter, None)
                if not homed:
                    continue
                # unhomed→homed: skip this tick (grace period will
                # suppress subsequent ticks too)
                continue

            if not homed:
                self._prev_axis_pos.pop(letter, None)
                continue

            # Inside grace period after homing — don't track yet
            homed_at = self._axis_homed_at.get(letter)
            if homed_at is not None and (now - homed_at) < self.HOMING_GRACE_SECS:
                self._prev_axis_pos[letter] = pos
                continue

            if letter in self._prev_axis_pos:
                delta = abs(pos - self._prev_axis_pos[letter])
                if delta > 0 and delta < 100000:
                    self._add_keyed("axes", letter, delta)

            self._prev_axis_pos[letter] = pos

    def _update_extruder_travel(self, model):
        """Track extruder travel and net filament usage."""
        move = getattr(model, "move", None)
        if move is None:
            return
        extruders = getattr(move, "extruders", None)
        if extruders is None:
            return

        for i, ext in enumerate(extruders):
            pos = getattr(ext, "position", None)
            if pos is None:
                continue

            key = f"E{i}"
            if i in self._prev_extruder_pos:
                raw_delta = pos - self._prev_extruder_pos[i]
                abs_delta = abs(raw_delta)

                if abs_delta > 0 and abs_delta < 10000:  # Sanity: < 10m per tick
                    # Total extruder travel (abs, includes retracts)
                    self._add_keyed("axes", key, abs_delta)

                    # Net filament (positive extrusion only)
                    if raw_delta > 0:
                        self._add_keyed("filament_mm", key, raw_delta)

            self._prev_extruder_pos[i] = pos

    def _update_heaters(self, model, dt: float):
        """Track heater on-time and full-load time."""
        heat = getattr(model, "heat", None)
        if heat is None:
            return
        heaters = getattr(heat, "heaters", None)
        if heaters is None:
            return

        for i, heater in enumerate(heaters):
            state = getattr(heater, "state", None)
            key = str(i)

            if state is not None and str(state) != "off":
                self._add_heater(key, "on_seconds", dt)

                # Full load: check average PWM duty cycle
                avg_pwm = getattr(heater, "avg_pwm", None)
                if avg_pwm is not None and avg_pwm >= 0.95:
                    self._add_heater(key, "full_load_seconds", dt)

    def _update_fans(self, model, dt: float):
        """Track fan runtime."""
        fans = getattr(model, "fans", None)
        if fans is None:
            return

        for i, fan in enumerate(fans):
            if fan is None:
                continue
            actual = getattr(fan, "actual_value", None)
            key = str(i)

            if actual is not None and actual > 0:
                self._add_fan(key, "on_seconds", dt)

    def _update_board_vitals(self, model):
        """Track board MCU temp, vIn, v12 min/max."""
        boards = getattr(model, "boards", None)
        if not boards:
            return

        # Use first board (main board)
        board = boards[0] if boards else None
        if board is None:
            return

        vitals = self._data["vitals"]

        mcu_temp = getattr(board, "mcu_temp", None)
        if mcu_temp is not None:
            current = getattr(mcu_temp, "current", None)
            if current is not None:
                self._update_min_max(vitals, "mcu_temp", current)

        v_in = getattr(board, "v_in", None)
        if v_in is not None:
            current = getattr(v_in, "current", None)
            if current is not None:
                self._update_min_max(vitals, "vin", current)

        v12 = getattr(board, "v12", None)
        if v12 is not None:
            current = getattr(v12, "current", None)
            if current is not None:
                self._update_min_max(vitals, "v12", current)

        self._dirty = True

    def _update_sbc_vitals(self, model):
        """Track SBC CPU temp, load, and memory."""
        sbc = getattr(model, "sbc", None)
        if sbc is None:
            return

        vitals = self._data["vitals"]

        cpu = getattr(sbc, "cpu", None)
        if cpu is not None:
            temp = getattr(cpu, "temperature", None)
            if temp is not None:
                if vitals["sbc_cpu_temp_max"] is None or temp > vitals["sbc_cpu_temp_max"]:
                    vitals["sbc_cpu_temp_max"] = temp

            avg_load = getattr(cpu, "avg_load", None)
            if avg_load is not None:
                vitals["sbc_cpu_load_avg_sum"] += avg_load
                vitals["sbc_cpu_load_avg_count"] += 1

        memory = getattr(sbc, "memory", None)
        if memory is not None:
            available = getattr(memory, "available", None)
            if available is not None:
                if vitals["sbc_memory_min_bytes"] is None or available < vitals["sbc_memory_min_bytes"]:
                    vitals["sbc_memory_min_bytes"] = available

        self._dirty = True

    def _update_uptime(self, model):
        """Track firmware and SBC uptime, detect reboots."""
        state = getattr(model, "state", None)
        if state is not None:
            up_time = getattr(state, "up_time", None)
            if up_time is not None:
                if (self._prev_firmware_uptime is not None
                        and up_time < self._prev_firmware_uptime):
                    self._data["uptime"]["firmware_reboots"] += 1
                    self._dirty = True
                self._prev_firmware_uptime = up_time
                self._data["uptime"]["firmware_uptime_secs"] = up_time

        sbc = getattr(model, "sbc", None)
        if sbc is not None:
            sbc_uptime = getattr(sbc, "uptime", None)
            if sbc_uptime is not None:
                if (self._prev_sbc_uptime is not None
                        and sbc_uptime < self._prev_sbc_uptime):
                    self._data["uptime"]["sbc_reboots"] += 1
                    self._dirty = True
                self._prev_sbc_uptime = sbc_uptime
                self._data["uptime"]["sbc_uptime_secs"] = sbc_uptime

    def _update_volume(self, model):
        """Track volume free space (first mounted volume)."""
        volumes = getattr(model, "volumes", None)
        if not volumes:
            return

        for vol in volumes:
            if vol is None:
                continue
            mounted = getattr(vol, "mounted", None)
            if mounted:
                free = getattr(vol, "free_space", None)
                if free is not None:
                    self._data["volume_free_bytes"] = free
                    self._dirty = True
                break

    @staticmethod
    def _update_min_max(vitals: dict, prefix: str, value: float):
        """Update min/max tracking for a vitals prefix."""
        min_key = f"{prefix}_min"
        max_key = f"{prefix}_max"
        if vitals[min_key] is None or value < vitals[min_key]:
            vitals[min_key] = value
        if vitals[max_key] is None or value > vitals[max_key]:
            vitals[max_key] = value

    def _add_fan(self, key: str, field: str, value: float):
        """Add to a fan counter across all three tiers."""
        for tier in [self._data["lifetime"], self._data["service"], self._session]:
            if key not in tier["fans"]:
                tier["fans"][key] = {"on_seconds": 0.0}
            tier["fans"][key][field] += value
        self._dirty = True

    # --- Counter helpers ---

    def _add(self, counter: str, value):
        """Add to a scalar counter across all three tiers."""
        self._data["lifetime"][counter] += value
        self._data["service"][counter] += value
        self._session[counter] += value
        self._dirty = True

    def _add_keyed(self, category: str, key: str, value: float):
        """Add to a keyed counter (axes, filament_mm) across all three tiers."""
        for tier in [self._data["lifetime"], self._data["service"], self._session]:
            if key not in tier[category]:
                tier[category][key] = 0.0
            tier[category][key] += value
        self._dirty = True

    def _add_heater(self, key: str, field: str, value: float):
        """Add to a heater counter across all three tiers."""
        for tier in [self._data["lifetime"], self._data["service"], self._session]:
            if key not in tier["heaters"]:
                tier["heaters"][key] = {"on_seconds": 0.0, "full_load_seconds": 0.0}
            tier["heaters"][key][field] += value
        self._dirty = True

    # --- Service Reset ---

    def service_reset(self, scope: str, keys: list | None = None,
                      description: str = "", component: str | None = None) -> dict:
        """
        Reset service counters for a given scope.
        Returns values before reset for the service log.
        """
        service = self._data["service"]
        values_before = {}

        if scope == "machine_time":
            values_before["machine_seconds"] = service["machine_seconds"]
            service["machine_seconds"] = 0.0

        elif scope == "print_time":
            values_before["print_seconds"] = service["print_seconds"]
            service["print_seconds"] = 0.0

        elif scope == "jobs":
            for k in ["jobs_total", "jobs_successful", "jobs_cancelled"]:
                values_before[k] = service[k]
                service[k] = 0

        elif scope == "axes":
            target_keys = keys if keys else list(service["axes"].keys())
            for k in target_keys:
                if k in service["axes"]:
                    values_before[k] = service["axes"][k]
                    service["axes"][k] = 0.0

        elif scope == "extruders":
            target_keys = keys if keys else [k for k in service["axes"] if k.startswith("E")]
            for k in target_keys:
                if k in service["axes"]:
                    values_before[k] = service["axes"][k]
                    service["axes"][k] = 0.0

        elif scope == "filament":
            target_keys = keys if keys else list(service["filament_mm"].keys())
            for k in target_keys:
                if k in service["filament_mm"]:
                    values_before[k] = service["filament_mm"][k]
                    service["filament_mm"][k] = 0.0

        elif scope == "heaters":
            target_keys = keys if keys else list(service["heaters"].keys())
            for k in target_keys:
                if k in service["heaters"]:
                    values_before[k] = copy.deepcopy(service["heaters"][k])
                    service["heaters"][k] = {"on_seconds": 0.0, "full_load_seconds": 0.0}

        elif scope == "fans":
            target_keys = keys if keys else list(service["fans"].keys())
            for k in target_keys:
                if k in service["fans"]:
                    values_before[k] = copy.deepcopy(service["fans"][k])
                    service["fans"][k] = {"on_seconds": 0.0}

        elif scope == "pause_time":
            values_before["pause_seconds"] = service["pause_seconds"]
            service["pause_seconds"] = 0.0

        elif scope == "warmup_time":
            values_before["warmup_seconds"] = service["warmup_seconds"]
            service["warmup_seconds"] = 0.0

        else:
            raise ValueError(f"Unknown reset scope: {scope}")

        # Log the reset
        log_entry = {
            "timestamp": utc_now_iso(),
            "type": "counter_reset",
            "component": component,
            "description": description,
            "reset_scope": scope,
            "reset_keys": keys,
            "values_before_reset": values_before,
        }
        self._data["service_log"].append(log_entry)
        self._dirty = True

        return values_before

    def add_service_event(self, component: str, description: str):
        """Log a service event (no counter reset)."""
        log_entry = {
            "timestamp": utc_now_iso(),
            "type": "service_event",
            "component": component,
            "description": description,
            "reset_scope": None,
            "reset_keys": None,
            "values_before_reset": None,
        }
        self._data["service_log"].append(log_entry)
        self._dirty = True

    # --- History Snapshots ---

    def _check_day_change(self):
        """Check for day change and create snapshot if needed."""
        previous_date = self._day_tracker.check_day_change()
        if previous_date is not None:
            self._create_daily_snapshot(previous_date)
            self._day_baseline = copy.deepcopy(self._data["lifetime"])
            # Reset daily vitals for the new day
            self._vitals_baseline = copy.deepcopy(self._data["vitals"])
            self._data["vitals"] = _empty_vitals()

    def create_shutdown_snapshot(self):
        """Create a snapshot for the current day at shutdown."""
        self._create_daily_snapshot(self._day_tracker.current_date)

    def _create_daily_snapshot(self, snapshot_date: date):
        """Create a daily snapshot from the delta between now and day baseline."""
        lt = self._data["lifetime"]
        bl = self._day_baseline

        snapshot = {
            "date": snapshot_date.isoformat(),
            "machine_hours": round((lt["machine_seconds"] - bl["machine_seconds"]) / 3600, 2),
            "print_hours": round((lt["print_seconds"] - bl["print_seconds"]) / 3600, 2),
            "pause_hours": round((lt["pause_seconds"] - bl["pause_seconds"]) / 3600, 2),
            "warmup_hours": round((lt["warmup_seconds"] - bl["warmup_seconds"]) / 3600, 2),
            "jobs_total": lt["jobs_total"] - bl["jobs_total"],
            "jobs_successful": lt["jobs_successful"] - bl["jobs_successful"],
            "jobs_cancelled": lt["jobs_cancelled"] - bl["jobs_cancelled"],
        }

        # Axis travel delta
        axis_travel = {}
        for axis, val in lt["axes"].items():
            baseline_val = bl["axes"].get(axis, 0.0)
            delta = val - baseline_val
            if delta > 0:
                axis_travel[axis] = round(delta, 1)
        if axis_travel:
            snapshot["axis_travel_mm"] = axis_travel

        # Filament delta
        filament = {}
        for ext, val in lt["filament_mm"].items():
            baseline_val = bl["filament_mm"].get(ext, 0.0)
            delta = val - baseline_val
            if delta > 0:
                filament[ext] = round(delta, 1)
        if filament:
            snapshot["filament_mm"] = filament

        # Heater on-hours delta
        heater_hours = {}
        for h, vals in lt["heaters"].items():
            baseline_h = bl["heaters"].get(h, {})
            delta = vals.get("on_seconds", 0) - baseline_h.get("on_seconds", 0)
            if delta > 0:
                heater_hours[h] = round(delta / 3600, 2)
        if heater_hours:
            snapshot["heater_on_hours"] = heater_hours

        # Fan on-hours delta
        fan_hours = {}
        for f, vals in lt["fans"].items():
            baseline_f = bl["fans"].get(f, {})
            delta = vals.get("on_seconds", 0) - baseline_f.get("on_seconds", 0)
            if delta > 0:
                fan_hours[f] = round(delta / 3600, 2)
        if fan_hours:
            snapshot["fan_on_hours"] = fan_hours

        # Board/SBC vitals (from the day's vitals, not from deltas)
        vitals = self._data["vitals"]
        if vitals["mcu_temp_max"] is not None:
            snapshot["mcu_temp_max"] = round(vitals["mcu_temp_max"], 1)
        if vitals["mcu_temp_min"] is not None:
            snapshot["mcu_temp_min"] = round(vitals["mcu_temp_min"], 1)
        if vitals["vin_min"] is not None:
            snapshot["vin_min"] = round(vitals["vin_min"], 2)
        if vitals["vin_max"] is not None:
            snapshot["vin_max"] = round(vitals["vin_max"], 2)
        if vitals["v12_min"] is not None:
            snapshot["v12_min"] = round(vitals["v12_min"], 2)
        if vitals["v12_max"] is not None:
            snapshot["v12_max"] = round(vitals["v12_max"], 2)
        if vitals["sbc_cpu_temp_max"] is not None:
            snapshot["sbc_cpu_temp_max"] = round(vitals["sbc_cpu_temp_max"], 1)
        if vitals["sbc_cpu_load_avg_count"] > 0:
            avg = vitals["sbc_cpu_load_avg_sum"] / vitals["sbc_cpu_load_avg_count"]
            snapshot["sbc_cpu_load_avg"] = round(avg, 3)
        if vitals["sbc_memory_min_bytes"] is not None:
            snapshot["sbc_memory_min_mb"] = round(vitals["sbc_memory_min_bytes"] / (1024 * 1024), 1)

        # Uptime / reboots
        uptime = self._data["uptime"]
        if uptime["firmware_reboots"] > 0:
            snapshot["firmware_reboots"] = uptime["firmware_reboots"]
        if uptime["sbc_reboots"] > 0:
            snapshot["sbc_reboots"] = uptime["sbc_reboots"]

        # Volume free space
        if self._data["volume_free_bytes"] is not None:
            snapshot["volume_free_mb"] = round(self._data["volume_free_bytes"] / (1024 * 1024), 1)

        try:
            append_daily_snapshot(snapshot)
            logger.info("Daily snapshot created for %s", snapshot_date)
        except Exception as e:
            logger.error("Failed to save daily snapshot: %s", e)

    # --- Status for API / Plugin Data ---

    def get_status(self) -> dict:
        """Return all three counter tiers for the API."""
        return {
            "lifetime": self._data["lifetime"],
            "service": self._data["service"],
            "session": self._session,
            "vitals": self._data["vitals"],
            "uptime": self._data["uptime"],
            "volume_free_bytes": self._data["volume_free_bytes"],
        }

    def get_plugin_data_summary(self) -> dict:
        """Return a compact summary for the DSF Object Model plugin data."""
        lt = self._data["lifetime"]
        return {
            "status": "tracking",
            "machineHours": round(lt["machine_seconds"] / 3600, 2),
            "printHours": round(lt["print_seconds"] / 3600, 2),
            "jobsTotal": lt["jobs_total"],
            "lastSaved": self._data.get("last_saved", ""),
        }

    def get_service_log(self) -> list:
        """Return the service log (newest first)."""
        return list(reversed(self._data["service_log"]))

    def save(self):
        """Persist data to disk."""
        atomic_save(self._data)
        self.clear_dirty()

    # --- Export ---

    def export_json(self) -> dict:
        """Return full data for JSON export."""
        return {
            "schema_version": self._data.get("schema_version", 1),
            "exported_at": utc_now_iso(),
            "lifetime": self._data["lifetime"],
            "service": self._data["service"],
            "session": self._session,
            "service_log": self._data["service_log"],
            "vitals": self._data["vitals"],
            "uptime": self._data["uptime"],
            "volume_free_bytes": self._data["volume_free_bytes"],
        }

    def export_csv(self) -> str:
        """Return data as CSV string for export."""
        lines = ["tier,counter,key,value"]

        for tier_name, tier_data in [("lifetime", self._data["lifetime"]),
                                      ("service", self._data["service"]),
                                      ("session", self._session)]:
            # Scalar counters
            for key in ["machine_seconds", "print_seconds", "pause_seconds",
                        "warmup_seconds", "jobs_total",
                        "jobs_successful", "jobs_cancelled"]:
                lines.append(f"{tier_name},{key},,{tier_data.get(key, 0)}")

            # Axes
            for axis, val in tier_data.get("axes", {}).items():
                lines.append(f"{tier_name},axis_travel_mm,{axis},{val}")

            # Filament
            for ext, val in tier_data.get("filament_mm", {}).items():
                lines.append(f"{tier_name},filament_mm,{ext},{val}")

            # Heaters
            for h, vals in tier_data.get("heaters", {}).items():
                lines.append(f"{tier_name},heater_on_seconds,{h},{vals.get('on_seconds', 0)}")
                lines.append(f"{tier_name},heater_full_load_seconds,{h},{vals.get('full_load_seconds', 0)}")

            # Fans
            for f, vals in tier_data.get("fans", {}).items():
                lines.append(f"{tier_name},fan_on_seconds,{f},{vals.get('on_seconds', 0)}")

        # Vitals (not tiered)
        vitals = self._data.get("vitals", {})
        for key in ["mcu_temp_min", "mcu_temp_max", "vin_min", "vin_max",
                     "v12_min", "v12_max", "sbc_cpu_temp_max", "sbc_memory_min_bytes"]:
            val = vitals.get(key)
            if val is not None:
                lines.append(f"vitals,{key},,{val}")

        # Uptime
        uptime = self._data.get("uptime", {})
        for key in ["firmware_uptime_secs", "sbc_uptime_secs",
                     "firmware_reboots", "sbc_reboots"]:
            val = uptime.get(key)
            if val is not None:
                lines.append(f"uptime,{key},,{val}")

        # Volume
        vol_free = self._data.get("volume_free_bytes")
        if vol_free is not None:
            lines.append(f"volume,free_bytes,,{vol_free}")

        return "\n".join(lines) + "\n"
