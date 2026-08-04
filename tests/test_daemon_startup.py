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
