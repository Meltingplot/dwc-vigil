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

# --------------------------------------------------------------------------------
# dsf-python compatibility patches.
#
# The plugin ships one daemon for two DSF generations (the DWC 3.6 package carries
# sbcDsfVersion 3.6, the 3.7 package 3.7), and dsf-python 3.7 is a substantial rewrite:
# hand-written properties became `model_prop` descriptors and `BaseConnection.connect`
# was renamed to `_connect`. Every patch below therefore states which generations it is
# for, targets whichever spelling the installed library actually has, and swallows any
# failure -- an unpatchable library must not stop the daemon from starting, since most
# of these guard against inputs that may never occur.
#
# Verified against dsf-python v3.6-dev and v3.7-dev (3.7.0-beta.1) on 2026-09-10.
# --------------------------------------------------------------------------------


def _patch_property_setter(cls, name, setter):
    """Replace the setter of a model property, keeping its getter.

    Works on both generations: 3.6 hand-writes these as `property` objects and 3.7
    generates them with `model_prop`, but both end up as a `property` on the class and
    both store the value in `_<name>`.
    """
    prop = getattr(cls, name, None)
    if not isinstance(prop, property):
        return False
    setattr(cls, name, prop.setter(setter))
    return True


# dsf-python 3.6 only: PluginManifest.__init__ creates _data as a plain dict, which the
# deserializer skips, so plugin.data is always empty. 3.7 declares it as a
# `model_prop('data', ModelDictionary, ...)` and needs no help; re-seeding _data there
# is a no-op of the same shape.
try:
    from dsf.object_model.plugins.plugin_manifest import PluginManifest as _PM
    from dsf.object_model.model_dictionary import ModelDictionary as _MD

    _original_pm_init = _PM.__init__

    def _patched_pm_init(self):
        _original_pm_init(self)
        self._data = _MD(False)

    _PM.__init__ = _patched_pm_init
except Exception:
    pass

# dsf-python 3.7 only: GCodeFileInfo.custom_info (like ObjectModel.globals and
# PluginManifest.data) is a non-nullable `model_prop` over a ModelDictionary, and the
# setter's helper `_set_model_prop` has no branch for None. DSF does send
# `"customInfo": null` in PATCH updates, which raises
# "GCodeFileInfo._custom_info must be of type ModelDictionary ... Got NoneType" and
# aborts update_from_json() for the whole patch. ModelDictionary.update_from_json(None)
# already means "clear", so route a None aimed at a dictionary (or collection) there.
# 3.6 hand-writes custom_info as a getter-only property the deserializer skips, and has
# no `_set_model_prop` to patch.
try:
    import dsf.object_model.utils as _om_utils
    from dsf.object_model.model_collection import ModelCollection as _ModelCollection
    from dsf.object_model.model_dictionary import ModelDictionary as _ModelDictionary

    _original_set_model_prop = _om_utils._set_model_prop

    def _patched_set_model_prop(instance, name, runtime_type, current_value, value):
        if value is None:
            if isinstance(current_value, _ModelDictionary):
                current_value.update_from_json(None)
                return
            if isinstance(current_value, _ModelCollection):
                current_value.update_from_json([])
                return
        return _original_set_model_prop(instance, name, runtime_type, current_value, value)

    # model_prop's setter looks `_set_model_prop` up in the utils module at call time
    _om_utils._set_model_prop = _patched_set_model_prop
except Exception:
    pass

# Both generations: the BoardState enum is missing values DSF reports (e.g. timedOut).
# Assigning one raises ValueError from the property setter, which takes down the whole
# get_object_model() call rather than just that board.
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

    _patch_property_setter(_Board, "state", _safe_state_setter)
except Exception:
    pass

# dsf-python 3.6 only: NetworkInterfaceType is missing 'ethernet', which DSF 3.6.3-rc.1
# reports; the setter raises ValueError on unknown strings and crashes the whole
# get_object_model() call. 3.7 has the value, but the safe setter still guards against
# the next one nobody has seen yet.
try:
    import dsf.object_model.network.network_interface_type as _nit_mod
    import dsf.object_model.network.network_interface as _ni_mod
    from dsf.object_model.network.network_interface import NetworkInterface as _NetworkInterface
    from enum import Enum

    class _PatchedNetworkInterfaceType(str, Enum):
        lan = "lan"
        wifi = "wifi"
        ethernet = "ethernet"
        unknown = "unknown"

    _nit_mod.NetworkInterfaceType = _PatchedNetworkInterfaceType
    _ni_mod.NetworkInterfaceType = _PatchedNetworkInterfaceType

    def _safe_type_setter(self, value):
        try:
            if value is None or value == "":
                self._type = _PatchedNetworkInterfaceType.wifi
            elif isinstance(value, _PatchedNetworkInterfaceType):
                self._type = value
            elif isinstance(value, str):
                self._type = _PatchedNetworkInterfaceType(value)
            else:
                self._type = _PatchedNetworkInterfaceType.unknown
        except (ValueError, KeyError):
            self._type = _PatchedNetworkInterfaceType.unknown

    _patch_property_setter(_NetworkInterface, "type", _safe_type_setter)
except Exception:
    pass

# Both generations: Axis.letter crashes on invalid values (e.g. '\x00' from
# uninitialized axes when the plugin loads before firmware has configured them).
try:
    from dsf.object_model.move.axis import Axis as _Axis, AxisLetter as _AxisLetter

    def _safe_letter_setter(self, value):
        try:
            if value is None:
                self._letter = _AxisLetter.none
            elif isinstance(value, _AxisLetter):
                self._letter = value
            elif isinstance(value, str):
                self._letter = _AxisLetter(value)
            else:
                self._letter = _AxisLetter.none
        except (ValueError, KeyError):
            self._letter = _AxisLetter.none

    _patch_property_setter(_Axis, "letter", _safe_letter_setter)
except Exception:
    pass

# Both generations: the server init message is read with a fixed-size
# self.socket.recv(50). DSF sends a greeting longer than 50 bytes (e.g. one carrying a
# GUID id), so the JSON is truncated mid-string and json.loads raises
# "JSONDecodeError: Unterminated string". Read until a complete JSON object has arrived
# instead, keeping any trailing bytes for the next read.
#
# dsf-python 3.7 renamed this method from `connect` to `_connect` (CommandConnection and
# SubscribeConnection now call `super()._connect(...)`), so patch whichever names the
# installed class actually has -- writing only the 3.6 name would leave 3.7 running the
# unpatched recv(50).
try:
    import socket as _socket
    from dsf.connections.base_connection import BaseConnection as _BaseConnection
    from dsf.connections.init_messages.server_init_message import (
        ServerInitMessage as _ServerInitMessage,
    )
    from dsf.connections.exceptions import (
        IncompatibleVersionException as _IncompatibleVersionException,
    )

    from vigil_socket import read_json_object as _read_json_object

    def _patched_connect(self, init_message, socket_file):
        self.socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        self.socket.connect(socket_file)
        self.socket.settimeout(self.timeout if self.timeout > 0 else None)

        json_string, leftover = _read_json_object(self.socket.recv, self.timeout)
        # Preserve any bytes received past the init message for later reads.
        self.input = leftover

        server_init_msg = _ServerInitMessage.from_json(json.loads(json_string))
        if not server_init_msg.is_compatible():
            raise _IncompatibleVersionException(
                f"Incompatible API version (need {server_init_msg.PROTOCOL_VERSION}, "
                f"got {server_init_msg.version})"
            )
        self.id = server_init_msg.id
        self.send(init_message)

        response = self.receive_response()
        if not getattr(response, "success", True):
            raise Exception(
                f"Could not set connection type {init_message.mode} "
                f"({response.error_type}: {response.error_message})"
            )

    for _name in ("connect", "_connect"):
        if hasattr(_BaseConnection, _name):
            setattr(_BaseConnection, _name, _patched_connect)
except Exception:
    pass

from dsf.connections import CommandConnection, SubscribeConnection, SubscriptionMode
from dsf.object_model import HttpEndpointType
from dsf.http import HttpEndpointConnection, HttpResponseType

from vigil_tracker import VigilTracker
from vigil_persistence import load_data, ensure_data_dir, SAVE_INTERVAL_S
from vigil_api import ENDPOINTS, json_response, error_response

# DSF redirects stdout to "success" messages and stderr to "error" messages in
# the DWC console (sbcOutputRedirected). Log to stderr so warnings and errors
# are not reported as successes.
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("vigil")

PLUGIN_ID = "Vigil"
API_NAMESPACE = "Vigil"

# DSF may launch the plugin before duetcontrolserver accepts connections
# (e.g. on boot or right after a plugin upgrade). Retry instead of exiting,
# which would leave the plugin stopped ("partially started" in DWC).
CONNECT_ATTEMPTS = 15
CONNECT_RETRY_DELAY_S = 2.0

# Global tracker for signal handler access
_tracker = None
_shutdown = False


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT: save data and exit."""
    global _shutdown
    _shutdown = True
    logger.debug("Signal %d received, shutting down...", signum)


def connect_with_retry(connection, description, attempts=CONNECT_ATTEMPTS,
                       delay=CONNECT_RETRY_DELAY_S):
    """Connect to DCS, retrying while the socket is not available yet.

    Returns True once connected, False if shutdown was requested while waiting.
    Raises the last error if all attempts fail.
    """
    last_error = None
    for attempt in range(1, attempts + 1):
        if _shutdown:
            return False
        try:
            connection.connect()
            if attempt > 1:
                logger.warning("%s connected after %d attempts", description, attempt)
            return True
        except Exception as exc:
            last_error = exc
            logger.warning(
                "%s connection attempt %d/%d failed: %s",
                description, attempt, attempts, exc,
            )
            if attempt < attempts:
                time.sleep(delay)

    raise RuntimeError(
        f"{description} connection failed after {attempts} attempts: {last_error}"
    )


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
    if not connect_with_retry(cmd, "CommandConnection"):
        return

    endpoints = []
    sub = None

    try:
        # Register HTTP endpoints
        endpoints = register_endpoints(cmd, tracker)
        logger.debug("Registered %d HTTP endpoints", len(endpoints))

        # Push initial plugin data
        update_plugin_data(cmd, tracker)

        # SubscribeConnection for Object Model updates
        sub = SubscribeConnection(SubscriptionMode.PATCH)
        if not connect_with_retry(sub, "SubscribeConnection"):
            return

        # First call: receive the complete object model
        object_model = sub.get_object_model()
        tracker.update(object_model)

        logger.debug("Vigil daemon started — tracking active")

        last_save = time.monotonic()

        while not _shutdown:
            try:
                # Receive incremental patch and apply to the in-memory model.
                # TimeoutError is expected when idle — the default 3s timeout
                # acts as a loop heartbeat for periodic saves and shutdown checks.
                patch = sub.get_object_model_patch()
                object_model.update_from_json(patch)
                tracker.update(object_model)
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
        logger.debug("Saving final state...")
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
        if sub is not None:
            try:
                sub.close()
            except Exception:
                pass
        try:
            cmd.close()
        except Exception:
            pass

        logger.debug("Vigil daemon stopped")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        # DSF only reports the exit code, so print the traceback to stderr
        # where it ends up in the DWC console and the plugin log.
        sys.stderr.write("Vigil daemon terminated with an unhandled exception:\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)
