"""Tests for vigil_tracker — data model, tracking logic, service reset.

Test models use SimpleNamespace to mirror the dsf-python ObjectModel attribute
structure (snake_case attributes accessed via getattr).
"""

import copy
import time
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from vigil_persistence import empty_state
from vigil_tracker import VigilTracker


def _model(state=None, move=None, heat=None, job=None, boards=None,
           fans=None, sbc=None, volumes=None, up_time=None):
    """Build a minimal ObjectModel-like namespace."""
    m = NS()
    if state is not None or up_time is not None:
        m.state = NS(status=state, up_time=up_time)
    if move is not None:
        m.move = move
    if heat is not None:
        m.heat = heat
    if job is not None:
        m.job = job
    if boards is not None:
        m.boards = boards
    if fans is not None:
        m.fans = fans
    if sbc is not None:
        m.sbc = sbc
    if volumes is not None:
        m.volumes = volumes
    return m


def _axes(*args):
    """Build a move namespace with axes.  Each arg is (letter, machine_position)
    or (letter, machine_position, homed).  Defaults to homed=True."""
    axis_list = []
    for a in args:
        homed = a[2] if len(a) >= 3 else True
        axis_list.append(NS(letter=a[0], machine_position=a[1], homed=homed))
    return NS(axes=axis_list, extruders=[])


def _extruders(*positions):
    """Build a move namespace with extruders.  Each arg is a position float."""
    return NS(axes=[], extruders=[NS(position=p) for p in positions])


def _heaters(*args):
    """Build a heat namespace.  Each arg is (state_str, avg_pwm_float)."""
    return NS(heaters=[NS(state=s, avg_pwm=c) for s, c in args])


def _job(file_name, warm_up_duration=None, pause_duration=None):
    """Build a job namespace."""
    if file_name is None:
        return NS(file=NS(file_name=None), warm_up_duration=warm_up_duration,
                  pause_duration=pause_duration)
    return NS(file=NS(file_name=file_name), warm_up_duration=warm_up_duration,
              pause_duration=pause_duration)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VIGIL_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def tracker(data_dir):
    return VigilTracker(empty_state())


class TestCounters:
    def test_initial_state(self, tracker):
        status = tracker.get_status()
        assert status["lifetime"]["machine_seconds"] == 0.0
        assert status["service"]["machine_seconds"] == 0.0
        assert status["session"]["machine_seconds"] == 0.0

    def test_machine_time_increments(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="idle"))

        status = tracker.get_status()
        assert status["lifetime"]["machine_seconds"] > 0
        assert status["session"]["machine_seconds"] > 0

    def test_print_time_only_during_processing(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="idle"))

        status = tracker.get_status()
        assert status["lifetime"]["print_seconds"] == 0.0

        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="processing"))

        status = tracker.get_status()
        assert status["lifetime"]["print_seconds"] > 0

    def test_no_time_when_off(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="off"))

        status = tracker.get_status()
        assert status["lifetime"]["machine_seconds"] == 0.0


class TestAxisTracking:
    def test_axis_travel(self, tracker):
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            tracker.update(_model(move=_axes(("X", 0))))

            # Advance past homing grace period
            mock_time.monotonic.return_value = t + 11
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 0))))

            mock_time.monotonic.return_value = t + 11.25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 100))))

        status = tracker.get_status()
        assert status["lifetime"]["axes"]["X"] == 100.0

    def test_dynamic_axis_detection(self, tracker):
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            tracker.update(_model(move=_axes(("X", 0), ("Y", 0), ("Z", 0))))

            # Advance past homing grace period
            mock_time.monotonic.return_value = t + 11
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 0), ("Y", 0), ("Z", 0))))

            mock_time.monotonic.return_value = t + 11.25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 50), ("Y", 30), ("Z", 10))))

        status = tracker.get_status()
        assert "X" in status["lifetime"]["axes"]
        assert "Y" in status["lifetime"]["axes"]
        assert "Z" in status["lifetime"]["axes"]


class TestAxisHomedFiltering:
    def test_unhomed_axis_not_tracked(self, tracker):
        tracker._timer.reset()
        tracker.update(_model(move=_axes(("X", 0, False))))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(move=_axes(("X", 100, False))))

        status = tracker.get_status()
        assert "X" not in status["lifetime"]["axes"]

    def test_homed_axis_tracked_after_grace(self, tracker):
        """Homed axis is tracked once the 10s grace period expires."""
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            # First seen as homed — starts grace period
            tracker.update(_model(move=_axes(("X", 0, True))))

            # Advance past the 10s grace period
            mock_time.monotonic.return_value = t + 11
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 0, True))))

            mock_time.monotonic.return_value = t + 11.25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 100, True))))

        status = tracker.get_status()
        assert status["lifetime"]["axes"]["X"] == 100.0

    def test_axis_becoming_homed_no_false_delta(self, tracker):
        """When axis transitions from unhomed to homed, the position
        jump from homing should not be counted as travel."""
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            tracker.update(_model(move=_axes(("X", 500, False))))
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 0, True))))

            # Even after grace period — the homing jump itself is not counted
            mock_time.monotonic.return_value = t + 11
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 0, True))))

        status = tracker.get_status()
        assert "X" not in status["lifetime"]["axes"]

    def test_mixed_homed_unhomed(self, tracker):
        """Only homed axes get tracked in a multi-axis setup."""
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            tracker.update(_model(move=_axes(("X", 0, True), ("Y", 0, False), ("Z", 0, True))))

            # Advance past grace period
            mock_time.monotonic.return_value = t + 11
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 0, True), ("Y", 0, False), ("Z", 0, True))))

            mock_time.monotonic.return_value = t + 11.25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 50, True), ("Y", 100, False), ("Z", 10, True))))

        status = tracker.get_status()
        assert status["lifetime"]["axes"]["X"] == 50.0
        assert "Y" not in status["lifetime"]["axes"]
        assert status["lifetime"]["axes"]["Z"] == 10.0

    def test_grace_period_suppresses_homing_travel(self, tracker):
        """During the 10s grace period after homing, travel is not counted.
        This covers multi-tap homing (home, rewind, re-home slower)."""
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            # Axis unhomed
            tracker.update(_model(move=_axes(("X", 0, False))))

            # First tap: homed at 880
            mock_time.monotonic.return_value = t + 1
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 880, True))))

            # Rewind during homing (still within grace)
            mock_time.monotonic.return_value = t + 3
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 870, True))))

            # Second tap re-homes at 878
            mock_time.monotonic.return_value = t + 5
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 878, True))))

        status = tracker.get_status()
        assert "X" not in status["lifetime"]["axes"]

    def test_rehoming_already_homed_axis_not_tracked(self, tracker):
        """When re-homing an already-homed axis, the unhomed→homed
        transition triggers a new grace period that suppresses travel."""
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            tracker.update(_model(move=_axes(("X", 100, True))))

            # Past grace period, normal move tracked
            mock_time.monotonic.return_value = t + 11
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 100, True))))
            mock_time.monotonic.return_value = t + 11.25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 120, True))))

            # Re-homing: axis goes unhomed then homed at 880
            mock_time.monotonic.return_value = t + 20
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 120, False))))
            mock_time.monotonic.return_value = t + 22
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 880, True))))

            # Still in grace period — not tracked
            mock_time.monotonic.return_value = t + 25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 870, True))))

        status = tracker.get_status()
        # Only the 20mm from the normal move should be tracked
        assert status["lifetime"]["axes"]["X"] == 20.0

    def test_homed_to_unhomed_starts_grace_period(self, tracker):
        """When a homed axis becomes unhomed (e.g. G28 starts), the
        homed→unhomed transition starts a grace period so that when the
        axis becomes homed again the grace is already running."""
        t = time.monotonic()
        with patch("vigil_tracker.time") as mock_time:
            mock_time.monotonic.return_value = t
            tracker._timer.reset()
            tracker.update(_model(move=_axes(("X", 100, True))))

            # Past initial grace, normal move
            mock_time.monotonic.return_value = t + 11
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 100, True))))
            mock_time.monotonic.return_value = t + 11.25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 120, True))))

            # Axis becomes unhomed — grace starts at t+20
            mock_time.monotonic.return_value = t + 20
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 120, False))))

            # Axis becomes homed again at t+22 — grace restarts
            mock_time.monotonic.return_value = t + 22
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 880, True))))

            # t+29 is within 10s of the t+22 unhomed→homed transition
            mock_time.monotonic.return_value = t + 29
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 870, True))))

            # t+33 is past the grace period (>10s from t+22)
            mock_time.monotonic.return_value = t + 33
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 870, True))))
            mock_time.monotonic.return_value = t + 33.25
            tracker._timer._last_tick -= 0.25
            tracker.update(_model(move=_axes(("X", 850, True))))

        status = tracker.get_status()
        # 20mm pre-homing + 20mm post-grace = 40mm
        assert status["lifetime"]["axes"]["X"] == 40.0


class TestExtruderTracking:
    def test_filament_net_positive_only(self, tracker):
        tracker._timer.reset()
        tracker.update(_model(move=_extruders(0)))

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(move=_extruders(100)))

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(move=_extruders(90)))

        status = tracker.get_status()
        assert status["lifetime"]["axes"]["E0"] == 110.0
        assert status["lifetime"]["filament_mm"]["E0"] == 100.0


class TestWarmup:
    def test_warmup_from_object_model(self, tracker):
        """warm_up_duration from ObjectModel is tracked as a delta."""
        tracker._timer.reset()

        # Job starts, no warmup yet
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", warm_up_duration=None)))
        assert tracker.get_status()["lifetime"]["warmup_seconds"] == 0.0

        # Warmup duration appears (heaters finished heating after 45s)
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", warm_up_duration=45)))
        assert tracker.get_status()["lifetime"]["warmup_seconds"] == 45.0

    def test_warmup_stays_constant(self, tracker):
        """Once warm_up_duration is set, it stays constant — no double counting."""
        tracker._timer.reset()

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", warm_up_duration=30)))
        assert tracker.get_status()["lifetime"]["warmup_seconds"] == 30.0

        # Same value on next tick — no additional warmup
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", warm_up_duration=30)))
        assert tracker.get_status()["lifetime"]["warmup_seconds"] == 30.0

    def test_warmup_accumulates_across_jobs(self, tracker):
        """Warmup from multiple jobs accumulates in lifetime counter."""
        tracker._timer.reset()

        # First job: 20s warmup
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("job1.gcode", warm_up_duration=20)))

        # Job ends
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", job=_job(None)))

        # Second job: 35s warmup
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("job2.gcode", warm_up_duration=35)))

        assert tracker.get_status()["lifetime"]["warmup_seconds"] == 55.0

    def test_warmup_zero_when_no_warmup_reported(self, tracker):
        """If warm_up_duration stays None, no warmup is counted."""
        tracker._timer.reset()

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", warm_up_duration=None)))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", warm_up_duration=None)))

        assert tracker.get_status()["lifetime"]["warmup_seconds"] == 0.0


class TestJobTracking:
    def test_job_start(self, tracker):
        tracker._timer.reset()
        tracker._prev_job_file = None
        tracker.update(_model(state="processing", job=_job("test.gcode")))

        status = tracker.get_status()
        assert status["lifetime"]["jobs_total"] == 1

    def test_job_success(self, tracker):
        tracker._prev_status = "processing"
        tracker._prev_job_file = "test.gcode"
        tracker._timer.reset()
        tracker.update(_model(state="idle", job=_job(None)))

        status = tracker.get_status()
        assert status["lifetime"]["jobs_successful"] == 1

    def test_job_cancel(self, tracker):
        tracker._prev_status = "processing"
        tracker._prev_job_file = "test.gcode"
        tracker._timer.reset()
        tracker.update(_model(state="cancelling", job=_job(None)))

        status = tracker.get_status()
        assert status["lifetime"]["jobs_cancelled"] == 1

    def test_job_cancel_from_paused(self, tracker):
        tracker._prev_status = "paused"
        tracker._prev_job_file = "test.gcode"
        tracker._timer.reset()
        tracker.update(_model(state="cancelling", job=_job(None)))

        status = tracker.get_status()
        assert status["lifetime"]["jobs_cancelled"] == 1

    def test_job_cancel_from_pausing(self, tracker):
        tracker._prev_status = "pausing"
        tracker._prev_job_file = "test.gcode"
        tracker._timer.reset()
        tracker.update(_model(state="cancelling", job=_job(None)))

        status = tracker.get_status()
        assert status["lifetime"]["jobs_cancelled"] == 1

    def test_job_cancel_from_paused_no_double_count(self, tracker):
        """Ensure cancelling -> idle does not also count as successful."""
        tracker._prev_status = "paused"
        tracker._prev_job_file = "test.gcode"
        tracker._timer.reset()
        tracker.update(_model(state="cancelling", job=_job("test.gcode")))

        # Now transition cancelling -> idle
        tracker._timer.reset()
        tracker.update(_model(state="idle", job=_job(None)))

        status = tracker.get_status()
        assert status["lifetime"]["jobs_cancelled"] == 1
        assert status["lifetime"]["jobs_successful"] == 0


class TestServiceReset:
    def test_reset_machine_time(self, tracker, data_dir):
        tracker._data["service"]["machine_seconds"] = 5000.0
        values = tracker.service_reset("machine_time", description="Test reset")

        assert values["machine_seconds"] == 5000.0
        assert tracker._data["service"]["machine_seconds"] == 0.0
        assert tracker._data["lifetime"]["machine_seconds"] == 0.0  # Lifetime untouched

    def test_reset_axes_selective(self, tracker, data_dir):
        tracker._data["service"]["axes"] = {"X": 1000, "Y": 2000, "Z": 500}
        values = tracker.service_reset("axes", keys=["X", "Y"], description="Guides replaced")

        assert values == {"X": 1000, "Y": 2000}
        assert tracker._data["service"]["axes"]["X"] == 0.0
        assert tracker._data["service"]["axes"]["Y"] == 0.0
        assert tracker._data["service"]["axes"]["Z"] == 500  # Untouched

    def test_reset_heaters(self, tracker, data_dir):
        tracker._data["service"]["heaters"] = {
            "0": {"on_seconds": 3600, "full_load_seconds": 1200},
        }
        values = tracker.service_reset("heaters", keys=["0"], description="Heater replaced")

        assert values["0"]["on_seconds"] == 3600
        assert tracker._data["service"]["heaters"]["0"]["on_seconds"] == 0.0

    def test_reset_logs_to_service_log(self, tracker, data_dir):
        tracker._data["service"]["machine_seconds"] = 100
        tracker.service_reset("machine_time", description="Test")

        log = tracker.get_service_log()
        assert len(log) == 1
        assert log[0]["type"] == "counter_reset"
        assert log[0]["reset_scope"] == "machine_time"

    def test_invalid_scope_raises(self, tracker, data_dir):
        with pytest.raises(ValueError, match="Unknown reset scope"):
            tracker.service_reset("nonexistent", description="Test")


class TestServiceEvent:
    def test_add_event(self, tracker, data_dir):
        tracker.add_service_event("fan_hotend", "Hotend fan replaced")

        log = tracker.get_service_log()
        assert len(log) == 1
        assert log[0]["type"] == "service_event"
        assert log[0]["component"] == "fan_hotend"
        assert log[0]["reset_scope"] is None


class TestExport:
    def test_json_export(self, tracker):
        export = tracker.export_json()
        assert "lifetime" in export
        assert "service" in export
        assert "session" in export
        assert "exported_at" in export

    def test_csv_export(self, tracker):
        csv = tracker.export_csv()
        assert csv.startswith("tier,counter,key,value")
        assert "lifetime,machine_seconds" in csv
        assert "session,machine_seconds" in csv


class TestPluginDataSummary:
    def test_summary(self, tracker):
        tracker._data["lifetime"]["machine_seconds"] = 3600
        tracker._data["lifetime"]["print_seconds"] = 1800
        tracker._data["lifetime"]["jobs_total"] = 5

        summary = tracker.get_plugin_data_summary()
        assert summary["status"] == "tracking"
        assert summary["machineHours"] == 1.0
        assert summary["printHours"] == 0.5
        assert summary["jobsTotal"] == 5


class TestHeaterTracking:
    def test_heater_on_time(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="idle", heat=_heaters(("active", 0.5))))

        status = tracker.get_status()
        assert "0" in status["lifetime"]["heaters"]
        assert status["lifetime"]["heaters"]["0"]["on_seconds"] > 0
        assert status["lifetime"]["heaters"]["0"]["full_load_seconds"] == 0.0

    def test_heater_full_load(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="idle", heat=_heaters(("active", 0.98))))

        status = tracker.get_status()
        assert status["lifetime"]["heaters"]["0"]["full_load_seconds"] > 0

    def test_heater_off_not_tracked(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="idle", heat=_heaters(("off", 0.0))))

        status = tracker.get_status()
        assert status["lifetime"]["heaters"] == {}

    def test_multiple_heaters(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(
            state="idle",
            heat=_heaters(("active", 0.5), ("active", 1.0)),
        ))

        status = tracker.get_status()
        assert "0" in status["lifetime"]["heaters"]
        assert "1" in status["lifetime"]["heaters"]
        assert status["lifetime"]["heaters"]["1"]["full_load_seconds"] > 0


class TestUpdateEdgeCases:
    def test_zero_dt_skips_update(self, tracker):
        """When tick returns 0, update should be a no-op."""
        tracker._timer.reset()
        tracker.update(_model(state="idle"))
        status = tracker.get_status()
        assert status["lifetime"]["machine_seconds"] < 0.01

    def test_missing_status_in_model(self, tracker):
        """Model without state.status should not crash."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(move=NS(axes=[], extruders=[])))
        # Should not raise

    def test_axes_none(self, tracker):
        """None axes should be skipped."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", move=NS(axes=None, extruders=[])))
        assert tracker.get_status()["lifetime"]["axes"] == {}

    def test_extruders_none(self, tracker):
        """None extruders should be skipped."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", move=NS(axes=[], extruders=None)))
        assert tracker.get_status()["lifetime"]["filament_mm"] == {}

    def test_axis_missing_position(self, tracker):
        """Axis without machine_position should be skipped."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", move=NS(axes=[NS(letter="X", homed=True)], extruders=[])))
        assert "X" not in tracker.get_status()["lifetime"]["axes"]

    def test_extruder_missing_position(self, tracker):
        """Extruder without position should be skipped."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", move=NS(axes=[], extruders=[NS(other=1)])))
        assert tracker.get_status()["lifetime"]["filament_mm"] == {}

    def test_heaters_none(self, tracker):
        """None heaters should be skipped."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", heat=NS(heaters=None)))
        assert tracker.get_status()["lifetime"]["heaters"] == {}

    def test_heater_missing_state(self, tracker):
        """Heater without state attribute should be skipped."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", heat=NS(heaters=[NS(avg_pwm=0.5)])))
        assert tracker.get_status()["lifetime"]["heaters"] == {}

    def test_axis_travel_sanity_check(self, tracker):
        """Delta >= 100km per tick should be ignored."""
        tracker._timer.reset()
        tracker.update(_model(move=_axes(("X", 0))))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(move=_axes(("X", 200000))))
        assert tracker.get_status()["lifetime"]["axes"] == {}

    def test_extruder_travel_sanity_check(self, tracker):
        """Delta >= 10m per tick should be ignored."""
        tracker._timer.reset()
        tracker.update(_model(move=_extruders(0)))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(move=_extruders(50000)))
        assert tracker.get_status()["lifetime"]["axes"] == {}
        assert tracker.get_status()["lifetime"]["filament_mm"] == {}

    def test_no_move_attribute(self, tracker):
        """Model without move attribute should not crash."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle"))
        assert tracker.get_status()["lifetime"]["axes"] == {}

    def test_no_heat_attribute(self, tracker):
        """Model without heat attribute should not crash."""
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle"))
        assert tracker.get_status()["lifetime"]["heaters"] == {}


class TestServiceResetAdditional:
    def test_reset_print_time(self, tracker, data_dir):
        tracker._data["service"]["print_seconds"] = 7200.0
        values = tracker.service_reset("print_time", description="Counter reset")
        assert values["print_seconds"] == 7200.0
        assert tracker._data["service"]["print_seconds"] == 0.0

    def test_reset_jobs(self, tracker, data_dir):
        tracker._data["service"]["jobs_total"] = 50
        tracker._data["service"]["jobs_successful"] = 40
        tracker._data["service"]["jobs_cancelled"] = 10
        values = tracker.service_reset("jobs", description="Reset job counters")
        assert values["jobs_total"] == 50
        assert values["jobs_successful"] == 40
        assert values["jobs_cancelled"] == 10
        assert tracker._data["service"]["jobs_total"] == 0

    def test_reset_axes_all(self, tracker, data_dir):
        """Reset all axes when no keys specified."""
        tracker._data["service"]["axes"] = {"X": 1000, "Y": 2000}
        values = tracker.service_reset("axes", description="Full axis reset")
        assert "X" in values
        assert "Y" in values
        assert tracker._data["service"]["axes"]["X"] == 0.0
        assert tracker._data["service"]["axes"]["Y"] == 0.0

    def test_reset_extruders(self, tracker, data_dir):
        tracker._data["service"]["axes"] = {"X": 100, "E0": 500, "E1": 300}
        values = tracker.service_reset("extruders", description="Extruder reset")
        assert "E0" in values
        assert "E1" in values
        assert "X" not in values  # non-extruder axis untouched
        assert tracker._data["service"]["axes"]["E0"] == 0.0
        assert tracker._data["service"]["axes"]["X"] == 100

    def test_reset_extruders_selective(self, tracker, data_dir):
        tracker._data["service"]["axes"] = {"E0": 500, "E1": 300}
        values = tracker.service_reset("extruders", keys=["E0"], description="E0 reset")
        assert "E0" in values
        assert "E1" not in values

    def test_reset_filament(self, tracker, data_dir):
        tracker._data["service"]["filament_mm"] = {"E0": 10000, "E1": 5000}
        values = tracker.service_reset("filament", description="Filament reset")
        assert values["E0"] == 10000
        assert tracker._data["service"]["filament_mm"]["E0"] == 0.0

    def test_reset_filament_selective(self, tracker, data_dir):
        tracker._data["service"]["filament_mm"] = {"E0": 10000, "E1": 5000}
        values = tracker.service_reset("filament", keys=["E0"], description="E0 filament reset")
        assert "E0" in values
        assert "E1" not in values
        assert tracker._data["service"]["filament_mm"]["E1"] == 5000


class TestDirtyFlag:
    def test_initial_not_dirty(self, tracker):
        assert not tracker.dirty

    def test_update_sets_dirty(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="idle"))
        assert tracker.dirty

    def test_clear_dirty(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(state="idle"))
        tracker.clear_dirty()
        assert not tracker.dirty


class TestDataAccessors:
    def test_data_property(self, tracker):
        assert "lifetime" in tracker.data
        assert "service" in tracker.data

    def test_session_property(self, tracker):
        assert "machine_seconds" in tracker.session


class TestDailySnapshots:
    def test_shutdown_snapshot(self, tracker, data_dir):
        # Add some data
        tracker._data["lifetime"]["machine_seconds"] = 3600
        tracker._data["lifetime"]["print_seconds"] = 1800
        tracker._data["lifetime"]["jobs_total"] = 5
        tracker._data["lifetime"]["jobs_successful"] = 4
        tracker._data["lifetime"]["jobs_cancelled"] = 1
        tracker._data["lifetime"]["axes"] = {"X": 1000, "Y": 500}
        tracker._data["lifetime"]["filament_mm"] = {"E0": 2000}
        tracker._data["lifetime"]["heaters"] = {"0": {"on_seconds": 7200, "full_load_seconds": 100}}

        tracker.create_shutdown_snapshot()

        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        assert month is not None
        assert len(month["days"]) == 1
        snap = month["days"][0]
        assert snap["date"] == date.today().isoformat()
        assert snap["machine_hours"] == 1.0
        assert snap["print_hours"] == 0.5
        assert snap["jobs_total"] == 5
        assert "axis_travel_mm" in snap
        assert "filament_mm" in snap
        assert "heater_on_hours" in snap

    def test_snapshot_no_axis_travel_when_zero(self, tracker, data_dir):
        """Snapshot should omit axis_travel_mm if no travel."""
        tracker.create_shutdown_snapshot()
        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        snap = month["days"][0]
        assert "axis_travel_mm" not in snap
        assert "filament_mm" not in snap
        assert "heater_on_hours" not in snap

    def test_day_change_creates_snapshot(self, tracker, data_dir):
        """Simulate a day change triggering snapshot creation."""
        from datetime import date, timedelta
        yesterday = date.today() - timedelta(days=1)

        tracker._day_tracker._current_date = yesterday
        tracker._data["lifetime"]["machine_seconds"] = 100
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.5
        tracker.update(_model(state="idle"))

        from vigil_persistence import load_month_history
        ym = yesterday.strftime("%Y-%m")
        month = load_month_history(ym)
        assert month is not None
        snap = [d for d in month["days"] if d["date"] == yesterday.isoformat()]
        assert len(snap) == 1


class TestStartupGap:
    def test_startup_gap_resets_baseline(self, data_dir):
        """When last_saved is from a previous day, baseline should reset."""
        from datetime import datetime, timezone, timedelta

        data = empty_state()
        data["lifetime"]["machine_seconds"] = 5000
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        data["last_saved"] = yesterday

        tracker = VigilTracker(data)
        # Baseline should equal lifetime (reset for new day)
        assert tracker._day_baseline["machine_seconds"] == 5000

    def test_no_gap_on_fresh_start(self, data_dir):
        """Empty last_saved should not trigger gap detection."""
        data = empty_state()
        data["last_saved"] = ""
        tracker = VigilTracker(data)
        # Should not crash or alter baseline


class TestExportWithData:
    def test_csv_export_with_axes_and_heaters(self, tracker):
        tracker._data["lifetime"]["axes"] = {"X": 1000, "Y": 500}
        tracker._data["lifetime"]["filament_mm"] = {"E0": 2000}
        tracker._data["lifetime"]["heaters"] = {"0": {"on_seconds": 3600, "full_load_seconds": 100}}

        csv = tracker.export_csv()
        assert "lifetime,axis_travel_mm,X,1000" in csv
        assert "lifetime,filament_mm,E0,2000" in csv
        assert "lifetime,heater_on_seconds,0,3600" in csv
        assert "lifetime,heater_full_load_seconds,0,100" in csv

    def test_csv_export_with_fans(self, tracker):
        tracker._data["lifetime"]["fans"] = {"0": {"on_seconds": 7200}}
        csv = tracker.export_csv()
        assert "lifetime,fan_on_seconds,0,7200" in csv

    def test_csv_export_with_vitals(self, tracker):
        tracker._data["vitals"]["mcu_temp_max"] = 55.3
        tracker._data["vitals"]["vin_min"] = 23.8
        csv = tracker.export_csv()
        assert "vitals,mcu_temp_max,,55.3" in csv
        assert "vitals,vin_min,,23.8" in csv

    def test_csv_export_with_uptime(self, tracker):
        tracker._data["uptime"]["firmware_reboots"] = 2
        csv = tracker.export_csv()
        assert "uptime,firmware_reboots,,2" in csv

    def test_json_export_has_schema_version(self, tracker):
        export = tracker.export_json()
        assert export["schema_version"] == 1
        assert "service_log" in export
        assert "vitals" in export
        assert "uptime" in export
        assert "volume_free_bytes" in export


class TestFanTracking:
    def test_fan_on_time(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(
            state="idle",
            fans=[NS(actual_value=0.8)],
        ))

        status = tracker.get_status()
        assert "0" in status["lifetime"]["fans"]
        assert status["lifetime"]["fans"]["0"]["on_seconds"] > 0

    def test_fan_off_not_tracked(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(
            state="idle",
            fans=[NS(actual_value=0.0)],
        ))

        status = tracker.get_status()
        assert status["lifetime"]["fans"] == {}

    def test_multiple_fans(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(
            state="idle",
            fans=[NS(actual_value=1.0), NS(actual_value=0.5)],
        ))

        status = tracker.get_status()
        assert "0" in status["lifetime"]["fans"]
        assert "1" in status["lifetime"]["fans"]

    def test_none_fan_skipped(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update(_model(
            state="idle",
            fans=[None, NS(actual_value=1.0)],
        ))

        status = tracker.get_status()
        assert "0" not in status["lifetime"]["fans"]
        assert "1" in status["lifetime"]["fans"]


class TestBoardVitals:
    def test_mcu_temp_tracking(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            boards=[NS(mcu_temp=NS(current=45.2), v_in=None, v12=None)],
        ))

        vitals = tracker._data["vitals"]
        assert vitals["mcu_temp_min"] == 45.2
        assert vitals["mcu_temp_max"] == 45.2

    def test_mcu_temp_min_max(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            boards=[NS(mcu_temp=NS(current=40.0), v_in=None, v12=None)],
        ))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            boards=[NS(mcu_temp=NS(current=55.0), v_in=None, v12=None)],
        ))

        vitals = tracker._data["vitals"]
        assert vitals["mcu_temp_min"] == 40.0
        assert vitals["mcu_temp_max"] == 55.0

    def test_vin_tracking(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            boards=[NS(mcu_temp=None, v_in=NS(current=24.1), v12=None)],
        ))

        vitals = tracker._data["vitals"]
        assert vitals["vin_min"] == 24.1
        assert vitals["vin_max"] == 24.1

    def test_v12_tracking(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            boards=[NS(mcu_temp=None, v_in=None, v12=NS(current=12.05))],
        ))

        vitals = tracker._data["vitals"]
        assert vitals["v12_min"] == 12.05
        assert vitals["v12_max"] == 12.05

    def test_no_boards_is_safe(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle"))
        # Should not crash
        assert tracker._data["vitals"]["mcu_temp_max"] is None


class TestSbcVitals:
    def test_sbc_cpu_temp(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            sbc=NS(cpu=NS(temperature=62.5, avg_load=None), memory=None, uptime=None),
        ))

        vitals = tracker._data["vitals"]
        assert vitals["sbc_cpu_temp_max"] == 62.5

    def test_sbc_cpu_load_avg(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            sbc=NS(cpu=NS(temperature=None, avg_load=15), memory=None, uptime=None),
        ))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            sbc=NS(cpu=NS(temperature=None, avg_load=25), memory=None, uptime=None),
        ))

        vitals = tracker._data["vitals"]
        assert vitals["sbc_cpu_load_avg_count"] == 2
        avg = vitals["sbc_cpu_load_avg_sum"] / vitals["sbc_cpu_load_avg_count"]
        assert abs(avg - 0.2) < 0.001

    def test_sbc_memory_min(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            sbc=NS(cpu=None, memory=NS(available=500_000_000), uptime=None),
        ))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            sbc=NS(cpu=None, memory=NS(available=300_000_000), uptime=None),
        ))

        vitals = tracker._data["vitals"]
        assert vitals["sbc_memory_min_bytes"] == 300_000_000


class TestUptimeTracking:
    def test_firmware_uptime_recorded(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", up_time=1000))

        assert tracker._data["uptime"]["firmware_uptime_secs"] == 1000

    def test_firmware_reboot_detected(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", up_time=1000))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", up_time=5))

        assert tracker._data["uptime"]["firmware_reboots"] == 1

    def test_firmware_uptime_increasing_no_reboot(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", up_time=1000))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", up_time=1250))

        assert tracker._data["uptime"]["firmware_reboots"] == 0

    def test_sbc_reboot_detected(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            sbc=NS(cpu=None, memory=None, uptime=5000),
        ))
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            sbc=NS(cpu=None, memory=None, uptime=10),
        ))

        assert tracker._data["uptime"]["sbc_reboots"] == 1


class TestVolumeTracking:
    def test_volume_free_space(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            volumes=[NS(mounted=True, free_space=5_000_000_000)],
        ))

        assert tracker._data["volume_free_bytes"] == 5_000_000_000

    def test_unmounted_volume_skipped(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            volumes=[NS(mounted=False, free_space=5_000_000_000)],
        ))

        assert tracker._data["volume_free_bytes"] is None

    def test_first_mounted_volume_used(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(
            state="idle",
            volumes=[
                NS(mounted=False, free_space=1_000),
                NS(mounted=True, free_space=9_000_000_000),
            ],
        ))

        assert tracker._data["volume_free_bytes"] == 9_000_000_000


class TestPauseWarmupTracking:
    def test_pause_time_tracked_from_object_model(self, tracker):
        """pause_duration from ObjectModel ticks up continuously while paused."""
        tracker._timer.reset()

        # Job running, no pause yet
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", pause_duration=None)))
        assert tracker.get_status()["lifetime"]["pause_seconds"] == 0.0

        # Pause starts, duration ticks up
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="paused", job=_job("test.gcode", pause_duration=5)))
        assert tracker.get_status()["lifetime"]["pause_seconds"] == 5.0

        # Still paused, duration increases
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="paused", job=_job("test.gcode", pause_duration=10)))
        assert tracker.get_status()["lifetime"]["pause_seconds"] == 10.0

    def test_pause_no_double_count(self, tracker):
        """Same pause_duration value on next tick adds nothing."""
        tracker._timer.reset()

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="paused", job=_job("test.gcode", pause_duration=20)))

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("test.gcode", pause_duration=20)))

        assert tracker.get_status()["lifetime"]["pause_seconds"] == 20.0

    def test_no_pause_when_none(self, tracker):
        """If pause_duration stays None, no pause is counted."""
        tracker._timer.reset()

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", job=_job("test.gcode", pause_duration=None)))

        assert tracker.get_status()["lifetime"]["pause_seconds"] == 0.0

    def test_pause_accumulates_across_jobs(self, tracker):
        """Pause from multiple jobs accumulates."""
        tracker._timer.reset()

        # First job: 10s pause
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("j1.gcode", pause_duration=10)))

        # Job ends
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="idle", job=_job(None)))

        # Second job: 15s pause
        tracker._timer._last_tick -= 0.25
        tracker.update(_model(state="processing", job=_job("j2.gcode", pause_duration=15)))

        assert tracker.get_status()["lifetime"]["pause_seconds"] == 25.0


class TestServiceResetNewScopes:
    def test_reset_fans(self, tracker, data_dir):
        tracker._data["service"]["fans"] = {"0": {"on_seconds": 7200}}
        values = tracker.service_reset("fans", description="Fan replaced")
        assert values["0"]["on_seconds"] == 7200
        assert tracker._data["service"]["fans"]["0"]["on_seconds"] == 0.0

    def test_reset_fans_selective(self, tracker, data_dir):
        tracker._data["service"]["fans"] = {"0": {"on_seconds": 100}, "1": {"on_seconds": 200}}
        values = tracker.service_reset("fans", keys=["0"], description="Fan 0 replaced")
        assert "0" in values
        assert "1" not in values
        assert tracker._data["service"]["fans"]["1"]["on_seconds"] == 200

    def test_reset_pause_time(self, tracker, data_dir):
        tracker._data["service"]["pause_seconds"] = 3600.0
        values = tracker.service_reset("pause_time", description="Reset pause")
        assert values["pause_seconds"] == 3600.0
        assert tracker._data["service"]["pause_seconds"] == 0.0

    def test_reset_warmup_time(self, tracker, data_dir):
        tracker._data["service"]["warmup_seconds"] = 1800.0
        values = tracker.service_reset("warmup_time", description="Reset warmup")
        assert values["warmup_seconds"] == 1800.0
        assert tracker._data["service"]["warmup_seconds"] == 0.0


class TestSnapshotNewFields:
    def test_snapshot_includes_fan_hours(self, tracker, data_dir):
        tracker._data["lifetime"]["fans"] = {"0": {"on_seconds": 7200}}
        tracker.create_shutdown_snapshot()

        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        snap = month["days"][0]
        assert "fan_on_hours" in snap
        assert snap["fan_on_hours"]["0"] == 2.0

    def test_snapshot_includes_vitals(self, tracker, data_dir):
        tracker._data["vitals"]["mcu_temp_max"] = 55.3
        tracker._data["vitals"]["mcu_temp_min"] = 38.1
        tracker._data["vitals"]["vin_min"] = 23.8
        tracker._data["vitals"]["vin_max"] = 24.2
        tracker.create_shutdown_snapshot()

        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        snap = month["days"][0]
        assert snap["mcu_temp_max"] == 55.3
        assert snap["mcu_temp_min"] == 38.1
        assert snap["vin_min"] == 23.8
        assert snap["vin_max"] == 24.2

    def test_snapshot_includes_sbc_vitals(self, tracker, data_dir):
        tracker._data["vitals"]["sbc_cpu_temp_max"] = 62.5
        tracker._data["vitals"]["sbc_cpu_load_avg_sum"] = 0.6
        tracker._data["vitals"]["sbc_cpu_load_avg_count"] = 3
        tracker._data["vitals"]["sbc_memory_min_bytes"] = 300_000_000
        tracker.create_shutdown_snapshot()

        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        snap = month["days"][0]
        assert snap["sbc_cpu_temp_max"] == 62.5
        assert snap["sbc_cpu_load_avg"] == 0.2
        assert snap["sbc_memory_min_mb"] == 286.1  # 300M / 1024 / 1024

    def test_snapshot_includes_reboots(self, tracker, data_dir):
        tracker._data["uptime"]["firmware_reboots"] = 2
        tracker.create_shutdown_snapshot()

        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        snap = month["days"][0]
        assert snap["firmware_reboots"] == 2

    def test_snapshot_includes_volume(self, tracker, data_dir):
        tracker._data["volume_free_bytes"] = 5_000_000_000
        tracker.create_shutdown_snapshot()

        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        snap = month["days"][0]
        assert snap["volume_free_mb"] == 4768.4  # 5G / 1024 / 1024

    def test_snapshot_omits_none_vitals(self, tracker, data_dir):
        """Vitals that are None should not appear in snapshot."""
        tracker.create_shutdown_snapshot()

        from vigil_persistence import load_month_history
        from datetime import date
        ym = date.today().strftime("%Y-%m")
        month = load_month_history(ym)
        snap = month["days"][0]
        assert "mcu_temp_max" not in snap
        assert "vin_min" not in snap
        assert "sbc_cpu_temp_max" not in snap
        assert "firmware_reboots" not in snap
        assert "volume_free_mb" not in snap


class TestStatusIncludesNewFields:
    def test_status_has_vitals(self, tracker):
        status = tracker.get_status()
        assert "vitals" in status
        assert "uptime" in status
        assert "volume_free_bytes" in status

    def test_initial_vitals_are_none(self, tracker):
        status = tracker.get_status()
        assert status["vitals"]["mcu_temp_max"] is None
        assert status["uptime"]["firmware_reboots"] == 0
        assert status["volume_free_bytes"] is None


class TestSchemaMigration:
    def test_old_data_gets_new_fields(self, data_dir):
        """Loading old data without new fields should add defaults."""
        old_data = {
            "schema_version": 1,
            "last_saved": "",
            "lifetime": {
                "machine_seconds": 1000,
                "print_seconds": 500,
                "jobs_total": 3,
                "jobs_successful": 2,
                "jobs_cancelled": 1,
                "axes": {"X": 100},
                "filament_mm": {"E0": 50},
                "heaters": {},
            },
            "service": {
                "machine_seconds": 100,
                "print_seconds": 50,
                "jobs_total": 1,
                "jobs_successful": 1,
                "jobs_cancelled": 0,
                "axes": {},
                "filament_mm": {},
                "heaters": {},
            },
            "service_log": [],
        }
        tracker = VigilTracker(old_data)
        assert "vitals" in tracker._data
        assert "uptime" in tracker._data
        assert "volume_free_bytes" in tracker._data
        assert tracker._data["lifetime"]["pause_seconds"] == 0.0
        assert tracker._data["lifetime"]["fans"] == {}
        assert tracker._data["service"]["warmup_seconds"] == 0.0
