"""Tests for vigil_api — HTTP endpoint handler logic."""

import json

import pytest

from vigil_persistence import empty_state
from vigil_tracker import VigilTracker
from vigil_api import (
    handle_status,
    handle_service_reset,
    handle_service_event,
    handle_service_log,
    handle_history,
    handle_export,
)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VIGIL_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def tracker(data_dir):
    data = empty_state()
    data["lifetime"]["machine_seconds"] = 3600
    data["lifetime"]["print_seconds"] = 1800
    data["lifetime"]["jobs_total"] = 10
    data["lifetime"]["jobs_successful"] = 8
    data["lifetime"]["jobs_cancelled"] = 2
    data["service"]["machine_seconds"] = 1000
    return VigilTracker(data)


class TestStatusEndpoint:
    def test_returns_all_tiers(self, tracker):
        resp = handle_status(tracker, "", {})
        assert resp["status"] == 200
        body = json.loads(resp["body"])
        assert "lifetime" in body
        assert "service" in body
        assert "session" in body

    def test_lifetime_values(self, tracker):
        resp = handle_status(tracker, "", {})
        body = json.loads(resp["body"])
        assert body["lifetime"]["machine_seconds"] == 3600
        assert body["lifetime"]["jobs_total"] == 10


class TestServiceResetEndpoint:
    def test_valid_reset(self, tracker):
        body = json.dumps({"scope": "machine_time", "description": "Board replaced"})
        resp = handle_service_reset(tracker, body, {})
        assert resp["status"] == 200
        result = json.loads(resp["body"])
        assert result["ok"] is True
        assert result["values_before_reset"]["machine_seconds"] == 1000

    def test_missing_scope(self, tracker):
        body = json.dumps({"description": "Test"})
        resp = handle_service_reset(tracker, body, {})
        assert resp["status"] == 400

    def test_short_description(self, tracker):
        body = json.dumps({"scope": "jobs", "description": "ab"})
        resp = handle_service_reset(tracker, body, {})
        assert resp["status"] == 400

    def test_invalid_json(self, tracker):
        resp = handle_service_reset(tracker, "not json", {})
        assert resp["status"] == 400

    def test_invalid_scope(self, tracker):
        body = json.dumps({"scope": "nonexistent", "description": "Test desc"})
        resp = handle_service_reset(tracker, body, {})
        assert resp["status"] == 400


class TestServiceEventEndpoint:
    def test_valid_event(self, tracker):
        body = json.dumps({"component": "fan_hotend", "description": "Fan replaced"})
        resp = handle_service_event(tracker, body, {})
        assert resp["status"] == 200

    def test_short_description(self, tracker):
        body = json.dumps({"component": "other", "description": "ab"})
        resp = handle_service_event(tracker, body, {})
        assert resp["status"] == 400


class TestServiceLogEndpoint:
    def test_empty_log(self, tracker):
        resp = handle_service_log(tracker, "", {})
        body = json.loads(resp["body"])
        assert body["log"] == []

    def test_log_after_events(self, tracker):
        tracker.add_service_event("fan_hotend", "Fan replaced")
        tracker.service_reset("jobs", description="Counter correction")

        resp = handle_service_log(tracker, "", {})
        body = json.loads(resp["body"])
        assert len(body["log"]) == 2


class TestHistoryEndpoint:
    def test_empty_history(self, tracker):
        resp = handle_history(tracker, "", {})
        body = json.loads(resp["body"])
        assert body["days"] == []

    def test_days_parameter(self, tracker):
        resp = handle_history(tracker, "", {"days": "7"})
        assert resp["status"] == 200

    def test_invalid_days(self, tracker):
        resp = handle_history(tracker, "", {"days": "abc"})
        assert resp["status"] == 200  # Falls back to 30


class TestExportEndpoint:
    def test_json_export(self, tracker):
        resp = handle_export(tracker, "", {"format": "json"})
        assert resp["status"] == 200
        body = json.loads(resp["body"])
        assert "lifetime" in body

    def test_csv_export(self, tracker):
        resp = handle_export(tracker, "", {"format": "csv"})
        assert resp["status"] == 200
        assert resp["responseType"] == "file"

    def test_default_format_is_json(self, tracker):
        resp = handle_export(tracker, "", {})
        assert resp["status"] == 200
        assert resp["contentType"] == "application/json"


class TestServiceEventInvalidJson:
    def test_invalid_json_body(self, tracker):
        resp = handle_service_event(tracker, "not json", {})
        assert resp["status"] == 400
        body = json.loads(resp["body"])
        assert "error" in body

    def test_empty_body(self, tracker):
        resp = handle_service_event(tracker, "", {})
        assert resp["status"] == 400  # description too short


class TestSaveFailures:
    def test_reset_save_failure(self, tracker, monkeypatch):
        """Service reset should still return success even if save fails."""
        def broken_save():
            raise OSError("disk full")
        monkeypatch.setattr(tracker, "save", broken_save)
        body = json.dumps({"scope": "machine_time", "description": "Board replaced"})
        resp = handle_service_reset(tracker, body, {})
        assert resp["status"] == 200

    def test_event_save_failure(self, tracker, monkeypatch):
        """Service event should still return success even if save fails."""
        def broken_save():
            raise OSError("disk full")
        monkeypatch.setattr(tracker, "save", broken_save)
        body = json.dumps({"component": "nozzle", "description": "Nozzle replaced"})
        resp = handle_service_event(tracker, body, {})
        assert resp["status"] == 200
