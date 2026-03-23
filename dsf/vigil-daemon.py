#!/usr/bin/env python3
"""Vigil — DSF SBC daemon for machine monitoring.

Connects to DSF, subscribes to the object model for real-time tracking,
registers HTTP endpoints for the DWC frontend, and persists data with
crash-safe atomic writes.
"""

import json
import logging
import os
import signal
import sys
import time
import traceback

# Monkey-patch dsf-python: PluginManifest._data deserialization bug
try:
    from dsf.object_model.plugins.plugin_manifest import PluginManifest as _PM
    from dsf.object_model.model_dictionary import ModelDictionary as _MD

    _original_pm_init = _PM.__init__

    def _patched_pm_init(self):
        _original_pm_init(self)
        self._data = _MD(False)

    _PM.__init__ = _patched_pm_init
except ImportError:
    pass

# Monkey-patch dsf-python: BoardState enum missing values (e.g. timedOut)
try:
    import dsf.object_model.boards.boards as _boards_mod
    from dsf.object_model.boards.boards import Board as _Board
    from enum import Enum

    class _PatchedBoardState(str, Enum):
        unknown = "unknown"
        flashing = "flashing"
        flashFailed = "flashFailed"
        resetting = "resetting"
        running = "running"
        timedOut = "timedOut"

    _boards_mod.BoardState = _PatchedBoardState

    def _safe_state_setter(self, value):
        try:
            if value is None or isinstance(value, _PatchedBoardState):
                self._state = value
            elif isinstance(value, str):
                self._state = _PatchedBoardState(value)
            else:
                raise TypeError(f"invalid type for Board.state: {type(value)}")
        except (ValueError, KeyError):
            self._state = _PatchedBoardState.unknown

    _Board.state = _Board.state.setter(_safe_state_setter)
except ImportError:
    pass

from dsf.connections import CommandConnection, SubscribeConnection, SubscriptionMode
from dsf.object_model import HttpEndpointType
from dsf.http import HttpEndpointConnection, HttpResponseType

from vigil_tracker import VigilTracker
from vigil_persistence import load_data, ensure_data_dir, SAVE_INTERVAL_S
from vigil_api import ENDPOINTS, json_response, error_response

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("vigil")

PLUGIN_ID = "Vigil"
API_NAMESPACE = "Vigil"

# Global tracker for signal handler access
_tracker = None
_shutdown = False


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT: save data and exit."""
    global _shutdown
    _shutdown = True
    logger.info("Signal %d received, shutting down...", signum)


def set_plugin_data(cmd, key, value):
    """Set a key in the plugin's Object Model data."""
    try:
        cmd.set_plugin_data(PLUGIN_ID, key, json.dumps(value) if not isinstance(value, str) else value)
    except Exception as e:
        logger.debug("Failed to set plugin data %s: %s", key, e)


def update_plugin_data(cmd, tracker):
    """Push summary data to the DSF Object Model for frontend visibility."""
    summary = tracker.get_plugin_data_summary()
    for key, value in summary.items():
        set_plugin_data(cmd, key, str(value) if not isinstance(value, str) else value)


# --- HTTP endpoint handler factory ---

def _make_async_handler(tracker, handler_func):
    """Create an async HTTP handler for a dsf-python endpoint."""
    async def _handler(http_conn):
        request = await http_conn.read_request()
        try:
            queries = getattr(request, "queries", {}) or {}
            body = getattr(request, "body", "") or ""
            response = handler_func(tracker, body, queries)

            content_type = response.get("contentType", "application/json")
            resp_type_str = response.get("responseType", "")

            if resp_type_str == "file":
                resp_type = HttpResponseType.File
            elif content_type == "application/json":
                resp_type = HttpResponseType.JSON
            else:
                resp_type = HttpResponseType.PlainText

            await http_conn.send_response(
                response.get("status", 200),
                response.get("body", ""),
                resp_type,
            )
        except Exception:
            logger.error("Handler error: %s", traceback.format_exc())
            await http_conn.send_response(
                500,
                json.dumps({"error": "Internal server error"}),
                HttpResponseType.JSON,
            )
    return _handler


def register_endpoints(cmd, tracker):
    """Register all HTTP endpoints with DSF."""
    registered = []
    for (method, path), handler_func in ENDPOINTS.items():
        http_type = HttpEndpointType.GET if method == "GET" else HttpEndpointType.POST
        try:
            endpoint = cmd.add_http_endpoint(http_type, API_NAMESPACE, path)
            endpoint.set_endpoint_handler(_make_async_handler(tracker, handler_func))
            registered.append(endpoint)
            logger.debug("Registered: %s /%s/%s", method, API_NAMESPACE, path)
        except Exception as exc:
            logger.error("Failed to register %s %s: %s", method, path, exc)
    return registered


def _subscribe_filters():
    """Return the Object Model filter list for SubscribeConnection."""
    return [
        "state/status",
        "move/axes[]/letter,machinePosition",
        "move/extruders[]/position",
        "heat/heaters[]/state,current",
        "job/file/fileName",
    ]


def _object_model_to_dict(model) -> dict:
    """Convert a dsf-python object model (or patch) to a plain dict."""
    if isinstance(model, dict):
        return model
    try:
        return json.loads(model.to_json())
    except Exception:
        pass
    # Fallback: manually extract what we need
    result = {}
    try:
        state = getattr(model, "state", None)
        if state:
            result["state"] = {"status": getattr(state, "status", None)}
    except Exception:
        pass
    try:
        move = getattr(model, "move", None)
        if move:
            axes_list = []
            for ax in (getattr(move, "axes", None) or []):
                axes_list.append({
                    "letter": getattr(ax, "letter", None),
                    "machinePosition": getattr(ax, "machine_position", None),
                })
            extruders_list = []
            for ext in (getattr(move, "extruders", None) or []):
                extruders_list.append({
                    "position": getattr(ext, "position", None),
                })
            result["move"] = {"axes": axes_list, "extruders": extruders_list}
    except Exception:
        pass
    try:
        heat = getattr(model, "heat", None)
        if heat:
            heaters_list = []
            for h in (getattr(heat, "heaters", None) or []):
                heaters_list.append({
                    "state": getattr(h, "state", None),
                    "current": getattr(h, "current", None),
                })
            result["heat"] = {"heaters": heaters_list}
    except Exception:
        pass
    try:
        job = getattr(model, "job", None)
        if job:
            jf = getattr(job, "file", None)
            result["job"] = {"file": {"fileName": getattr(jf, "file_name", None) if jf else None}}
    except Exception:
        pass
    return result


def main():
    global _tracker, _shutdown

    # Signal handlers
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Ensure data directory exists
    ensure_data_dir()

    # Load persisted data (with recovery)
    data = load_data()
    tracker = VigilTracker(data)
    _tracker = tracker

    # CommandConnection for HTTP endpoints + plugin data
    cmd = CommandConnection()
    cmd.connect()

    # Register HTTP endpoints
    endpoints = register_endpoints(cmd, tracker)
    logger.info("Registered %d HTTP endpoints", len(endpoints))

    # Push initial plugin data
    update_plugin_data(cmd, tracker)

    # SubscribeConnection for Object Model updates
    sub = SubscribeConnection(SubscriptionMode.PATCH, filter_list=_subscribe_filters())
    sub.connect()

    # First call must be get_object_model() to receive the full initial model
    initial_model = sub.get_object_model()
    model_dict = _object_model_to_dict(initial_model)
    tracker.update(model_dict)

    logger.info("Vigil daemon started — tracking active")

    last_save = time.monotonic()

    try:
        while not _shutdown:
            try:
                # Receive Object Model patch (JSON string, ~250ms cycle).
                # TimeoutError is expected when idle — the default 3s timeout
                # acts as a loop heartbeat for periodic saves and shutdown checks.
                patch_json = sub.get_object_model_patch()
                model_dict = json.loads(patch_json)
                tracker.update(model_dict)
            except TimeoutError:
                pass
            except Exception as e:
                if _shutdown:
                    break
                logger.error("Subscribe error: %s", e)
                time.sleep(1)
                continue

            # Periodic save
            now = time.monotonic()
            if tracker.dirty and (now - last_save) >= SAVE_INTERVAL_S:
                try:
                    tracker.save()
                    update_plugin_data(cmd, tracker)
                    last_save = now
                except Exception as e:
                    logger.error("Save failed: %s", e)

    finally:
        # Shutdown: create final snapshot and save
        logger.info("Saving final state...")
        try:
            tracker.create_shutdown_snapshot()
            tracker.save()
        except Exception as e:
            logger.error("Final save failed: %s", e)

        # Cleanup
        for ep in endpoints:
            try:
                ep.close()
            except Exception:
                pass
        try:
            sub.close()
        except Exception:
            pass
        try:
            cmd.close()
        except Exception:
            pass

        logger.info("Vigil daemon stopped")


if __name__ == "__main__":
    main()
