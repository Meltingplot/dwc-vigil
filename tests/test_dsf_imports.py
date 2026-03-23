"""Tests that DSF library imports used by vigil-daemon resolve correctly."""

import importlib

import pytest


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
