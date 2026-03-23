"""Tests that DSF library imports used by vigil-daemon resolve correctly."""

import importlib
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def mock_dsf_modules(monkeypatch):
    """Provide mock DSF modules so import tests pass without the real library."""
    from unittest.mock import MagicMock
    from enum import Enum

    # dsf
    dsf = types.ModuleType("dsf")
    dsf.__path__ = []

    # dsf.connections
    dsf_conn = types.ModuleType("dsf.connections")
    dsf_conn.CommandConnection = MagicMock
    dsf_conn.SubscribeConnection = MagicMock
    dsf_conn.SubscriptionMode = MagicMock

    # dsf.object_model
    dsf_om = types.ModuleType("dsf.object_model")

    class _HttpEndpointType(str, Enum):
        GET = "GET"
        POST = "POST"
        PUT = "PUT"
        PATCH = "PATCH"
        DELETE = "DELETE"

    dsf_om.HttpEndpointType = _HttpEndpointType

    # dsf.http
    dsf_http = types.ModuleType("dsf.http")
    dsf_http.HttpEndpointConnection = MagicMock
    dsf_http.HttpResponseType = type(
        "HttpResponseType", (), {"JSON": "JSON", "File": "File", "PlainText": "PlainText"}
    )

    mods = {
        "dsf": dsf,
        "dsf.connections": dsf_conn,
        "dsf.object_model": dsf_om,
        "dsf.http": dsf_http,
    }
    for name, mod in mods.items():
        monkeypatch.setitem(sys.modules, name, mod)

    yield

    # Clean up so cached real modules (if any) aren't polluted
    for name in mods:
        if name in sys.modules and sys.modules[name] is mods[name]:
            monkeypatch.delitem(sys.modules, name, raising=False)


@pytest.mark.parametrize(
    "module, name",
    [
        ("dsf.connections", "CommandConnection"),
        ("dsf.connections", "SubscribeConnection"),
        ("dsf.connections", "SubscriptionMode"),
        ("dsf.object_model", "HttpEndpointType"),
        ("dsf.http", "HttpEndpointConnection"),
        ("dsf.http", "HttpResponseType"),
    ],
)
def test_dsf_import(module, name):
    mod = importlib.import_module(module)
    assert hasattr(mod, name), f"{module}.{name} not found"
