"""
Vigil API — HTTP endpoint handlers for the DWC frontend.

All handlers follow the pattern: handler(tracker, body, queries) → response dict
Response dict: {"status": int, "body": str, "contentType": str}
"""

import json
import logging
import tempfile
import os

from vigil_persistence import load_history_range

logger = logging.getLogger("vigil.api")


def json_response(data, status=200):
    return {
        "status": status,
        "body": json.dumps(data),
        "contentType": "application/json",
    }


def error_response(message, status=400):
    return json_response({"error": message}, status)


# --- Handlers ---


def handle_status(tracker, body, queries):
    """GET /machine/Vigil/status — Return all three counter tiers."""
    return json_response(tracker.get_status())


def handle_history(tracker, body, queries):
    """GET /machine/Vigil/history?days=30 — Return daily snapshots."""
    try:
        days = int(queries.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    days = max(1, min(days, 365))

    snapshots = load_history_range(days)
    return json_response({"days": snapshots})


def handle_export(tracker, body, queries):
    """GET /machine/Vigil/export?format=json|csv — Export data."""
    fmt = queries.get("format", "json")

    if fmt == "csv":
        csv_data = tracker.export_csv()
        # Write to temp file for DSF file response
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", prefix="vigil_export_",
            delete=False, encoding="utf-8"
        )
        tmp.write(csv_data)
        tmp.close()
        return {
            "status": 200,
            "body": tmp.name,
            "contentType": "text/csv",
            "responseType": "file",
        }

    return json_response(tracker.export_json())


def handle_service_reset(tracker, body, queries):
    """POST /machine/Vigil/service/reset — Reset service counters."""
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return error_response("Invalid JSON body")

    scope = data.get("scope")
    if not scope:
        return error_response("Missing 'scope' field")

    description = data.get("description", "")
    if len(description) < 3:
        return error_response("'description' must be at least 3 characters")

    keys = data.get("keys")
    component = data.get("component")

    try:
        values_before = tracker.service_reset(
            scope=scope,
            keys=keys,
            description=description,
            component=component,
        )
    except ValueError as e:
        return error_response(str(e))

    # Save immediately after reset
    try:
        tracker.save()
    except Exception as e:
        logger.error("Failed to save after reset: %s", e)

    return json_response({"ok": True, "values_before_reset": values_before})


def handle_service_event(tracker, body, queries):
    """POST /machine/Vigil/service/event — Log a service event (no reset)."""
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return error_response("Invalid JSON body")

    component = data.get("component", "other")
    description = data.get("description", "")
    if len(description) < 3:
        return error_response("'description' must be at least 3 characters")

    tracker.add_service_event(component=component, description=description)

    try:
        tracker.save()
    except Exception as e:
        logger.error("Failed to save after service event: %s", e)

    return json_response({"ok": True})


def handle_service_log(tracker, body, queries):
    """GET /machine/Vigil/service/log — Return service log."""
    return json_response({"log": tracker.get_service_log()})


# --- Endpoint registry ---
# Maps (HTTP_METHOD, endpoint_path) to handler function.

ENDPOINTS = {
    ("GET", "status"): handle_status,
    ("GET", "history"): handle_history,
    ("GET", "export"): handle_export,
    ("POST", "service/reset"): handle_service_reset,
    ("POST", "service/event"): handle_service_event,
    ("GET", "service/log"): handle_service_log,
}
