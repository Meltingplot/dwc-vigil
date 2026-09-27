"""Shared fixtures: the daemon imported with the dsf library mocked out."""

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
