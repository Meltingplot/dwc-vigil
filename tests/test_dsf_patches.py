"""The dsf-python compatibility patches at the top of vigil-daemon.py.

The plugin ships one daemon for two DSF generations, and dsf-python 3.7 is a
substantial rewrite of 3.6: hand-written model properties became `model_prop`
descriptors and `BaseConnection.connect` was renamed to `_connect`. These tests stand
in for both library shapes so a rename cannot go unnoticed again — the connect patch in
particular failed silently on 3.7, leaving the recv(50) truncation it exists to fix.
"""

import importlib.util
import json
import os
import sys
import types
from enum import Enum
from unittest.mock import MagicMock

import pytest

DAEMON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dsf", "vigil-daemon.py")


class _BoardState(str, Enum):
    """dsf-python's enum, in both generations: no timedOut."""

    unknown = "unknown"
    flashing = "flashing"
    running = "running"


def _make_model_prop(name, enum_cls):
    """A property that rejects unknown enum values, as both generations do."""
    storage = "_" + name

    def getter(self):
        return getattr(self, storage, None)

    def setter(self, value):
        setattr(self, storage, enum_cls(value) if isinstance(value, str) else value)

    return property(getter, setter)


def _install_dsf(monkeypatch, connect_name):
    """Install a fake dsf package whose BaseConnection uses the given method name."""
    created = {}

    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__path__ = []
        for key, value in attrs.items():
            setattr(mod, key, value)
        created[name] = mod
        return mod

    class Board:
        state = _make_model_prop("state", _BoardState)

    class NetworkInterfaceType(str, Enum):
        lan = "lan"
        wifi = "wifi"

    class NetworkInterface:
        type = _make_model_prop("type", NetworkInterfaceType)

    class AxisLetter(str, Enum):
        none = ""
        X = "X"

    class Axis:
        letter = _make_model_prop("letter", AxisLetter)

    class BaseConnection:
        def __init__(self):
            self.timeout = 1
            self.input = ""
            self.id = None
            self.socket = None

    # The method the plugin has to find, under whichever name this generation uses
    setattr(BaseConnection, connect_name, lambda self, init_message, socket_file: None)

    class ServerInitMessage:
        PROTOCOL_VERSION = 12

        @classmethod
        def from_json(cls, data):
            instance = cls()
            instance.version = data["version"]
            instance.id = data["id"]
            return instance

        def is_compatible(self):
            return True

    class PluginManifest:
        def __init__(self):
            self._data = {}

    module("dsf")
    module("dsf.object_model", HttpEndpointType=Enum("HttpEndpointType", {"GET": "GET", "POST": "POST"}))
    module("dsf.object_model.plugins")
    module("dsf.object_model.plugins.plugin_manifest", PluginManifest=PluginManifest)
    module("dsf.object_model.model_dictionary", ModelDictionary=lambda *a, **k: {})
    module("dsf.object_model.boards")
    module("dsf.object_model.boards.boards", Board=Board, BoardState=_BoardState)
    module("dsf.object_model.network")
    module("dsf.object_model.network.network_interface_type", NetworkInterfaceType=NetworkInterfaceType)
    module("dsf.object_model.network.network_interface", NetworkInterface=NetworkInterface,
           NetworkInterfaceType=NetworkInterfaceType)
    module("dsf.object_model.move")
    module("dsf.object_model.move.axis", Axis=Axis, AxisLetter=AxisLetter)
    module("dsf.connections", CommandConnection=MagicMock, SubscribeConnection=MagicMock,
           SubscriptionMode=MagicMock)
    module("dsf.connections.base_connection", BaseConnection=BaseConnection)
    module("dsf.connections.init_messages")
    module("dsf.connections.init_messages.server_init_message", ServerInitMessage=ServerInitMessage)
    module("dsf.connections.exceptions", IncompatibleVersionException=type("IVE", (Exception,), {}))
    module("dsf.http", HttpEndpointConnection=MagicMock,
           HttpResponseType=type("HttpResponseType", (), {"JSON": "JSON", "File": "File", "PlainText": "PlainText"}))

    for name, mod in created.items():
        monkeypatch.setitem(sys.modules, name, mod)

    spec = importlib.util.spec_from_file_location("vigil_daemon_patched", DAEMON)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    return daemon, BaseConnection, Board, NetworkInterface, Axis


@pytest.fixture(params=["connect", "_connect"], ids=["dsf3.6", "dsf3.7"])
def dsf(request, monkeypatch):
    """Both library shapes: 3.6 names the method connect(), 3.7 _connect()."""
    daemon, base_connection, board, network_interface, axis = _install_dsf(monkeypatch, request.param)
    return types.SimpleNamespace(
        daemon=daemon,
        connect_name=request.param,
        BaseConnection=base_connection,
        Board=board,
        NetworkInterface=network_interface,
        Axis=axis,
    )


class _FakeSocket:
    """Answers a greeting far longer than the 50 bytes dsf-python reads."""

    def __init__(self, payload):
        self.payload = payload.encode()
        self.offset = 0

    def connect(self, _file):
        pass

    def settimeout(self, _timeout):
        pass

    def recv(self, size):
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


def test_connect_patch_lands_on_the_method_the_library_actually_calls(dsf, monkeypatch):
    # The whole point: on 3.7 the method is _connect, and writing only `connect`
    # would leave the truncating recv(50) in place with no error to show for it.
    patched = getattr(dsf.BaseConnection, dsf.connect_name)
    assert patched.__name__ == "_patched_connect"


def test_connect_reads_a_greeting_longer_than_fifty_bytes(dsf, monkeypatch):
    greeting = json.dumps({"version": 12, "id": "8f14e45f-ceea-467a-9d2d-fcf2d0e9e4b1"})
    assert len(greeting) > 50, "greeting must exceed the recv(50) dsf-python uses"

    sock = _FakeSocket(greeting + '{"trailing": true}')
    monkeypatch.setattr(dsf.daemon._socket, "socket", lambda *a, **k: sock)

    connection = dsf.BaseConnection()
    connection.send = lambda _message: None
    connection.receive_response = lambda: types.SimpleNamespace(success=True)

    getattr(connection, dsf.connect_name)(types.SimpleNamespace(mode="Command"), "/tmp/dsf.sock")

    assert connection.id == "8f14e45f-ceea-467a-9d2d-fcf2d0e9e4b1"
    # Bytes past the init message belong to the next read, not the bin
    assert connection.input == '{"trailing": true}'


def test_board_state_accepts_values_dsf_python_omits(dsf):
    board = dsf.Board()
    # Neither generation's enum has timedOut, and the unpatched setter raises
    # ValueError for it — which takes down the whole get_object_model() call.
    board.state = "timedOut"
    assert board.state == "timedOut"

    board.state = "running"
    assert board.state == "running"


def test_a_genuinely_unknown_board_state_falls_back(dsf):
    board = dsf.Board()
    board.state = "on fire"
    assert board.state == "unknown"


def test_unknown_network_interface_type_falls_back(dsf):
    interface = dsf.NetworkInterface()
    interface.type = "ethernet"
    assert interface.type in ("ethernet", "unknown")

    interface.type = "carrier-pigeon"
    assert interface.type == "unknown"


def test_uninitialised_axis_letter_falls_back(dsf):
    axis = dsf.Axis()
    axis.letter = "\x00"
    assert axis.letter == ""

    axis.letter = "X"
    assert axis.letter == "X"
