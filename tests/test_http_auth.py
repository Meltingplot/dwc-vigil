"""Tests for session enforcement on the daemon's DSF HTTP endpoints.

DuetWebServer forwards every request to a plugin endpoint, logged in or not, and only
reports the session the X-Session-Key header resolved to (-1 for none). The daemon has
to refuse anonymous requests itself.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class _FakeHttpConnection:
    """Stands in for dsf.http.HttpEndpointConnection: one request, records the reply."""

    def __init__(self, request):
        self.request = request
        self.responses = []

    async def read_request(self):
        return self.request

    async def send_response(self, status_code, response="", response_type=None):
        self.responses.append((status_code, response, response_type))


def _request(**overrides):
    fields = {"session_id": 7, "queries": {}, "headers": {}, "content_type": "", "body": ""}
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _serve(handler, request):
    conn = _FakeHttpConnection(request)
    asyncio.run(handler(conn))
    assert len(conn.responses) == 1
    return conn.responses[0]


def test_request_with_a_session_reaches_the_handler(daemon):
    handler_func = MagicMock(return_value={"status": 200, "body": '{"ok": true}'})
    status, body, _ = _serve(daemon._make_async_handler("tracker", handler_func), _request(session_id=3))

    handler_func.assert_called_once_with("tracker", "", {})
    assert status == 200
    assert body == '{"ok": true}'


@pytest.mark.parametrize("session_id", [-1, 0, None, "3"], ids=["anonymous", "zero", "null", "string"])
def test_request_without_a_session_is_refused(daemon, session_id):
    # -1 is what DSF sends for a missing or unknown key; DSF never registers session 0
    handler_func = MagicMock()
    status, body, response_type = _serve(
        daemon._make_async_handler("tracker", handler_func), _request(session_id=session_id)
    )

    handler_func.assert_not_called()
    assert status == 401
    assert "X-Session-Key" in json.loads(body)["error"]
    assert response_type == daemon.HttpResponseType.JSON


def test_request_without_a_session_field_is_refused(daemon):
    request = _request()
    del request.session_id
    handler_func = MagicMock()
    status, _, _ = _serve(daemon._make_async_handler("tracker", handler_func), request)

    handler_func.assert_not_called()
    assert status == 401


def test_every_registered_endpoint_refuses_anonymous_requests(daemon):
    handlers = {}

    def add_http_endpoint(http_type, namespace, path):
        endpoint = MagicMock()
        endpoint.set_endpoint_handler.side_effect = lambda h: handlers.__setitem__((http_type, path), h)
        return endpoint

    cmd = MagicMock()
    cmd.add_http_endpoint.side_effect = add_http_endpoint
    tracker = MagicMock()
    daemon.register_endpoints(cmd, tracker)

    assert len(handlers) == len(daemon.ENDPOINTS)
    for key, handler in handlers.items():
        status, _, _ = _serve(handler, _request(session_id=-1, body='{"scope": "all", "description": "abc"}'))
        assert status == 401, key
    # Neither the GET nor the POST handlers got to read or reset anything
    assert tracker.method_calls == []
