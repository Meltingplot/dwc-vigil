"""Tests for the daemon startup path (DCS connection retries)."""

import importlib.util
import os
import sys
import types
from enum import Enum
from unittest.mock import MagicMock

import pytest

DAEMON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dsf",
    "vigil-daemon.py",
)


@pytest.fixture
def daemon(monkeypatch):
    """Import vigil-daemon.py with the dsf library mocked out."""
    dsf = types.ModuleType("dsf")
    dsf.__path__ = []

    dsf_conn = types.ModuleType("dsf.connections")
    dsf_conn.CommandConnection = MagicMock
    dsf_conn.SubscribeConnection = MagicMock
    dsf_conn.SubscriptionMode = MagicMock

    dsf_om = types.ModuleType("dsf.object_model")

    class _HttpEndpointType(str, Enum):
        GET = "GET"
        POST = "POST"

    dsf_om.HttpEndpointType = _HttpEndpointType
    dsf_om.MessageType = Enum("MessageType", {"Success": 0, "Warning": 1, "Error": 2})
    dsf_om.LogLevel = Enum("LogLevel", {"Debug": "debug", "Info": "info", "Warn": "warn", "Off": "off"})

    dsf_http = types.ModuleType("dsf.http")
    dsf_http.HttpEndpointConnection = MagicMock
    dsf_http.HttpResponseType = type(
        "HttpResponseType", (), {"JSON": "JSON", "File": "File", "PlainText": "PlainText"}
    )

    for name, mod in [
        ("dsf", dsf),
        ("dsf.connections", dsf_conn),
        ("dsf.object_model", dsf_om),
        ("dsf.http", dsf_http),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)

    spec = importlib.util.spec_from_file_location("vigil_daemon", DAEMON_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FlakyConnection:
    """Connection stub that fails a given number of times before succeeding."""

    def __init__(self, failures):
        self.failures = failures
        self.attempts = 0

    def connect(self):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise ConnectionRefusedError("DCS not ready")


def test_connect_succeeds_on_first_attempt(daemon):
    conn = _FlakyConnection(failures=0)
    assert daemon.connect_with_retry(conn, "Test", attempts=3, delay=0) is True
    assert conn.attempts == 1


def test_connect_retries_until_dcs_is_available(daemon):
    conn = _FlakyConnection(failures=2)
    assert daemon.connect_with_retry(conn, "Test", attempts=5, delay=0) is True
    assert conn.attempts == 3


def test_connect_raises_after_all_attempts(daemon):
    conn = _FlakyConnection(failures=99)
    with pytest.raises(RuntimeError, match="failed after 4 attempts"):
        daemon.connect_with_retry(conn, "Test", attempts=4, delay=0)
    assert conn.attempts == 4


def test_connect_aborts_when_shutdown_requested(daemon, monkeypatch):
    conn = _FlakyConnection(failures=99)
    monkeypatch.setattr(daemon, "_shutdown", True)
    assert daemon.connect_with_retry(conn, "Test", attempts=3, delay=0) is False
    assert conn.attempts == 0


def test_warnings_wait_for_the_command_connection_and_reach_dwc_as_warnings(daemon, capsys):
    daemon.logger.warning("connected after %d attempts", 3)
    daemon.logger.error("boom")

    # DSF turns everything on stderr into an "Error:" console message, so only the
    # error is there; the warning is held back
    assert capsys.readouterr().err == "boom\n"
    assert daemon._deferred_warnings.pending == ["connected after 3 attempts"]

    cmd = MagicMock()
    daemon._deferred_warnings.send_to(cmd)
    cmd.write_message.assert_called_once_with(
        daemon.MessageType.Warning, "[Vigil]: connected after 3 attempts", True, daemon.LogLevel.Warn
    )
    assert daemon._deferred_warnings.pending == []
    assert capsys.readouterr().err == ""

    # Nothing to send: DSF is not bothered
    daemon._deferred_warnings.send_to(cmd)
    cmd.write_message.assert_called_once()


def test_warnings_dsf_refuses_fall_back_to_stderr_instead_of_getting_lost(daemon, capsys):
    daemon.logger.warning("first")
    daemon.logger.warning("second")
    cmd = MagicMock()
    cmd.write_message.side_effect = [ConnectionError("gone"), None]

    daemon._deferred_warnings.send_to(cmd)

    assert capsys.readouterr().err == "first\n"
    assert cmd.write_message.call_count == 2
    assert daemon._deferred_warnings.pending == []


def test_warnings_from_the_tracker_and_friends_take_the_same_route(daemon, capsys):
    import logging

    logging.getLogger("vigil.tracker").warning("odd model")
    assert capsys.readouterr().err == ""
    assert daemon._deferred_warnings.pending == ["odd model"]


def test_reimporting_the_daemon_does_not_stack_handlers(daemon):
    import logging

    owned = [h for h in logging.getLogger("vigil").handlers if getattr(h, "_vigil_owned", False)]
    assert len(owned) == 2
