"""Tests for vigil_tracker — data model, tracking logic, service reset."""

import copy

import pytest

from vigil_persistence import empty_state
from vigil_tracker import VigilTracker


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
        # Simulate: machine is idle (not "off"), so machine_seconds should increase
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0  # Pretend 1 second has passed
        tracker.update({"state": {"status": "idle"}})

        status = tracker.get_status()
        assert status["lifetime"]["machine_seconds"] > 0
        assert status["session"]["machine_seconds"] > 0

    def test_print_time_only_during_processing(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update({"state": {"status": "idle"}})

        status = tracker.get_status()
        assert status["lifetime"]["print_seconds"] == 0.0

        tracker._timer._last_tick -= 1.0
        tracker.update({"state": {"status": "processing"}})

        status = tracker.get_status()
        assert status["lifetime"]["print_seconds"] > 0

    def test_no_time_when_off(self, tracker):
        tracker._timer.reset()
        tracker._timer._last_tick -= 1.0
        tracker.update({"state": {"status": "off"}})

        status = tracker.get_status()
        assert status["lifetime"]["machine_seconds"] == 0.0


class TestAxisTracking:
    def test_axis_travel(self, tracker):
        # First update establishes baseline
        tracker._timer.reset()
        tracker.update({"move": {"axes": [{"letter": "X", "machinePosition": 0}]}})

        # Second update should register travel
        tracker._timer._last_tick -= 0.25
        tracker.update({"move": {"axes": [{"letter": "X", "machinePosition": 100}]}})

        status = tracker.get_status()
        assert status["lifetime"]["axes"]["X"] == 100.0

    def test_dynamic_axis_detection(self, tracker):
        tracker._timer.reset()
        tracker.update({"move": {"axes": [
            {"letter": "X", "machinePosition": 0},
            {"letter": "Y", "machinePosition": 0},
            {"letter": "Z", "machinePosition": 0},
        ]}})

        tracker._timer._last_tick -= 0.25
        tracker.update({"move": {"axes": [
            {"letter": "X", "machinePosition": 50},
            {"letter": "Y", "machinePosition": 30},
            {"letter": "Z", "machinePosition": 10},
        ]}})

        status = tracker.get_status()
        assert "X" in status["lifetime"]["axes"]
        assert "Y" in status["lifetime"]["axes"]
        assert "Z" in status["lifetime"]["axes"]


class TestExtruderTracking:
    def test_filament_net_positive_only(self, tracker):
        # Establish baseline
        tracker._timer.reset()
        tracker.update({"move": {"extruders": [{"position": 0}]}})

        # Extrude 100mm
        tracker._timer._last_tick -= 0.25
        tracker.update({"move": {"extruders": [{"position": 100}]}})

        # Retract 10mm
        tracker._timer._last_tick -= 0.25
        tracker.update({"move": {"extruders": [{"position": 90}]}})

        status = tracker.get_status()
        # Total travel: 100 + 10 = 110
        assert status["lifetime"]["axes"]["E0"] == 110.0
        # Net filament: 100 (retract not counted)
        assert status["lifetime"]["filament_mm"]["E0"] == 100.0


class TestJobTracking:
    def test_job_start(self, tracker):
        tracker._timer.reset()
        tracker._prev_job_file = None
        tracker.update({"job": {"file": {"fileName": "test.gcode"}}, "state": {"status": "processing"}})

        status = tracker.get_status()
        assert status["lifetime"]["jobs_total"] == 1

    def test_job_success(self, tracker):
        tracker._prev_status = "processing"
        tracker._prev_job_file = "test.gcode"
        tracker._timer.reset()
        tracker.update({"state": {"status": "idle"}, "job": {"file": {"fileName": None}}})

        status = tracker.get_status()
        assert status["lifetime"]["jobs_successful"] == 1

    def test_job_cancel(self, tracker):
        tracker._prev_status = "processing"
        tracker._prev_job_file = "test.gcode"
        tracker._timer.reset()
        tracker.update({"state": {"status": "cancelling"}, "job": {"file": {"fileName": None}}})

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
