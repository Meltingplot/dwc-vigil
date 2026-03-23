"""Tests for vigil_tracker — data model, tracking logic, service reset.

Test models use SimpleNamespace to mirror the dsf-python ObjectModel attribute
structure (snake_case attributes accessed via getattr).
"""

import copy
from types import SimpleNamespace as NS

import pytest

from vigil_persistence import empty_state
from vigil_tracker import VigilTracker


def _model(state=None, move=None, heat=None, job=None):
    """Build a minimal ObjectModel-like namespace."""
    m = NS()
    if state is not None:
        m.state = NS(status=state)
    if move is not None:
        m.move = move
    if heat is not None:
        m.heat = heat
    if job is not None:
        m.job = job
    return m


def _axes(*args):
    """Build a move namespace with axes.  Each arg is (letter, machine_position)."""
    return NS(axes=[NS(letter=l, machine_position=p) for l, p in args],
              extruders=[])


def _extruders(*positions):
    """Build a move namespace with extruders.  Each arg is a position float."""
    return NS(axes=[], extruders=[NS(position=p) for p in positions])


def _heaters(*args):
    """Build a heat namespace.  Each arg is (state_str, current_float)."""
    return NS(heaters=[NS(state=s, current=c) for s, c in args])


def _job(file_name):
    """Build a job namespace."""
    if file_name is None:
        return NS(file=NS(file_name=None))
    return NS(file=NS(file_name=file_name))


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
        tracker._timer.reset()
        tracker.update(_model(move=_axes(("X", 0))))

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(move=_axes(("X", 100))))

        status = tracker.get_status()
        assert status["lifetime"]["axes"]["X"] == 100.0

    def test_dynamic_axis_detection(self, tracker):
        tracker._timer.reset()
        tracker.update(_model(move=_axes(("X", 0), ("Y", 0), ("Z", 0))))

        tracker._timer._last_tick -= 0.25
        tracker.update(_model(move=_axes(("X", 50), ("Y", 30), ("Z", 10))))

        status = tracker.get_status()
        assert "X" in status["lifetime"]["axes"]
        assert "Y" in status["lifetime"]["axes"]
        assert "Z" in status["lifetime"]["axes"]


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
        tracker.update(_model(state="idle", move=NS(axes=[NS(letter="X")], extruders=[])))
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
        tracker.update(_model(state="idle", heat=NS(heaters=[NS(current=0.5)])))
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

    def test_json_export_has_schema_version(self, tracker):
        export = tracker.export_json()
        assert export["schema_version"] == 1
        assert "service_log" in export
